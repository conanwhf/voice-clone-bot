import os
import re
import time
import subprocess
from abc import ABC, abstractmethod
import soundfile as sf
import numpy as np

# ==========================================
# 0. 长文本断句切片工具 (Sentence Chunker)
# ==========================================

# 单次推理的安全字符上限。超过此值的文本将被自动切片。
# F5-TTS 官方建议单次不超过约 100-200 字（中文）以获得最佳质量。
MAX_CHUNK_CHARS = 150

def split_text_to_chunks(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list:
    """
    将长文本按照自然语言的断句位置切片为数组。
    切片优先级：句号/叹号/问号 > 分号/冒号 > 逗号 > 空格强制截断。
    每个切片的长度不超过 max_chars。
    """
    if len(text) <= max_chars:
        return [text]

    # 第一步：按句末标点分割
    # 匹配中英文句号、叹号、问号、分号
    sentences = re.split(r'(?<=[。！？.!?；;])', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        # 如果当前累积 + 新句子仍能容纳，则拼入
        if len(current_chunk) + len(sentence) <= max_chars:
            current_chunk += sentence
        else:
            # 先把已累积的存档
            if current_chunk:
                chunks.append(current_chunk)
            # 如果单个句子本身就超长，对它进行二次切割（按逗号）
            if len(sentence) > max_chars:
                sub_parts = re.split(r'(?<=[，,、])', sentence)
                sub_chunk = ""
                for part in sub_parts:
                    if len(sub_chunk) + len(part) <= max_chars:
                        sub_chunk += part
                    else:
                        if sub_chunk:
                            chunks.append(sub_chunk)
                        # 如果逗号切片后仍然超长，强行按字数截断
                        while len(part) > max_chars:
                            chunks.append(part[:max_chars])
                            part = part[max_chars:]
                        sub_chunk = part
                if sub_chunk:
                    current_chunk = sub_chunk
                else:
                    current_chunk = ""
            else:
                current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


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
    def synthesize_chunk(self, text: str, ref_audio: str, speed: float = 1.0):
        """
        单次推理一个短句。
        返回: (np.ndarray audio_segment, int sample_rate)
        """
        pass

    def synthesize(self, text: str, ref_audio: str, output_path: str, speed: float = 1.0) -> bool:
        """
        完整合成：自动对长文本分片、逐一推理、拼接后转码输出。
        所有子类共享此逻辑，子类只需实现 synthesize_chunk。
        """
        chunks = split_text_to_chunks(text)
        print(f"[BaseTTSEngine] 文本共 {len(text)} 字，切分为 {len(chunks)} 个片段")

        all_segments = []
        sample_rate = 24000  # 大多数模型默认 24kHz

        for i, chunk in enumerate(chunks):
            print(f"  [{i+1}/{len(chunks)}] 推理中: '{chunk[:40]}...'")
            audio_seg, sr = self.synthesize_chunk(chunk, ref_audio, speed)
            sample_rate = sr
            all_segments.append(audio_seg)

        # 拼接所有片段
        final_wave = np.concatenate(all_segments) if all_segments else np.array([])

        # 写入中间 WAV
        tmp_wav = output_path.replace(".ogg", ".wav")
        sf.write(tmp_wav, final_wave, sample_rate)

        # 转码为 ogg/opus (Telegram 等平台友好格式)
        print(f"[BaseTTSEngine] 正在用 ffmpeg 压制为 {output_path}...")
        subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_wav, "-c:a", "libopus", "-b:a", "48k", output_path],
            capture_output=True
        )

        if os.path.exists(tmp_wav):
            os.remove(tmp_wav)

        return os.path.exists(output_path)


# ==========================================
# 2. F5-TTS 引擎
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
        config_path = str(files("f5_tts").joinpath(f"configs/{model_name}.yaml"))
        model_cfg = OmegaConf.load(config_path)
        model_cls = get_class(f"f5_tts.model.{model_cfg.model.backbone}")
        model_arc = model_cfg.model.arch

        # 3. Checkpoint 自动下载至被拦截的 HF_HOME
        ckpt_step = 1200000
        ckpt_file = str(cached_path(f"hf://SWivid/F5-TTS/{model_name}/model_{ckpt_step}.safetensors"))

        print(f"[F5TTSEngine] 正在将 {model_name} 的 1.5GB DiT 权重挂载至 {self.device}...")
        self.model = load_model(
            model_cls, model_arc, ckpt_file,
            mel_spec_type="vocos", vocab_file="", device=self.device
        )
        print("[F5TTSEngine] 成功挂载权重！")

        # 缓存预处理后的参考音频，避免每个 chunk 反复提取
        self._cached_ref = {}

    def _get_ref(self, ref_audio: str):
        """缓存参考音频的预处理结果"""
        if ref_audio not in self._cached_ref:
            from f5_tts.infer.utils_infer import preprocess_ref_audio_text
            ref_audio_proc, ref_text_proc = preprocess_ref_audio_text(ref_audio, "")
            self._cached_ref[ref_audio] = (ref_audio_proc, ref_text_proc)
        return self._cached_ref[ref_audio]

    def synthesize_chunk(self, text: str, ref_audio: str, speed: float = 1.0):
        from f5_tts.infer.utils_infer import infer_process

        ref_audio_proc, ref_text_proc = self._get_ref(ref_audio)

        audio_segment, final_sample_rate, _ = infer_process(
            ref_audio_proc, ref_text_proc, text,
            self.model, self.vocoder,
            mel_spec_type="vocos",
            target_rms=0.1,
            cross_fade_duration=0.15,
            nfe_step=32,
            cfg_strength=2.0,
            sway_sampling_coef=-1.0,
            speed=speed,
            fix_duration=None,
            device=self.device
        )
        return audio_segment, final_sample_rate


# ==========================================
# 3. CosyVoice 引擎 (阿里通义实验室)
# ==========================================
class CosyVoiceEngine(BaseTTSEngine):
    """
    依赖：需要先用 scripts/install_cosyvoice.sh 安装。
    核心库: cosyvoice (从 github 克隆并 pip install -e .)
    模型: CosyVoice2-0.5B (~1.5GB)
    """
    def load(self):
        print(f"[CosyVoiceEngine] 分配计算单元: {self.device}")

        try:
            from cosyvoice.cli.cosyvoice import CosyVoice2
        except ImportError:
            raise ImportError(
                "[CosyVoiceEngine] 缺少 cosyvoice 库！\n"
                "请先运行: bash scripts/install_cosyvoice.sh\n"
                "该脚本会自动克隆源码并安装依赖。"
            )

        model_path = os.path.join(self.model_dir, "CosyVoice2-0.5B")
        if not os.path.exists(model_path):
            # 自动从 HuggingFace/ModelScope 下载模型
            print(f"[CosyVoiceEngine] 模型目录不存在，尝试从远端拉取至 {model_path}...")
            model_path = "iic/CosyVoice2-0.5B"  # 会自动下载到 MODELSCOPE_CACHE

        print(f"[CosyVoiceEngine] 正在加载 CosyVoice2-0.5B...")
        self.model = CosyVoice2(model_path, load_jit=False, load_onnx=False, load_trt=False)
        print("[CosyVoiceEngine] 模型加载完毕！")

    def synthesize_chunk(self, text: str, ref_audio: str, speed: float = 1.0):
        from cosyvoice.utils.file_utils import load_wav
        import torch

        prompt_speech_16k = load_wav(ref_audio, 16000)
        # CosyVoice 的零样本推理需要参考音频的文字转录
        # 此处留空让它内部处理（或者后续集成 whisper 转录）
        prompt_text = ""

        all_audio = []
        for result in self.model.inference_zero_shot(prompt_text, text, prompt_speech_16k, stream=False):
            audio_tensor = result['tts_speech']
            if isinstance(audio_tensor, torch.Tensor):
                audio_tensor = audio_tensor.cpu().numpy()
            if audio_tensor.ndim > 1:
                audio_tensor = audio_tensor.squeeze()
            all_audio.append(audio_tensor)

        audio = np.concatenate(all_audio) if all_audio else np.array([])
        return audio, 24000


# ==========================================
# 4. ChatTTS 引擎 (2noise)
# ==========================================
class ChatTTSEngine(BaseTTSEngine):
    """
    依赖：需要先用 scripts/install_chattts.sh 安装。
    核心库: ChatTTS (从 github 克隆)
    特性: 极强的对话韵律控制，支持 [laugh] [uv_break] 等标记。
    注意: ChatTTS 不支持零样本声音克隆，它使用随机种子生成不同音色。
          ref_audio 参数在此引擎下不生效。
    """
    def load(self):
        print(f"[ChatTTSEngine] 分配计算单元: {self.device}")

        try:
            import ChatTTS
        except ImportError:
            raise ImportError(
                "[ChatTTSEngine] 缺少 ChatTTS 库！\n"
                "请先运行: bash scripts/install_chattts.sh\n"
                "该脚本会自动克隆源码并安装依赖。"
            )

        self.model = ChatTTS.Chat()
        self.model.load(compile=False)  # compile=True 需要较新的 torch
        print("[ChatTTSEngine] 模型加载完毕！")

    def synthesize_chunk(self, text: str, ref_audio: str, speed: float = 1.0):
        import torch

        wavs = self.model.infer([text])
        audio = wavs[0]
        if isinstance(audio, torch.Tensor):
            audio = audio.cpu().numpy()
        if audio.ndim > 1:
            audio = audio.squeeze()
        return audio, 24000


# ==========================================
# 5. OpenVoice V2 引擎 (MyShell)
# ==========================================
class OpenVoiceEngine(BaseTTSEngine):
    """
    依赖：需要先用 scripts/install_openvoice.sh 安装。
    核心库: openvoice (从 github 克隆并 pip install -e .)
    模型: checkpoints_v2 (~300MB)
    特性: 体积极小速度极快，但克隆拟真度低于 F5/CosyVoice。
          工作原理是 "基础TTS生成 + 音色转换" 两步走。
    """
    def load(self):
        print(f"[OpenVoiceEngine] 分配计算单元: {self.device}")

        try:
            from openvoice import se_extractor
            from openvoice.api import ToneColorConverter, BaseSpeakerTTS
        except ImportError:
            raise ImportError(
                "[OpenVoiceEngine] 缺少 openvoice 库！\n"
                "请先运行: bash scripts/install_openvoice.sh\n"
                "该脚本会自动克隆源码、下载权重并安装。"
            )

        ckpt_dir = os.path.join(self.model_dir, "OpenVoice", "checkpoints_v2")
        if not os.path.exists(ckpt_dir):
            raise FileNotFoundError(
                f"[OpenVoiceEngine] 未在 {ckpt_dir} 找到权重！\n"
                "请先运行: bash scripts/install_openvoice.sh"
            )

        converter_cfg = os.path.join(ckpt_dir, "converter", "config.json")
        converter_ckpt = os.path.join(ckpt_dir, "converter", "checkpoint.pth")

        self.converter = ToneColorConverter(converter_cfg, device=self.device)
        self.converter.load_ckpt(converter_ckpt)
        self.se_extractor = se_extractor
        self._ckpt_dir = ckpt_dir
        self.model = "loaded"
        print("[OpenVoiceEngine] 模型加载完毕！")

    def synthesize_chunk(self, text: str, ref_audio: str, speed: float = 1.0):
        from openvoice.api import BaseSpeakerTTS

        # 1. 提取目标音色
        target_se, _ = self.se_extractor.get_se(ref_audio, self.converter, vad=False)

        # 2. 使用基础 TTS 生成默认音色发言
        base_cfg = os.path.join(self._ckpt_dir, "base_speakers", "ses", "default.pth")
        source_se = os.path.join(self._ckpt_dir, "base_speakers", "EN", "default_se.pth")

        import tempfile, torch
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        # 3. 转换音色
        self.converter.convert(
            audio_src_path=tmp_path,
            src_se=torch.load(source_se),
            tgt_se=target_se,
            output_path=tmp_path + "_out.wav"
        )

        audio, sr = sf.read(tmp_path + "_out.wav")
        os.unlink(tmp_path)
        if os.path.exists(tmp_path + "_out.wav"):
            os.unlink(tmp_path + "_out.wav")

        return audio, sr


# ==========================================
# 6. 引擎工厂中枢
# ==========================================
GLOBAL_MODEL_DIR = os.path.expanduser("~/.openclaw/models/voice-clone")
_active_engine: BaseTTSEngine = None

# 注册引擎名称到类的映射
ENGINE_REGISTRY = {
    "f5": F5TTSEngine,
    "cosyvoice": CosyVoiceEngine,
    "chattts": ChatTTSEngine,
    "openvoice": OpenVoiceEngine,
}

def get_available_engines() -> list:
    """返回当前注册的所有引擎名称"""
    return list(ENGINE_REGISTRY.keys())

def initialize_models():
    global _active_engine
    if not os.path.exists(GLOBAL_MODEL_DIR):
        os.makedirs(GLOBAL_MODEL_DIR, exist_ok=True)

    engine_name = os.getenv("TTS_BACKEND", "f5").lower()

    if engine_name not in ENGINE_REGISTRY:
        available = ", ".join(ENGINE_REGISTRY.keys())
        raise ValueError(
            f"不支持的语音引擎: '{engine_name}'\n"
            f"可用引擎: {available}\n"
            f"请设置环境变量 TTS_BACKEND 为上述之一。"
        )

    engine_cls = ENGINE_REGISTRY[engine_name]
    print(f"[core_tts] 使用引擎: {engine_name} ({engine_cls.__name__})")
    _active_engine = engine_cls(GLOBAL_MODEL_DIR)
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
