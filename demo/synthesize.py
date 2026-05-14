"""Render all narration blocks with F5-TTS (24 kHz, voice-cloned).

Run from project root:
    python demo/synthesize.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from f5_tts.api import F5TTS

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = json.loads((ROOT / "demo" / "script.json").read_text())
OUT = ROOT / "demo" / "build"
OUT.mkdir(parents=True, exist_ok=True)

# Pick a reference voice. Default = F5-TTS bundled "mother nature" (warm female narrator, 5.3s).
# For a male narrator, set DEMO_REF_AUDIO env var to a path with matching DEMO_REF_TEXT.
import f5_tts as _f5
F5_PKG = Path(_f5.__path__[0])
DEFAULT_REF_WAV  = F5_PKG / "infer" / "examples" / "basic" / "basic_ref_en.wav"
DEFAULT_REF_TEXT = "Some call me nature, others call me mother nature."

REF_WAV  = Path(os.environ.get("DEMO_REF_AUDIO",  str(DEFAULT_REF_WAV)))
REF_TEXT = os.environ.get("DEMO_REF_TEXT", DEFAULT_REF_TEXT)
device   = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")

print(f"[F5-TTS] device={device}")
print(f"[F5-TTS] reference: {REF_WAV.name}")
print(f"[F5-TTS] ref_text:  {REF_TEXT!r}")

tts = F5TTS(model="F5TTS_v1_Base", device=device)

for i, block in enumerate(SCRIPT["scenes"]):
    text = " ".join(block["lines"])
    raw  = OUT / f"block_{i:02d}_raw.wav"
    wav  = OUT / f"block_{i:02d}.wav"
    print(f"[{i+1}/{len(SCRIPT['scenes'])}] {block['key']:8s} ({len(text):4d} chars) …")
    audio, sr, _ = tts.infer(
        ref_file=str(REF_WAV),
        ref_text=REF_TEXT,
        gen_text=text,
        speed=1.0,
        nfe_step=32,
        cfg_strength=2.0,
        sway_sampling_coef=-1.0,
        cross_fade_duration=0.15,
        remove_silence=False,
        seed=42 + i,
    )
    audio = np.asarray(audio, dtype=np.float32)
    # Normalize gently to -1 dBFS peak (matches studio voice levels)
    peak = float(np.max(np.abs(audio))) or 1.0
    audio = audio * (10 ** (-1 / 20.0)) / peak
    sf.write(raw, audio, sr, subtype="PCM_16")
    # Resample to 48 kHz stereo for ffmpeg concat
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(raw), "-ar", "48000", "-ac", "2", str(wav)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
    )
    print(f"      → {wav.name}  {sr} Hz → 48 kHz stereo")

print("\nAll blocks rendered.")
