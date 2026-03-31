import argparse
import sys
import os
import requests

def main():
    parser = argparse.ArgumentParser(description="OpenClaw Voice Clone TTS Client")
    parser.add_argument("--text", type=str, required=True, help="需要被语音克隆引擎读出来的文字内容")
    parser.add_argument("--ref_audio", type=str, default="", help="用户指定的参考录音本地绝对路径")
    
    args = parser.parse_args()
    
    if not args.text.strip():
        print("Error: 文本为空！无法生成音频。", file=sys.stderr)
        sys.exit(1)

    # 发送请求至本地常驻推理微服务 
    TARGET_URL = "http://127.0.0.1:8000/clone"
    payload = {
        "text": args.text,
        "ref_audio_path": args.ref_audio if args.ref_audio else None
    }
    
    try:
        resp = requests.post(TARGET_URL, json=payload, timeout=300) 
        # 我们给推理留 300 秒的时间，以防止长文本阻塞
        
        resp.raise_for_status()
        data = resp.json()
        
        output_file = data.get("output_audio_path")
        if output_file and os.path.exists(output_file):
            print(f"DEBUG: 成功收到模型发还的音频地址: {output_file}", file=sys.stderr)
            # SKILL.md 要求：脚本标准输出只有一行即生成的音频绝对路径
            print(output_file)
            sys.exit(0)
        else:
            print(f"Error: 成功走完了接口，但返回的本地文件 {output_file} 无效或丢失。", file=sys.stderr)
            sys.exit(1)
            
    except Exception as e:
        print(f"Error: 请求守护端崩溃或不可达。你刚才是不是忘了启动 server/app.py？原因：{e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
