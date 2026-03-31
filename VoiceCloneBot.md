# VoiceCloneBot (OpenClaw 通用语音交互插件机制)

## 1. 项目愿景与定位

VoiceCloneBot 旨在为大模型 Agent（具体化为本地开源项目 **OpenClaw**）提供一套**完全解耦、高拟真度、且轻量泛用的 Voice-to-Voice（语音到语音）克隆插件通信机制**。

它的核心交互效果是：
- 用户在聊天端（如 Telegram）向机器人发送一段自己的语音。
- 机器人听懂语音，并使用其思考引擎（如 LM Studio）产出文字回复。
- **最终，机器人使用该用户刚才发来的原声作为音色锚点，把生成的文字合成为“克隆后的该用户声音”发送回给用户，形成仿佛“复读机/照镜子”般的拟真交流体验。**

为了作为开源项目发布，本架构摆脱了硬编码。它不干涉 ASR（语音识别）与 LLM（文本生成），而是专注于如何优雅地提供**TTS与零样本语音克隆**，并把它沉淀为标准的 OpenClaw `Skill`。

---

## 2. 宏观架构设计 (V2 版)

我们采用了“**重后端，轻协议**”的通信拓扑。

### 模块一：前置依赖 (外部)
- **Speech-to-Text (ASR)**：不由本插件实现。依赖于 OpenClaw 内置的 `openai-whisper` 等技能来处理输入侧并保存原始录音。
- **Brain (LLM)**：不由本插件实现。由 OpenClaw 的中枢（如接入本地 LM Studio 中的模型）生成需要被念出来的话。

### 模块二：底层推理微服务 (Server 引擎)
放置于 `/server` 目录下。
- 这是一套守护进程式的 **FastAPI 后端**。
- **存在意义**：重型 PyTorch 语音合成大模型（如 F5-TTS）每次装载进 VRAM 需要数十秒。我们在此将其常驻内存，只暴露 `http://127.0.0.1:8000/clone` 这一个无状态的 API。只要传给它一段待说的 `<text>` 和声音克隆参考源 `<ref_audio>`，它就迅速生成一条本地 `.ogg` 录音文件并返回路径。

### 模块三：OpenClaw 交互端 (Skill 包装)
放置于 `/skill` 目录下。
- **SKILL.md**：定义了本项机制的 Agent 触发规范，指导 OpenClaw 如何根据上下文提取用户最新的录音，组织文字，并调用通信脚本。
- **tts_client.py**：作为轻量级 CLI 客户端。OpenClaw 大脑只执行此脚本，通过参数传递参数。一旦获取到后端回传的音频地址，立刻在其输出末尾添加 OpenClaw 原生的附件语法 `MEDIA:<文件绝对路径>`，以实现发送语音。

---

## 3. 设计思想极要 (给后续接手 Agent 的提示)

如果你是负责继续更新和完成代码的 Agent（或开发者），请务必遵守以下全局设计约定：

### 3.1 引擎工厂模式 (Engine Factory Pattern)
本系统在 TTS 推理层（位于 `/server/core_tts.py`）使用动态引擎插槽架构，以便适应多元化的硬件要求：
- 追求极致资源优化：应可选入体积不到 1GB，速度如飞的 **Qwen3-TTS (0.6BD)** 或 **OpenVoice V2**。
- 追求惊艳的高拟真语气：应可选入 **F5-TTS**（DiT 流匹配架构）或 **CosyVoice**。
请你在后续代码扩展中，基于 `BaseTTSEngine` 类提供接口，通过 `TTS_BACKEND` 等环境变量，让这两款以上的主力声学模型能够自由装载、切换，确保能在 Mac (MPS)、Linux (CUDA) 和 Win 平台通用。

### 3.2 严密且统一的权重管理 (Model Sandbox)
为了防止用户每次安装此技能都在工作区下载数十个 GB 的 HuggingFace 原始断点造成脏乱，或者多个技能相互覆盖，所有的重型模型权重 **必须统一下载且读取于系统全局锚点**：
`~/.openclaw/models/voice-clone/`
请在编写真正的下载脚本（`install.sh`）与 Python 内部调用装载路径时，严格寻址到此全局文件夹。

### 3.3. 依赖最小化机制 (Requirements Isolation)
Voice Clone 极易引发 PyTorch、Torchaudio、甚至 FlashAttention 的环境版本地狱。
未来的执行者必须将所需的依赖清单编写在 `server/requirements.txt` 中，并在 `install.sh` 里默认使用 `venv`（或用户环境下的 Anaconda）为其包装严密的沙盒系统。

---

## 4. 目录流转与全貌解说

目前仓库目录拓扑及其内部含义如下：

```
VoiceCloneBot/
├── README.md               # 最终用户的开箱指南 (面向人脑)
├── VoiceCloneBot.md        # 系统全景设计文档 (当前文件，面向 AI 或开发者)
├── install.sh              # 面向部署的运维脚本，用于装载 Python 环境与拉取上述全局权重
├── skill/                  # OpenClaw 的执行端代码
│   ├── SKILL.md            # 向 OpenClaw 说明它该在什么模式下、如何提取音频给下方的客户端
│   └── scripts/
│       └── tts_client.py   # 轻量客户端脚本 (被 OpenClaw.json 触发并发送 Post 请求)
│
└── server/                 # 核心的后台内存推演系统
    ├── app.py              # 起点守护服务 (Web 推理节点)
    ├── core_tts.py         # 核心推理：这包含着多态生成逻辑和对接算法库入口的占位符，待接续的 Agent 进行丰满
    └── requirements.txt    # 核心的后端库依赖 (torch, f5-tts 等待确认填入)
```

## 5. 待完善的接力动作 (TODOs)

目前的接手方（后续 Agent）应当：
1. **挑大梁**：在对比 F5-TTS 和 Qwen/OpenVoice 之间作出首选开源引擎决定。
2. **写驱动**：将真实的开源语音推理底层组装进 `server/core_tts.py`。
3. **管环境**：为选定的合成方案在 `install.sh` 编写健壮的模型权重与 `pip` 下载逻辑。
4. **长短句兜底**：如果在 `core_tts.py` 里生成大量长句，需要补充一套基于符号（或者逗号句号）的分句生成切片合并机制，以防多段生成的显存爆炸和响应迟钝。
