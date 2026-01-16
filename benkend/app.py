import cv2
import time
import argparse
import threading

from flask import Flask, Response, request, jsonify
from flask_cors import CORS  # 处理跨域
from src.inference_engine import InferenceEngine
import subprocess

app = Flask(__name__)
CORS(app) # 允许前端跨域访问

# Global variables to store the engine and default parameters
engine = None
default_model_path = "/app/model/yolo11n.rknn"
default_camera_id = 0
default_udp_host = "127.0.0.1"
default_udp_port = 8080

@app.route('/api/start', methods=['POST'])
def start_task():
    global engine
    print(f"Start request received - Method: {request.method}, Content-Type: {request.content_type}")  # Debug print
    try:
        # Check if request contains JSON data
        if not request.is_json:
            print("Request is not JSON")
            return jsonify({"status": "error", "message": "Request must be JSON"}), 400

        # Try to get raw data for debugging
        raw_data = request.get_data(as_text=True)
        print(f"Raw request data: {raw_data}")  # Debug print

        params = request.json
        print(f"Received start request with params: {params}")  # Debug print

        if params is None:
            print("No JSON data received")
            return jsonify({"status": "error", "message": "No JSON data received"}), 400

        # Use provided parameters or defaults
        model_path = params.get('model_path', default_model_path)
        cam_id = params.get('cam_id', default_camera_id)  # Fixed typo: was 'cam_i'
        udp_host = params.get('udp_host', default_udp_host)
        udp_port = params.get('udp_port', default_udp_port)

        print(f"Using parameters - model: {model_path}, cam: {cam_id}, udp: {udp_host}:{udp_port}")  # Debug print

        # Initialize engine if not already done
        if engine is None:
            print("Creating new engine instance")  # Debug print
            engine = InferenceEngine()
        elif engine.is_running:
            print("Engine already running, stopping first")  # Debug print
            # If engine is already running, stop it first
            engine.stop()
            # Wait a moment for cleanup
            import time
            time.sleep(0.5)

        success = engine.start(
            model_path,
            cam_id,
            udp_host,
            udp_port
        )
        print(f"Engine start result: {success}")  # Debug print
        return jsonify({"status": "success" if success else "failed"})
    except Exception as e:
        print(f"Error in start_task: {str(e)}")  # Debug print
        import traceback
        traceback.print_exc()  # Print full stack trace
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/stop', methods=['POST'])
def stop_task():
    global engine
    try:
        print("Received stop request")  # Debug print
        if engine:
            engine.stop()
            print("Engine stopped")  # Debug print
        else:
            print("No engine instance to stop")  # Debug print
        return jsonify({"status": "stopped"})
    except Exception as e:
        print(f"Error in stop_task: {str(e)}")  # Debug print
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/video_feed')
def video_feed():
    def gen():
        global engine
        while True:
            if engine and engine.latest_frame is not None:
                _, buffer = cv2.imencode('.jpg', engine.latest_frame)
                yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(0.04)
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

# backend/app.py 增加设备扫描接口
@app.route('/api/list_cameras', methods=['GET'])
def list_cameras():
    """扫描系统中所有的 video 设备"""
    camera_list = []
    try:
        # 使用 v4l2-ctl 列出设备 (需要安装 v4l-utils: sudo apt install v4l-utils)
        output = subprocess.check_output(["v4l2-ctl", "--list-devices"]).decode()
        camera_list.append({"info": output})
    except:
        # 备选方案：直接检查 /dev/
        import os
        devs = [f"/dev/{d}" for d in os.listdir('/dev/') if d.startswith('video')]
        camera_list.append({"devices": devs})

    return jsonify(camera_list)

def auto_start_inference(model_path, camera_id, udp_host, udp_port):
    """Automatically start inference with provided parameters"""
    global engine
    # Only start if no engine is already running
    if engine is None or not engine.is_running:
        engine = InferenceEngine()
        success = engine.start(model_path, camera_id, udp_host, udp_port)
        if success:
            print(f"Inference started with model: {model_path}, camera: {camera_id}, UDP: {udp_host}:{udp_port}")
        else:
            print("Failed to start inference")
    else:
        print("Engine already running, skipping auto-start")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='YOLOv11 Object Detection Backend')
    parser.add_argument('--model_path', type=str, default=default_model_path, help='Path to the model file')
    parser.add_argument('--camera_id', type=int, default=default_camera_id, help='Camera ID to use')
    parser.add_argument('--udp_host', type=str, default=default_udp_host, help='UDP host to send detection results')
    parser.add_argument('--udp_port', type=int, default=default_udp_port, help='UDP port to send detection results')

    args = parser.parse_args()

    # Start inference automatically if command-line arguments are provided
    if args.model_path or args.camera_id != default_camera_id or args.udp_host != default_udp_host or args.udp_port != default_udp_port:
        # Start the inference in a separate thread so Flask can start
        inference_thread = threading.Thread(
            target=auto_start_inference,
            args=(args.model_path, args.camera_id, args.udp_host, args.udp_port)
        )
        inference_thread.daemon = True
        inference_thread.start()

    app.run(host='0.0.0.0', port=5000)