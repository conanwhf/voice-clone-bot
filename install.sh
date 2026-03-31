#!/bin/bash
# voice-clone 安装与资源校验脚本

set -e

echo "=== 检查并配置 OpenClaw Voice Clone 通用资源环境 ==="

# 1. 设置模型存放全局常量路径 (参考 openai-whisper 的逻辑隔离机制)
GLOBAL_MODEL_DIR="$HOME/.openclaw/models/voice-clone"
if [ ! -d "$GLOBAL_MODEL_DIR" ]; then
    echo "[!] 未检测到全局模型权重库，正在建立核心锚点目录: $GLOBAL_MODEL_DIR"
    mkdir -p "$GLOBAL_MODEL_DIR"
else
    echo "[*] 模型全景存放库已经就绪: $GLOBAL_MODEL_DIR"
fi

# 2. 拉起或更新独立的 Python 推理沙盒环境
echo "=== 初始化独立的 Python 推理隔离环境 (Venv) ==="
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "[*] 成功创建 venv"
fi

# 切换为隔离期的 Pip 通道
source venv/bin/activate
pip install --upgrade pip

# 3. 安装前序依赖组件 (例如 F5-TTS 或 CosyVoice 的基础需求库将放到这里)
echo "=== 开始解析并安装 Server 端依赖图谱 ==="
if [ -f "server/requirements.txt" ]; then
    pip install -r server/requirements.txt
else
    echo "[!] 警告：未检测到 server/requirements.txt，请保证你已经将其编写完毕。"
fi

echo "=== 引擎配置执行完毕！==="
echo "你现在可以执行："
echo "$ source venv/bin/activate"
echo "$ cd server"
echo "$ python app.py"
