import os
import cv2
import time
import numpy as np
import threading
import socket
import pickle
import struct
from typing import Tuple, List, Optional

# 尝试导入 RKNN-Toolkit-Lite2
try:
    from rknnlite.api import RKNNLite
    RKNN_LITE_AVAILABLE = True
except ImportError:
    RKNN_LITE_AVAILABLE = False

# --- 常量与配置 ---
OBJ_THRESH = 0.25
NMS_THRESH = 0.45
IMG_SIZE = (640, 640)

CLASSES = ("person", "bicycle", "car","motorbike ","aeroplane ","bus ","train","truck ","boat","traffic light",
           "fire hydrant","stop sign ","parking meter","bench","bird","cat","dog ","horse ","sheep","cow","elephant",
           "bear","zebra ","giraffe","backpack","umbrella","handbag","tie","suitcase","frisbee","skis","snowboard","sports ball","kite",
           "baseball bat","baseball glove","skateboard","surfboard","tennis racket","bottle","wine glass","cup","fork","knife ",
           "spoon","bowl","banana","apple","sandwich","orange","broccoli","carrot","hot dog","pizza ","donut","cake","chair","sofa",
           "pottedplant","bed","diningtable","toilet ","tvmonitor","laptop  ","mouse    ","remote ","keyboard ","cell phone","microwave ",
           "oven ","toaster","sink","refrigerator ","book","clock","vase","scissors ","teddy bear ","hair drier", "toothbrush ")

# --- 数学后处理函数 ---

def dfl(position):
    n, c, h, w = position.shape
    p_num = 4
    mc = c // p_num
    y = position.reshape(n, p_num, mc, h, w)
    y_exp = np.exp(y - np.max(y, axis=2, keepdims=True))
    y_softmax = y_exp / np.sum(y_exp, axis=2, keepdims=True)
    acc_metrix = np.arange(mc).reshape(1, 1, mc, 1, 1).astype(np.float32)
    return (y_softmax * acc_metrix).sum(2)

def box_process(position):
    grid_h, grid_w = position.shape[2:4]
    col, row = np.meshgrid(np.arange(0, grid_w), np.arange(0, grid_h))
    col = col.reshape(1, 1, grid_h, grid_w)
    row = row.reshape(1, 1, grid_h, grid_w)
    grid = np.concatenate((col, row), axis=1)
    stride = np.array([IMG_SIZE[1]//grid_h, IMG_SIZE[0]//grid_w]).reshape(1,2,1,1)
    position = dfl(position)
    box_xy  = grid + 0.5 - position[:,0:2,:,:]
    box_xy2 = grid + 0.5 + position[:,2:4,:,:]
    return np.concatenate((box_xy*stride, box_xy2*stride), axis=1)

def nms_boxes(boxes, scores):
    x, y = boxes[:, 0], boxes[:, 1]
    w, h = boxes[:, 2] - boxes[:, 0], boxes[:, 3] - boxes[:, 1]
    areas = w * h
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1, yy1 = np.maximum(x[i], x[order[1:]]), np.maximum(y[i], y[order[1:]])
        xx2, yy2 = np.minimum(x[i] + w[i], x[order[1:]] + w[order[1:]]), np.minimum(y[i] + h[i], y[order[1:]] + h[order[1:]])
        w1, h1 = np.maximum(0.0, xx2 - xx1 + 1e-5), np.maximum(0.0, yy2 - yy1 + 1e-5)
        inter = w1 * h1
        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        inds = np.where(ovr <= NMS_THRESH)[0]
        order = order[inds + 1]
    return np.array(keep)

# --- 核心推理类 ---

class InferenceEngine:
    def __init__(self):
        self.is_running = False
        self.latest_frame = None
        self.rknn = None
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 需确保 py_utils 文件夹在 backend 目录下
        from py_utils.coco_utils import COCO_test_helper
        self.co_helper = COCO_test_helper(enable_letter_box=True)

    def _inference_loop(self, model_path, cam_id, udp_host, udp_port):
        if not RKNN_LITE_AVAILABLE:
            print("RKNN-Toolkit-Lite2 is not installed"); return

        self.rknn = RKNNLite()
        if self.rknn.load_rknn(model_path) != 0:
            print("Failed to load RKNN model"); return
        # 启动 RK3588 的三核 NPU 性能模式
        if self.rknn.init_runtime(core_mask=RKNNLite.NPU_CORE_0_1_2) != 0:
            print("Failed to init RKNN runtime"); return

        # USB 摄像头初始化
        cap = cv2.VideoCapture(cam_id)
        if not cap.isOpened():
            print(f"Failed to open camera {cam_id}")
            return
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        print(f"USB Camera {cam_id} started. Multi-core NPU active.")

        frame_count = 0
        while self.is_running:
            ret, frame = cap.read()
            if not ret:
                print(f"Failed to read frame from camera {cam_id}, return code: {ret}")
                # 尝试重新连接摄像头
                cap.release()
                cap = cv2.VideoCapture(cam_id)
                if not cap.isOpened():
                    print(f"Failed to reconnect to camera {cam_id}")
                    break
                continue

            # 预处理
            img = self.co_helper.letter_box(im=frame.copy(), new_shape=IMG_SIZE, pad_color=(0,0,0))
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            # 推理
            try:
                outputs = self.rknn.inference(inputs=[np.expand_dims(img, 0)])
            except Exception as e:
                print(f"Error during inference: {e}")
                continue  # 继续下一次循环

            # 后处理逻辑整合
            try:
                boxes, scores, classes_conf = [], [], []
                pair_per_branch = len(outputs)//3
                for i in range(3):
                    boxes.append(box_process(outputs[pair_per_branch*i]))
                    classes_conf.append(outputs[pair_per_branch*i+1])
                    scores.append(np.ones_like(outputs[pair_per_branch*i+1][:,:1,:,:], dtype=np.float32))

                def sp_flatten(_in): return _in.transpose(0,2,3,1).reshape(-1, _in.shape[1])
                boxes = np.concatenate([sp_flatten(_v) for _v in boxes])
                classes_conf = np.concatenate([sp_flatten(_v) for _v in classes_conf])
                scores = np.concatenate([sp_flatten(_v) for _v in scores]).reshape(-1)

                class_max_score = np.max(classes_conf, axis=-1)
                classes = np.argmax(classes_conf, axis=-1)
                _pos = np.where(class_max_score * scores >= OBJ_THRESH)

                f_boxes, f_classes, f_scores = boxes[_pos], classes[_pos], (class_max_score*scores)[_pos]

                # 绘制结果
                if len(f_classes) > 0:
                    real_boxes = self.co_helper.get_real_box(f_boxes)
                    # 应用 NMS
                    keep = nms_boxes(real_boxes, f_scores)
                    for i in keep:
                        box, score, cl = real_boxes[i], f_scores[i], f_classes[i]
                        top, left, right, bottom = [int(_b) for _b in box]
                        cv2.rectangle(frame, (top, left), (right, bottom), (0, 255, 0), 2)
                        cv2.putText(frame, f'{CLASSES[cl]} {score:.2f}', (top, left - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                    # UDP 数据推送
                    try:
                        msg = pickle.dumps({
                            "count": len(keep),
                            "results": [{"class": CLASSES[cl], "box": b.tolist()} for cl, b in zip(f_classes, real_boxes)],
                            "ts": time.time()
                        })
                        self.sock.sendto(struct.pack('!I', len(msg)) + msg, (udp_host, udp_port))
                    except Exception as e:
                        print(f"Error sending UDP data: {e}")
            except Exception as e:
                print(f"Error during post-processing: {e}")

            self.latest_frame = frame
            frame_count += 1

            # 每处理100帧打印一次信息
            if frame_count % 100 == 0:
                print(f"Processed {frame_count} frames...")

        print(f"Inference loop ended after processing {frame_count} frames.")
        cap.release()
        self.rknn.release()

    def start(self, model_path, cam_id, udp_host, udp_port):
        if self.is_running: return False
        self.is_running = True
        threading.Thread(target=self._inference_loop, args=(model_path, cam_id, udp_host, udp_port), daemon=True).start()
        return True

    def stop(self):
        self.is_running = False