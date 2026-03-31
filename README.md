# OpenClaw 语音克隆交互组件 (Voice-to-Voice Plugin)

这是一个为 **OpenClaw** 设计的通用“语音分身”交互插件机制。
当处于交互状态时，如果用户发送了一段语音消息，OpenClaw 会先识别用户的文字意图，大模型思考出回复内容，然后用**用户的原声（或指定的声音参考提取音色）**合成最终音频，发回给用户。这形成了完整封闭并且极为连贯的声音镜像（Mirror Voice）体验。

## 机制与分工

该插件遵循 OpenClaw 的通用解耦思路：
1. **语音识别 (ASR)**：请依赖已有的官方 `openai-whisper` 功能将你发来的语音转成文字。
2. **文本生成 (LLM)**：由用户配置在 OpenClaw 里的 LM-Studio 端点全权生成逻辑内容。
3. **语音克隆引擎 (TTS)**：本插件只提供重度的 **常驻推理端点 (FastAPI)** 加 **Skill (终端调用接口)**，专门负责吃下文本，克隆特定的参考原声进而吐出拟真后的录音。

## 安装步骤

### 1. 确认前置依赖机制
请务必保证你所在的 OpenClaw 已安装并能够使用 `openai-whisper` 进行音频转录。这就使得 OpenClaw 的内存流里知道你此前发送的参考原始文件的本地路径。

### 2. 初始化环境与克隆模型
为了不每次运行都重新读大模型，此组件采用重后端轻前端策略。
在终端执行安装脚本：
```bash
cd openclaw-voice-clone
bash install.sh
```
*(注意：此脚本会在本机 `~/.openclaw/models/voice-clone` 生成模型权重存放域，以便统一且不重复地下拉 F5-TTS 或相关底层通用模型结构)*

### 3. 配置 OpenClaw Skill 侧
将本项目的 `skill` 目录链接至你的 OpenClaw 技能库中：
```bash
ln -s ${PWD}/skill ~/.openclaw/skills/voice-clone
# 或是根据你的自定义目录，将其链入 main-workspace/my-skills/skills/voice-clone
```

### 4. 启动后端常驻推理服务
```bash
# 在插件主目录下
source venv/bin/activate
cd server
python app.py
```
这就使本地拥有了一个常驻响应 `http://127.0.0.1:8000/synthesize` 的 TTS 克隆微服务。

## 使用指引

一旦装配完成并启动了守护服务：
1. 向 OpenClaw 说：**“进入语音克隆复读模式。接下来请用这句语音作为你的声音锚点参考。”**
2. 发送一段十几秒长度的清晰语音录音给 OpenClaw。
3. OpenClaw 会记住该语音媒体。随后针对你聊的每一句话，系统不仅帮你文字作答，更会自动唤起本 `voice-clone` 技能发出 `.ogg` 录音回来！
