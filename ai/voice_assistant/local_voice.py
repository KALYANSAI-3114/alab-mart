import base64
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WHISPER_EXE = ROOT / "whisper.cpp" / "build" / "bin" / "Release" / "whisper-cli.exe"
DEFAULT_WHISPER_MODEL = ROOT / "whisper.cpp" / "ggml-base.en.bin"
DEFAULT_PIPER_MODEL = ROOT / "voices" / "en_US-lessac-medium.onnx"


def configured_path(env_name: str, default: Path) -> Path:
    return Path(os.environ.get(env_name, str(default))).resolve()


def transcribe_wav_bytes(wav_bytes: bytes) -> str:
    whisper_exe = configured_path("WHISPER_CPP_EXE", DEFAULT_WHISPER_EXE)
    whisper_model = configured_path("WHISPER_CPP_MODEL", DEFAULT_WHISPER_MODEL)

    if not whisper_exe.exists():
        raise RuntimeError(f"Whisper executable not found: {whisper_exe}")
    if not whisper_model.exists():
        raise RuntimeError(f"Whisper model not found: {whisper_model}")

    with tempfile.TemporaryDirectory(prefix="alab_voice_") as temp_dir:
        temp_path = Path(temp_dir)
        input_wav = temp_path / "input.wav"
        output_base = temp_path / "transcript"
        output_txt = temp_path / "transcript.txt"
        input_wav.write_bytes(wav_bytes)

        command = [
            str(whisper_exe),
            "-m",
            str(whisper_model),
            "-f",
            str(input_wav),
            "-nt",
            "-otxt",
            "-of",
            str(output_base),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=90)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Whisper transcription failed.")
        if output_txt.exists():
            return output_txt.read_text(encoding="utf-8", errors="ignore").strip()
        return result.stdout.strip()


def synthesize_reply_base64(text: str) -> Optional[str]:
    piper_exe = os.environ.get("PIPER_EXE")
    if not piper_exe:
        return None

    piper_path = Path(piper_exe).resolve()
    piper_model = configured_path("PIPER_MODEL", DEFAULT_PIPER_MODEL)
    if not piper_path.exists() or not piper_model.exists():
        return None

    with tempfile.TemporaryDirectory(prefix="alab_tts_") as temp_dir:
        output_wav = Path(temp_dir) / "reply.wav"
        command = [str(piper_path), "--model", str(piper_model), "--output_file", str(output_wav)]
        result = subprocess.run(command, input=text, capture_output=True, text=True, timeout=60)
        if result.returncode != 0 or not output_wav.exists():
            return None
        return base64.b64encode(output_wav.read_bytes()).decode("ascii")
