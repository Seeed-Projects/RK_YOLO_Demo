# Use Python 3.11 slim image as base (matching the wheel requirement)
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set PYTHONPATH to include the app directory
ENV PYTHONPATH=/app

# Install system dependencies for OpenCV and others
# libgl1: replacement for libgl1-mesa-glx in Debian 12 (Bookworm)
# libglib2.0-0: for cv2
# libgomp1: for OpenMP support if needed
# libsm6, libxext6, libxrender1: common OpenCV dependencies
# libxcb-*: dependencies for Qt (bundled in opencv-python) to fix "Could not load the Qt platform plugin 'xcb'"
# v4l-utils: for camera enumeration with v4l2-ctl
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libxcb-cursor0 \
    libxcb-xinerama0 \
    libxcb-keysyms1 \
    libxcb-image0 \
    libxcb-shm0 \
    libxcb-icccm4 \
    libxcb-sync1 \
    libxcb-xfixes0 \
    libxcb-shape0 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxkbcommon-x11-0 \
    v4l-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
# Use --no-cache-dir to keep image small
RUN pip install --no-cache-dir -r requirements.txt

# Copy RKNN Toolkit Lite2 wheel
COPY package/rknn_toolkit_lite2-2.3.2-cp311-cp311-manylinux_2_17_aarch64.manylinux2014_aarch64.whl ./package/

# Install RKNN Toolkit Lite2 wheel only if on compatible architecture
RUN if [ "$(dpkg --print-architecture)" = "arm64" ] || [ "$(dpkg --print-architecture)" = "aarch64" ]; then \
        pip install --no-cache-dir package/rknn_toolkit_lite2-2.3.2-cp311-cp311-manylinux_2_17_aarch64.manylinux2014_aarch64.whl; \
    else \
        echo "Warning: RKNN toolkit not installed - incompatible architecture $(dpkg --print-architecture)"; \
        echo "Note: This Docker image will not support hardware acceleration on x86_64 systems"; \
    fi

# Copy librknnrt.so to /usr/lib/ from src/rk3588
COPY lib/librknnrt.so /usr/lib/
RUN chmod 755 /usr/lib/librknnrt.so

# Copy the rest of the application code from src/rk3588
COPY src/ /app/src/
COPY py_utils/ /app/py_utils/
COPY app.py /app/app.py
COPY model/yolo11n.rknn /app/model/yolo11n.rknn

# Expose the Flask app port
EXPOSE 5000

# Set the default command to run the Flask application
CMD ["python", "app.py"]
