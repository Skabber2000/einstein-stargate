"""Render Ukrainian narration with the BrUk / robinhad `ukrainian-tts` package.

Runs on nucbox (Windows MSYS, Python 3.13, PyTorch 2.7 CPU).
Replaces the earlier Silero v3_ua draft; ukrainian-tts is a VITS model
trained specifically on Ukrainian and handles loan words / technical
vocabulary substantially better.

Notes:
  - Voice: `dmytro` (male, deeper / more documentary than mykyta).
  - Stress mode: `Stress.Model` — ML stress predictor for unknown words.
  - Technical proper nouns (Шварцшильд, Фламма, Ейнштейн, Юпітер, etc.)
    are pre-marked with '+' before the stressed vowel so the model
    doesn't have to guess. The package treats '+' as an explicit stress
    marker and strips it before synthesis.

Install on nucbox first (one time):
    pip install ukrainian-tts soundfile soxr

Run:
    python synthesize_uk.py        # generates block_uk_00.wav … block_uk_07.wav
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

# Force UTF-8 stdout so progress lines work on Windows cp1252.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from ukrainian_tts.tts import TTS, Voices, Stress

VOICE = Voices.Dmytro.value
STRESS_MODE = Stress.Model.value
SR = 48000

# Pre-marked '+' = stressed vowel (per ukrainian-tts convention).
BLOCKS_UK: list[str] = [
    # 0 — intro
    "Простір-час — це не сцена. Це актор. "
    "Маса та енергія тиснуть на нього. "
    "Тензор Ейншт+ейна вимірює, наскільки глибоко вони тиснуть.",

    # 1 — Moon
    "Місяць. Його радіус Шварцш+ильда — лише нуль кома одинадцять міліметра. "
    "Менше за піщинку. "
    "Кривина, яку ви бачите, — це те, що насправді відчув би мураха на поверхні Місяця.",

    # 2 — Earth
    "Земля. Радіус Шварцш+ильда — вісім кома дев'яносто п'ять міліметра. "
    "Уся планета мала б стиснутися до такого розміру, щоб стати чорною дірою. "
    "Ми обертаємось навколо Сонця, ми відчуваємо гравітацію — "
    "але геометричне викривлення тут лише одна частка з мільярда.",

    # 3 — Sun
    "Сонце. Радіус Шварцш+ильда — два кома дев'яносто п'ять кілометра. "
    "Фізичний радіус — майже сімсот тисяч кілометрів. "
    "Лійка виглядає глибокою тільки тому, що ми малюємо в одиницях радіуса Шварцш+ильда. "
    "Насправді простір-час навколо Сонця досі плоский на дев'яносто дев'ять кома дев'ять тисяч дев'ятсот дев'яносто шість відсотка. "
    "Але цього достатньо, щоб відхилити світло зір на одну кому сімдесят п'ять кутової секунди. "
    "Саме це вимірювання підтвердило загальну теорію відносності тисяча дев'ятсот дев'ятнадцятого року.",

    # 4 — R136a1
    "Ер сто тридцять шість а один. Найважча відома одиночна зоря. "
    "Близько двохсот мас Сонця, у туман+ності Тарант+ул. "
    "І все одно гравітаційне викривлення на її поверхні — лише вісім, помножене на десять у мінус п'ятому степені. "
    "Зорі не можуть зламати простір-час самою лише масою. Тільки кол+апсом.",

    # 5 — Black hole
    "Чорна діра десять мас Сонця. Тепер радіус дорівнює радіусу Шварцш+ильда. "
    "Уся параболо+їда Фл+амма відкрита. "
    "Усередині горизонту час і радіус міняються ролями. "
    "Ось так виглядає простір-час, продавлений за межу. "
    "Але в неї лише одна горлянка. Усе, що падає всередину, назовні не повертається.",

    # 6 — Star-Gate
    "Зоряна Брама. Дві геометрії Шварцш+ильда, склеєні горлом — міст Ейншт+ейна-Р+озена. "
    "Дві горлянки, один тунель. "
    "Щоб утримати горло відкритим всупереч його прагненню колапсувати, "
    "потрібна екзотична матерія — матерія з від'ємною щільністю енергії.",

    # 7 — energy
    "Скільки енергії це коштує? "
    "Рівняння Ейншт+ейна дають класичну оцінку: "
    "швидкість світла в четвертому степені, помножена на радіус горла, поділена на гравітаційну сталу. "
    "Для брами шириною два метри, достатньої для людини, — "
    "це два кома чотири, помножене на десять у сорок четвертому степені джоулів. "
    "Щоб уявити це число: приблизно десять у тридцять першому степені Х+іросім. "
    "Одиниця з тридцяти однома нулями. "
    "Це дорівнює всій ядерній зброї Землі, підірваній одночасно, шістнадцять септильйонів разів поспіль. "
    "Чотириста секстильйонів років усієї світової енергетики. "
    "Або, найпряміше: півтори маси Юп+ітера, перетворені на чисту енергію. "
    "Квантові нерівності Ф+орда-Ром+ана дозволяють екзотичній енергії лише величину порядку "
    "редукованої сталої Пл+анка, помноженої на швидкість світла, поділеної на радіус горла. "
    "Для тієї ж брами — менше за мільйонну частку мільярдної частки джоуля. "
    "Класична вимога перевищує квантовий ліміт на сімдесят порядків. "
    "Поки фізика не закриє цю прірву, Зоряна Брама лишається наукової фантастикою.",
]


def resample(audio: np.ndarray, sr_from: int, sr_to: int) -> np.ndarray:
    if sr_from == sr_to:
        return audio.astype(np.float32, copy=False)
    try:
        import soxr
        return soxr.resample(audio, sr_from, sr_to).astype(np.float32)
    except ImportError:
        from scipy.signal import resample_poly
        from math import gcd
        g = gcd(sr_from, sr_to)
        return resample_poly(audio, sr_to // g, sr_from // g).astype(np.float32)


def synthesize_block(tts: TTS, text: str) -> np.ndarray:
    buf = io.BytesIO()
    _, normalised = tts.tts(text, VOICE, STRESS_MODE, buf)
    buf.seek(0)
    audio, sr_native = sf.read(buf, dtype="float32")
    audio = resample(audio, sr_native, SR)
    return audio


def main() -> None:
    # Write to demo/build/ where the rest of the pipeline expects the WAVs.
    out_dir = Path(__file__).resolve().parent / "build"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[ukrainian-tts] loading model + voice={VOICE}, stress={STRESS_MODE}")
    tts = TTS(device="cpu")
    for i, text in enumerate(BLOCKS_UK):
        path = out_dir / f"block_uk_{i:02d}.wav"
        if path.exists() and path.stat().st_size > 1024:
            print(f"[{i+1}/{len(BLOCKS_UK)}] {path.name} exists, skip")
            continue
        print(f"[{i+1}/{len(BLOCKS_UK)}] synthesising {len(text)} chars ...")
        audio = synthesize_block(tts, text)
        peak = float(np.max(np.abs(audio))) or 1.0
        audio = audio * (10 ** (-1 / 20.0)) / peak
        sf.write(path, audio, SR, subtype="PCM_16")
        print(f"      -> {path.name}  {len(audio) / SR:.2f}s")
    print("\nAll Ukrainian blocks rendered (ukrainian-tts / dmytro).")


if __name__ == "__main__":
    main()
