# VoiceCloneBot

> 一套完全自给自足的 OpenClaw 标准语音克隆技能。支持多模型引擎、长文本无限生成、后台自守护。

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/conanwhf/VoiceCloneBot.git
cd VoiceCloneBot

# 2. 安装默认引擎 (F5-TTS)
bash scripts/auto_installer.sh

# 3. 直接使用（后台服务会自动启动）
bash scripts/run_tts.sh --text "你好，这是克隆后的声音。" --ref_audio "参考录音.ogg"
```

## 支持的引擎

| 引擎 | 安装命令 | 大小 | 零样本克隆 | 平台兼容 | 特点 |
| --- | --- | --- | :---: | --- | --- |
| **F5-TTS** | `bash scripts/auto_installer.sh` | ~1.5GB | ✅ | Mac/Linux/Win | 默认引擎。DiT 流匹配，克隆质量天花板 |
| **CosyVoice** | `bash scripts/install_cosyvoice.sh` | ~1.5GB | ✅ | Mac/Linux/Win | 阿里通义。自然韵律极佳 |
| **ChatTTS** | `bash scripts/install_chattts.sh` | ~400MB | ❌ | Mac/Linux/Win | 随机音色。支持 `[laugh]` `[uv_break]` 情绪标签 |
| **OpenVoice** | `bash scripts/install_openvoice.sh` | ~300MB | ✅ | Mac/Linux/Win | MyShell。速度最快，体积最小 |

切换引擎：
```bash
export TTS_BACKEND=cosyvoice  # 可选: f5, cosyvoice, chattts, openvoice
```

## 项目结构

```
VoiceCloneBot/
├── SKILL.md                      # Agent 触发规范 (标准 Skill 格式)
├── VoiceCloneBot.md              # 系统设计文档
├── README.md                     # 本文件
├── scripts/
│   ├── auto_installer.sh         # F5-TTS 默认安装 + OpenClaw 注册
│   ├── install_cosyvoice.sh      # CosyVoice 引擎安装
│   ├── install_chattts.sh        # ChatTTS 引擎安装
│   ├── install_openvoice.sh      # OpenVoice 引擎安装
│   ├── run_tts.sh                # 自动守护 + 推理入口 (Agent 直接调用)
│   ├── uninstall.sh              # 清理脚本
│   └── tts_client.py             # HTTP 通信客户端
└── server/
    ├── app.py                    # FastAPI 后台守护服务
    ├── core_tts.py               # 多引擎工厂 + 长文本切片
    └── requirements.txt          # F5-TTS 基础依赖
```

## 长文本支持

系统内置自动断句切片引擎。无论输入多长的文本（哪怕是整篇文章），都会被自动按句号、问号、逗号等切分为安全片段，逐一生成后无缝拼接。无需手动处理。

## 协议

MIT License
