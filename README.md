# YOLOv11 Object Detection Backend

基于RK3588 NPU加速的目标检测后端服务，支持实时视频流和检测结果获取。

## 功能特性

- 实时目标检测（基于YOLOv11模型）
- NPU硬件加速推理
- HTTP API接口控制
- 实时视频流传输
- 检测结果JSON查询
- 摄像头设备枚举

## 系统要求

- RK3588开发板
- USB摄像头
- Docker环境

## API接口

### 1. 启动推理任务

**接口**: `POST /api/start`

**请求参数**:
```json
{
  "model_path": "/app/model/yolo11n.rknn",
  "cam_id": 0,
  "udp_host": "127.0.0.1",
  "udp_port": 8080
}
```

**参数说明**:
- `model_path`: RKNN模型文件路径
- `cam_id`: 摄像头ID (0, 1, 等)
- `udp_host`: UDP数据发送主机
- `udp_port`: UDP数据发送端口

**响应示例**:
```json
{
  "status": "success"
}
```

**最小启动示例**:
```bash
curl -X POST http://localhost:5000/api/start \
  -H "Content-Type: application/json" \
  -d '{
    "model_path": "/app/model/yolo11n.rknn",
    "cam_id": 0,
    "udp_host": "127.0.0.1",
    "udp_port": 8080
  }'
```

### 2. 停止推理任务

**接口**: `POST /api/stop`

**请求示例**:
```bash
curl -X POST http://localhost:5000/api/stop
```

**响应示例**:
```json
{
  "status": "stopped"
}
```

### 3. 获取实时视频流

**接口**: `GET /api/video_feed`

**使用方式**:
- 在浏览器中直接访问: `http://localhost:5000/api/video_feed`
- 在HTML中使用: `<img src="http://localhost:5000/api/video_feed" />`

### 4. 获取检测结果

**接口**: `GET /api/detection_results`

**响应示例**:
```json
[
  {
    "class": "person",
    "confidence": 0.85,
    "bbox": [100, 50, 200, 150]
  },
  {
    "class": "car",
    "confidence": 0.92,
    "bbox": [300, 200, 450, 300]
  }
]
```

**获取检测结果示例**:
```bash
curl http://localhost:5000/api/detection_results
```

### 5. 枚举摄像头设备

**接口**: `GET /api/list_cameras`

**响应示例**:
```json
[
  {
    "info": "设备信息..."
  }
]
```

## Docker运行

### 构建镜像

```bash
cd benkend
docker build -t yolo11_rk3588:latest -f yolo11.dockerfile .
```

### 运行容器

```bash
sudo docker run -it --rm \
    --privileged \
    --network host \
    --device=/dev/video0 \
    --device=/dev/video1 \
    --device=/dev/dri:/dev/dri \
    --device=/dev/dma_heap:/dev/dma_heap \
    -p 5000:5000 \
    yolo11_rk3588:latest \
    python app.py --model_path /app/model/yolo11n.rknn --camera_id 0 --udp_host 127.0.0.1 --udp_port 8080
```

### 命令行参数

- `--model_path`: 模型文件路径 (默认: `/app/model/yolo11n.rknn`)
- `--camera_id`: 摄像头ID (默认: 0)
- `--udp_host`: UDP主机地址 (默认: `127.0.0.1`)
- `--udp_port`: UDP端口 (默认: 8080)

## 最小使用示例

### 1. 启动服务

```bash
# 启动Docker容器
sudo docker run -d --name yolo_backend \
    --privileged \
    --network host \
    --device=/dev/video0 \
    -p 5000:5000 \
    yolo11_rk3588:latest
```

### 2. 开始检测

```bash
# 启动推理任务
curl -X POST http://localhost:5000/api/start \
  -H "Content-Type: application/json" \
  -d '{
    "model_path": "/app/model/yolo11n.rknn",
    "cam_id": 0,
    "udp_host": "127.0.0.1",
    "udp_port": 8080
  }'
```

### 3. 查看视频流

在浏览器中访问: `http://localhost:5000/api/video_feed`

### 4. 获取检测结果

```bash
# 查询当前检测结果
curl http://localhost:5000/api/detection_results
```

### 5. 停止检测

```bash
# 停止推理任务
curl -X POST http://localhost:5000/api/stop
```

## 前端集成

前端项目位于 `frontend/` 目录，提供图形化界面控制推理任务和显示视频流。

## 错误处理

- `400 Bad Request`: 请求参数错误
- `500 Internal Server Error`: 服务器内部错误
- `200 OK`: 成功响应

## 注意事项

- 确保摄像头设备正确连接
- 模型文件路径必须正确
- 需要足够的硬件资源运行NPU推理
- 首次启动可能需要几秒钟初始化
