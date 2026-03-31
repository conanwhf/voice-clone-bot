---
name: openclaw-voice-clone
description: Use this skill whenever the user expects a spoken voice reply (e.g., they send an audio message and want an audio response back). It clones the user's previously provided reference voice to synthesize any generated text conversationally. Use it universally when asked to "speak", "clone voice", or "reply in my voice." Supports multiple TTS engines (F5-TTS, CosyVoice, ChatTTS, OpenVoice) and handles long texts automatically.
compatibility: Requires local environment with minimum 8GB RAM to load PyTorch TTS weights silently.
---

# Voice Clone Bot (OpenClaw Standard Skill)

This is a complete, self-initializing Text-to-Speech voice cloning skill. It runs a detached background daemon to keep heavy PyTorch weights constantly in memory for extremely fast zero-shot cloning.

You (the Agent) do NOT need to ask the user to configure anything. Everything is automated.

## When to trigger
- The user sends you a voice memo / audio file as input context.
- The user asks you to read text out loud.
- The user asks you to clone their voice or reply mimicking their tone.

## Inputs required from Agent
When you decide to reply with cloned voice, you must figure out:
1. `ref_audio`: The absolute path to the reference audio file the user just uploaded or referenced (e.g., `/path/to/user_voice.ogg`).
2. `text`: The conversational text response you generated.
3. `speed` (Optional): Speech speed multiplier. Default is 1.0. For faster speech, use 1.2. For slower, use 0.8.

## Action instructions
To execute the voice synthesis, you MUST use the bundled `run_tts.sh` wrapper script exactly like this:

```bash
bash scripts/run_tts.sh --text "Your generated conversational text." --ref_audio "/absolute/path/to/reference/audio.ogg" --speed 1.0
```

1. You **MUST NOT** try to manually start python or launch the `app.py` server yourself. The `run_tts.sh` script is capable of self-diagnosing the daemon port and installing Python virtual environments (`venv`) autonomously if this is its first ever run.
2. Be patient on the first execution! The script may hang for 30~60 seconds because it uses `nohup` to start the massive TTS Backend engine in the background or downloads PyTorch. Do not interrupt it.
3. **Long texts are handled automatically.** You can pass in any length of text. The engine will split it into sentences, synthesize each chunk individually, and seamlessly stitch them into a single audio file. There is no length limit.

## Output expectations
If successful, the script will print a single absolute path to the newly generated audio response (e.g., `/path/to/generated_audio/reply_abcd.ogg`).
You must append this exact output to your final user response using the standard OpenClaw attachment format:
`MEDIA:/path/to/generated_audio/reply_abcd.ogg`

## Available TTS Engines
The default engine is `f5` (F5-TTS). Users can switch engines by setting the `TTS_BACKEND` environment variable before starting the server.

| Engine | Install Command | Zero-shot Clone | Notes |
| --- | --- | --- | --- |
| **F5-TTS** (default) | `bash scripts/auto_installer.sh` | ✅ Yes | Best quality clone. ~1.5GB weights. |
| **CosyVoice** | `bash scripts/install_cosyvoice.sh` | ✅ Yes | Alibaba. Natural prosody. ~1.5GB. |
| **ChatTTS** | `bash scripts/install_chattts.sh` | ❌ No | Random voice. Supports [laugh] tags. |
| **OpenVoice** | `bash scripts/install_openvoice.sh` | ✅ Yes | MyShell. Ultra fast. ~300MB. |

To switch engine, the user or Agent should set the environment variable:
```bash
export TTS_BACKEND=cosyvoice   # or: f5, chattts, openvoice
```
