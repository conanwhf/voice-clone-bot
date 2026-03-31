import os
import time
import subprocess
from abc import ABC, abstractmethod
import soundfile as sf
import numpy as np

# ==========================================
# 1. 引擎通用基类定义
# ==========================================
class BaseTTSEngine(ABC):
    def __init__(self, model_dir: str):
        self.model_dir = model_dir
        self.device = self._get_optimal_device()
        self.model = None
        self.vocoder = None

    def _get_optimal_device(self) -> str:
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            elif torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        return "cpu"

    @abstractmethod
    def load(self):
        """将模型重度权重从 self.model_dir 载入 self.device 显存以常驻"""
        pass

    @abstractmethod
    def synthesize(self, text: str, ref_audio: str, output_path: str, speed: float = 1.0) -> bool:
        """执行推理并输出文件。如果是长文本，应在此层做切片处理。"""
        pass

# ==========================================
# 2. 具体引擎实现：F5-TTS
# ==========================================
class F5TTSEngine(BaseTTSEngine):
    def load(self):
        print(f"[F5TTSEngine] 分配计算单元: {self.device}")
        
        from f5_tts.infer.utils_infer import load_model, load_vocoder
        from importlib.resources import files
        from omegaconf import OmegaConf
        from hydra.utils import get_class
        from cached_path import cached_path
        
        # 1. 加载 Vocoder
        print("[F5TTSEngine] 正在加载 Vocoder (Vocos)...")
        self.vocoder = load_vocoder(vocoder_name="vocos", is_local=False, local_path="", device=self.device)
        
        # 2. 准备 F5-TTS Base 模型的配置
        model_name = "F5TTS_Base"
        # 这里的配置文件存在于 f5_tts 包内部
        config_path = str(files("f5_tts").joinpath(f"configs/{model_name}.yaml"))
        model_cfg = OmegaConf.load(config_path)
        model_cls = get_class(f"f5_tts.model.{model_cfg.model.backbone}")
        model_arc = model_cfg.model.arch
        
        # 3. 指定 HuggingFace 上的 Checkpoint (它将自动下载到我们被拦截强制设定的 HF_HOME 目录中)
        ckpt_step = 1200000
        ckpt_file = str(cached_path(f"hf://SWivid/F5-TTS/{model_name}/model_{ckpt_step}.safetensors"))
        vocab_file = ""
        
        print(f"[F5TTSEngine] 正在将 {model_name} 的 1.5GB DiT 权重挂载至 {self.device} 显存...")
        self.model = load_model(
            model_cls, 
            model_arc, 
            ckpt_file, 
            mel_spec_type="vocos", 
            vocab_file=vocab_file, 
            device=self.device
        )
        print("[F5TTSEngine] 成功挂载权重至显存！")

    def synthesize(self, text: str, ref_audio: str, output_path: str, speed: float = 1.0) -> bool:
        if not self.model or getattr(self, "vocoder", None) is None:
            raise RuntimeError("Engine or Vocoder not loaded!")
            
        print(f"[F5TTSEngine] (Device: {self.device} | Speed: {speed}x) 提取音色: {ref_audio}")
        print(f"[F5TTSEngine] 正在生成文本: {text}")
        
        from f5_tts.infer.utils_infer import infer_process, preprocess_ref_audio_text
        
        # 设为空的话 F5 内部会自动调用 whisper 转录 ref_audio 获得 prompt text
        ref_text = ""
        
        # 1. 预处理提取音频与文字 (确保格式匹配)
        ref_audio_proc, ref_text_proc = preprocess_ref_audio_text(ref_audio, ref_text)
        
        # 2. 调用模型生成 (此处为原子性阻塞，直到生成)
        audio_segment, final_sample_rate, _ = infer_process(
            ref_audio_proc,
            ref_text_proc,
            text,
            self.model,
            self.vocoder,
            mel_spec_type="vocos",
            target_rms=0.1,
            cross_fade_duration=0.15,
            nfe_step=32,      # 默认步数，生成速度与质量的良好平衡
            cfg_strength=2.0,
            sway_sampling_coef=-1.0,
            speed=speed,
            fix_duration=None,
            device=self.device
        )
        
        # 3. 将矩阵保存为带波形的中间文件 (Wav)
        tmp_wav = output_path.replace(".ogg", ".wav")
        sf.write(tmp_wav, audio_segment, final_sample_rate)
        
        # 4. 为了 Telegram 体验（或者 OpenClaw 的兼容性），我们把它压制为 ogg (libopus)
        # 你可以保留原本的 wav 也可以将其转码，此处默认安全策略是调用 ffmpeg 转为极度瘦身的 ogg Voice Message
        print(f"[F5TTSEngine] 波形导出完毕，正在用 ffmpeg 压制为 {output_path}...")
        subprocess.run(["ffmpeg", "-y", "-i", tmp_wav, "-c:a", "libopus", "-b:a", "32k", output_path],
                       capture_output=True)
                       
        if os.path.exists(tmp_wav):
            os.remove(tmp_wav)
            
        print(f"[F5TTSEngine] 推理完成。落盘于: {output_path}")
        return os.path.exists(output_path)


# ==========================================
# 3. 另外可以无缝插入 QwenTTS 或 CosyVoice 引擎 (预留口)
# ==========================================
class QwenTTSEngine(BaseTTSEngine):
    def load(self):
        print(f"[QwenTTSEngine] 开始加载 Qwen3-TTS 权重...")
        self.model = "LOADED_QWEN"

    def synthesize(self, text: str, ref_audio: str, output_path: str) -> bool:
        pass


# ==========================================
# 4. 引擎工厂中枢接口
# ==========================================
GLOBAL_MODEL_DIR = os.path.expanduser("~/.openclaw/models/voice-clone")
_active_engine: BaseTTSEngine = None

def initialize_models():
    global _active_engine
    if not os.path.exists(GLOBAL_MODEL_DIR):
        raise FileNotFoundError(f"[!] 没有找到全局模型库 {GLOBAL_MODEL_DIR}，请先执行根目录的 install.sh")
    
    engine_name = os.getenv("TTS_BACKEND", "f5").lower()
    
    if engine_name == "f5":
        _active_engine = F5TTSEngine(GLOBAL_MODEL_DIR)
    elif engine_name == "qwen":
        _active_engine = QwenTTSEngine(GLOBAL_MODEL_DIR)
    else:
        raise ValueError(f"当前不支持请求的语音引擎: {engine_name}")
        
    _active_engine.load()

def generate_voice(text: str, ref_audio: str, output_path: str, speed: float = 1.0) -> bool:
    global _active_engine
    if _active_engine is None:
        raise RuntimeError("全局引擎未就绪")
        
    start_t = time.time()
    result = _active_engine.synthesize(text, ref_audio, output_path, speed=speed)
    end_t = time.time()
    print(f"[core_tts] 整体克隆与生成耗时: {end_t - start_t:.2f} 秒")
    return result
