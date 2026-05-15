"""Render Ukrainian narration with Silero TTS.

Designed to run on nucbox (Windows MSYS, Python 3.13, PyTorch 2.7 CPU).
Outputs 8 WAV blocks (block_uk_00.wav … block_uk_07.wav) at 48 kHz mono
that the assemble pipeline can drop in as a replacement for the English
F5-TTS narration.

Silero TTS notes:
  - Model: snakers4/silero-models, language='ua', package='v3_ua'
  - Speaker: 'mykyta' (male, the only voice in v3_ua)
  - Each apply_tts call is limited to ~140 characters → we split by
    sentence and concatenate with a short pause between cues.
  - Numbers, scientific notation and Latin symbols must be spelled out
    in Cyrillic for the TTS to read them correctly. The script text below
    has already been normalised for this.

Run on nucbox:
    python synthesize_uk.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

# Windows default console is cp1252; force UTF-8 so we can log freely.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

torch.set_num_threads(16)  # Strix Halo: 16 Zen5 cores
device = torch.device("cpu")

# Cleaned Ukrainian narration. Symbols and digits spelled in Cyrillic so
# Silero pronounces them naturally (no SSML interpretation).
BLOCKS_UK: list[str] = [
    # 0 — intro
    "Простір-час — це не сцена. Це актор. "
    "Маса та енергія тиснуть на нього. "
    "Тензор Ейнштейна вимірює, наскільки глибоко вони тиснуть.",

    # 1 — Moon
    "Місяць. Його радіус Шварцшильда — лише нуль кома одинадцять міліметра. "
    "Менше за піщинку. "
    "Кривина, яку ви бачите, — це те, що насправді відчув би мураха на поверхні Місяця.",

    # 2 — Earth
    "Земля. Радіус Шварцшильда — вісім кома дев'яносто п'ять міліметра. "
    "Уся планета мала б стиснутися до такого розміру, щоб стати чорною дірою. "
    "Ми обертаємось навколо Сонця, ми відчуваємо гравітацію — "
    "але геометричне викривлення тут лише одна частка з мільярда.",

    # 3 — Sun
    "Сонце. Радіус Шварцшильда — два кома дев'яносто п'ять кілометра. "
    "Фізичний радіус — майже сімсот тисяч кілометрів. "
    "Лійка виглядає глибокою тільки тому, що ми малюємо в одиницях радіуса Шварцшильда. "
    "Насправді простір-час навколо Сонця досі плоский на дев'яносто дев'ять кома дев'ять тисяч дев'ятсот дев'яносто шість відсотка. "
    "Але цього достатньо, щоб відхилити світло зір на одну кому сімдесят п'ять кутової секунди. "
    "Саме це вимірювання підтвердило загальну теорію відносності тисяча дев'ятсот дев'ятнадцятого року.",

    # 4 — R136a1
    "Ер сто тридцять шість а один. Найважча відома одиночна зоря. "
    "Близько двохсот мас Сонця, у туманності Тарантул. "
    "І все одно гравітаційне викривлення на її поверхні — лише вісім, помножене на десять у мінус п'ятому степені. "
    "Зорі не можуть зламати простір-час самою лише масою. Тільки колапсом.",

    # 5 — Black hole
    "Чорна діра десять мас Сонця. Тепер радіус дорівнює радіусу Шварцшильда. "
    "Уся параболоїда Фламма відкрита. "
    "Усередині горизонту час і радіус міняються ролями. "
    "Ось так виглядає простір-час, продавлений за межу. "
    "Але в неї лише одна горлянка. Усе, що падає всередину, назовні не повертається.",

    # 6 — Star-Gate
    "Зоряна Брама. Дві геометрії Шварцшильда, склеєні горлом — міст Ейнштейна-Розена. "
    "Дві горлянки, один тунель. "
    "Щоб утримати горло відкритим всупереч його прагненню колапсувати, "
    "потрібна екзотична матерія — матерія з від'ємною щільністю енергії.",

    # 7 — energy
    "Скільки енергії це коштує? "
    "Рівняння Ейнштейна дають класичну оцінку: "
    "швидкість світла в четвертому степені, помножена на радіус горла, поділена на гравітаційну сталу. "
    "Для брами шириною два метри, достатньої для людини, — "
    "це два кома чотири, помножене на десять у сорок четвертому степені джоулів. "
    "Щоб уявити це число: приблизно десять у тридцять першому степені Хіросім. "
    "Одиниця з тридцяти однома нулями. "
    "Це дорівнює всій ядерній зброї Землі, підірваній одночасно, шістнадцять септильйонів разів поспіль. "
    "Чотириста секстильйонів років усієї світової енергетики. "
    "Або, найпряміше: півтори маси Юпітера, перетворені на чисту енергію. "
    "Квантові нерівності Форда-Романа дозволяють екзотичній енергії лише величину порядку "
    "редукованої сталої Планка, помноженої на швидкість світла, поділеної на радіус горла. "
    "Для тієї ж брами — менше за мільйонну частку мільярдної частки джоуля. "
    "Класична вимога перевищує квантовий ліміт на сімдесят порядків. "
    "Поки фізика не закриє цю прірву, Зоряна Брама лишається наукової фантастикою.",
]

SR = 48000
SPEAKER = "mykyta"
PAUSE_BETWEEN_SENTENCES = 0.25  # seconds


def load_model():
    print("[silero] loading v3_ua/mykyta ...")
    model, _ = torch.hub.load(
        repo_or_dir="snakers4/silero-models",
        model="silero_tts",
        language="ua",
        speaker="v3_ua",
        trust_repo=True,
    )
    model.to(device)
    return model


def split_sentences(text: str) -> list[str]:
    """Split paragraph into sentence-sized cues that Silero can chew."""
    pieces = re.split(r"(?<=[\.\!\?])\s+", text.strip())
    out: list[str] = []
    for p in pieces:
        p = p.strip()
        if not p:
            continue
        # Keep each chunk <= 130 chars; long sentences break at ' — ' or commas
        while len(p) > 130:
            cut = max(p.rfind(" — ", 0, 130), p.rfind(", ", 0, 130))
            if cut < 50:
                cut = 130
            out.append(p[:cut].rstrip(", —"))
            p = p[cut:].lstrip(" —,")
        out.append(p)
    return out


def synthesize_block(model, text: str) -> np.ndarray:
    sentences = split_sentences(text)
    chunks: list[np.ndarray] = []
    silence = np.zeros(int(SR * PAUSE_BETWEEN_SENTENCES), dtype=np.float32)
    for sent in sentences:
        # apply_tts returns a torch.Tensor mono waveform at SR
        wav = model.apply_tts(
            text=sent,
            speaker=SPEAKER,
            sample_rate=SR,
            put_accent=True,
            put_yo=True,
        )
        chunks.append(wav.cpu().numpy().astype(np.float32))
        chunks.append(silence)
    # Drop trailing silence
    if chunks and chunks[-1] is silence:
        chunks.pop()
    return np.concatenate(chunks)


def main() -> None:
    out_dir = Path(__file__).resolve().parent
    out_dir.mkdir(exist_ok=True)
    model = load_model()

    for i, text in enumerate(BLOCKS_UK):
        path = out_dir / f"block_uk_{i:02d}.wav"
        if path.exists() and path.stat().st_size > 1024:
            print(f"[{i+1}/{len(BLOCKS_UK)}] {path.name} already exists, skip")
            continue
        print(f"[{i+1}/{len(BLOCKS_UK)}] {len(text):4d} chars ...")
        audio = synthesize_block(model, text)
        peak = float(np.max(np.abs(audio))) or 1.0
        audio = audio * (10 ** (-1 / 20.0)) / peak
        sf.write(path, audio, SR, subtype="PCM_16")
        print(f"      -> {path.name}  {len(audio) / SR:.2f}s")
    print("\nAll Ukrainian blocks rendered.")


if __name__ == "__main__":
    main()
