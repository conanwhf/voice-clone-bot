# VoiceCloneBot

> OpenClaw 标准语音克隆技能 — 多引擎、长文本、全自动守护。

## 快速开始

```bash
git clone https://github.com/conanwhf/VoiceCloneBot.git
cd VoiceCloneBot
bash scripts/auto_installer.sh
bash scripts/run_tts.sh --text "你好，这是克隆后的声音。" --ref_audio "参考录音.ogg"
```

## 引擎选择

| 引擎 | 安装 | 大小 | 克隆 | 语速 | 特点 |
| --- | --- | --- | :---: | --- | --- |
| **F5-TTS** | `bash scripts/auto_installer.sh` | ~1.5GB | ✅ | 原生 | 默认。克隆质量最高 |
| **CosyVoice** | `bash scripts/install_cosyvoice.sh` | ~1.5GB | ✅ | ffmpeg | 阿里。中文韵律极佳 |
| **ChatTTS** | `bash scripts/install_chattts.sh` | ~400MB | ✅ | ffmpeg | 支持 `[laugh]` 等情绪标签与克隆 |
| **OpenVoice** | `bash scripts/install_openvoice.sh` | ~300MB | ✅ | ffmpeg | 速度最快，体积最小 |

切换引擎：`export TTS_BACKEND=cosyvoice`

## 参数

| 参数 | 说明 | 默认 |
| --- | --- | --- |
| `--text` | 要合成的文字（必填） | — |
| `--ref_audio` | 参考录音路径（必填） | — |
| `--speed` | 语速倍率（0.5-2.0） | 1.0 |

## 语气与情绪

语气由参考录音决定。想要愤怒的回复？用一段愤怒的参考录音。想要温柔的回复？用一段温柔的参考录音。模型会自动提取参考音频中的情感特征并复刻。

## 长文本

无长度限制。系统自动按句子切片、逐句推理、无缝拼接。

## 卸载

```bash
bash scripts/uninstall.sh              # 标准卸载
bash scripts/uninstall.sh --engine NAME # 仅卸载某引擎
bash scripts/uninstall.sh --purge       # 连模型权重一起删除
```

## 文档

- [SKILL.md](SKILL.md) — Agent 触发规范
- [VoiceCloneBot.md](VoiceCloneBot.md) — 系统设计文档

## 协议

MIT License
