/**
 * RK3588 前端控制中心逻辑
 */

let runningStatus = false;

// 获取当前用户输入的后端配置
function getServerConfig() {
    // If the user left the server IP empty or kept the placeholder, fall back to the page host
    const ipInput = document.getElementById('server-ip').value;
    const ip = ipInput && ipInput.trim() !== '' ? ipInput.trim() : window.location.hostname;

    return {
        ip: ip,
        model: document.getElementById('model-path').value,
        camId: parseInt(document.getElementById('cam-id').value),
        port: parseInt(document.getElementById('udp-port').value)
    };
}

/**
 * 启动推理任务
 */
async function handleStart() {
    const config = getServerConfig();
    const apiUrl = `http://${config.ip}:5000/api/start`;

    const payload = {
        model_path: config.model,
        cam_id: config.camId,
        udp_host: "127.0.0.1", // 默认发给板子本地监听者
        udp_port: config.port
    };

    console.log("Attempting to start inference with config:", config);
    console.log("Sending request to:", apiUrl);
    console.log("Payload:", payload);

    try {
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        console.log("Response status:", response.status);
        // Check if response is OK before parsing JSON
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log("Response data:", data);

        // Check if the response contains the expected status field
        if (data && typeof data.status !== 'undefined') {
            if (data.status === "success" || data.status === true) {
                console.log("Inference engine started successfully");
                setUIState(true);

                // 设置视频流源 (添加随机数防止浏览器缓存)
                const streamImg = document.getElementById('video-stream');
                const streamUrl = `http://${config.ip}:5000/api/video_feed?t=${Date.now()}`;
                console.log("Setting video stream URL to:", streamUrl);

                // 添加错误处理
                streamImg.onerror = function() {
                    console.error("Failed to load video stream from:", streamUrl);
                    alert("Failed to load video stream. Please check the connection to the backend.");
                };

                streamImg.onload = function() {
                    console.log("Video stream loaded successfully");
                };

                // For multipart streams, sometimes we need to force refresh
                // First try the img element approach
                streamImg.src = ''; // Clear first

                // Also try the video element approach as an alternative
                const videoElement = document.getElementById('video-element');
                videoElement.src = ''; // Clear first

                setTimeout(() => {
                    // Try the img element first
                    streamImg.src = streamUrl;

                    // Hide the video element initially
                    videoElement.classList.add('hidden');
                    streamImg.classList.remove('hidden');
                    // Don't hide loader immediately as stream may take time to start
                    // document.getElementById('loader').classList.add('hidden');

                    console.log("Video stream element is now visible, URL set to:", streamUrl);
                    console.log("Note: Video stream may take a few seconds to appear as inference engine initializes...");

                    // Update UI to indicate that inference is starting
                    const statusTag = document.getElementById('status-tag');
                    statusTag.innerText = "STARTING...";
                    statusTag.className = "text-xs px-2 py-1 rounded bg-yellow-600 font-bold";

                    // Set up error handler to fallback to video element if img fails
                    streamImg.onerror = function() {
                        console.warn("Image element failed to load stream, trying video element...");

                        // Switch to video element
                        streamImg.classList.add('hidden');
                        videoElement.src = streamUrl;
                        videoElement.classList.remove('hidden');

                        // Video element error handler
                        videoElement.onerror = function() {
                            console.error("Failed to load video stream from:", streamUrl);
                            alert("Failed to load video stream. Please check the connection to the backend.");

                            // Reset UI state
                            setUIState(false);
                        };
                    };

                    // Add load event to confirm stream is loading
                    streamImg.onload = function() {
                        console.log("Video stream started loading successfully");

                        // Update status to RUNNING once stream starts
                        const statusTag = document.getElementById('status-tag');
                        statusTag.innerText = "RUNNING";
                        statusTag.className = "text-xs px-2 py-1 rounded bg-green-600 animate-pulse font-bold";

                        // Hide loader once stream is confirmed to be loading
                        document.getElementById('loader').classList.add('hidden');
                    };
                }, 100); // Small delay to ensure proper loading
            } else {
                console.error("Backend returned failure status:", data.status);
                alert("Failed to start engine: Check model path or hardware. Backend returned: " + JSON.stringify(data));
            }
        } else {
            console.error("Unexpected response format from backend:", data);
            alert("Unexpected response from backend: " + JSON.stringify(data));
        }
    } catch (err) {
        alert("Server unreachable. Check IP and ensure backend is running.");
        console.error("Error starting inference:", err);
    }
}

/**
 * 停止推理任务
 */
async function handleStop() {
    const config = getServerConfig();
    console.log("Attempting to stop inference on:", config.ip);

    try {
        const response = await fetch(`http://${config.ip}:5000/api/stop`, { method: 'POST' });
        console.log("Stop response status:", response.status);

        setUIState(false);

        // 重置画面
        const streamImg = document.getElementById('video-stream');
        const videoElement = document.getElementById('video-element');

        streamImg.src = "";  // Clear the source
        videoElement.src = ""; // Clear video element source
        streamImg.removeAttribute('onerror');  // Remove event handlers
        streamImg.removeAttribute('onload');
        streamImg.classList.add('hidden');
        videoElement.classList.add('hidden');
        document.getElementById('loader').classList.remove('hidden');
    } catch (err) {
        console.error("Stop command failed:", err);
    }
}

/**
 * 更新页面 UI 状态
 * @param {boolean} isRunning
 */
function setUIState(isRunning) {
    runningStatus = isRunning;
    const tag = document.getElementById('status-tag');
    const startBtn = document.getElementById('btn-start');

    if (isRunning) {
        // Only set to RUNNING if not already in STARTING state
        if (tag.innerText !== "STARTING...") {
            tag.innerText = "RUNNING";
            tag.className = "text-xs px-2 py-1 rounded bg-green-600 animate-pulse font-bold";
        }
        startBtn.disabled = true;
        startBtn.classList.add('opacity-50', 'cursor-not-allowed');
    } else {
        tag.innerText = "OFFLINE";
        tag.className = "text-xs px-2 py-1 rounded bg-gray-700 font-bold";
        startBtn.disabled = false;
        startBtn.classList.remove('opacity-50', 'cursor-not-allowed');
    }
}

// 添加摄像头列表功能
async function loadCameraList() {
    const config = getServerConfig();
    try {
        const response = await fetch(`http://${config.ip}:5000/api/list_cameras`);
        const cameras = await response.json();

        // 显示摄像头信息到控制台或界面上
        console.log("Available cameras:", cameras);

        // 可以在这里添加UI更新逻辑来显示可用的摄像头
        // 例如，可以动态填充一个下拉菜单
    } catch (err) {
        console.error("Failed to load camera list:", err);
    }
}

// 测试视频流连接
async function testVideoStream() {
    const config = getServerConfig();
    const streamUrl = `http://${config.ip}:5000/api/video_feed`;

    try {
        // 尝试发起一个简单的请求来测试连接
        const response = await fetch(streamUrl, { method: 'HEAD' });
        console.log("Video stream test response status:", response.status);

        if (response.ok) {
            console.log("Video stream connection test successful");
        } else {
            console.error("Video stream connection test failed with status:", response.status);
        }
    } catch (err) {
        console.error("Video stream connection test failed:", err);
    }
}

// 页面加载完成后自动尝试获取摄像头列表
document.addEventListener('DOMContentLoaded', function() {
    // 可以在这里添加初始化逻辑
    console.log("Frontend initialized, ready to connect to backend");
    // If the server-ip field still has the placeholder value or is empty, set it to the current host
    try {
        const serverIpField = document.getElementById('server-ip');
        if (serverIpField) {
            const val = serverIpField.value && serverIpField.value.trim();
            if (!val || val === '192.168.1.100') {
                serverIpField.value = window.location.hostname;
            }
        }
    } catch (e) {
        console.warn('Could not auto-set server-ip field:', e);
    }
});