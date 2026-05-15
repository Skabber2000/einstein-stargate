"""Ukrainian narration via ElevenLabs Multilingual v2.

Studio-grade prosody on Ukrainian, including correct stress on
technical loan words. The multilingual model adapts a single voice
identity across 29 languages, so we pick a documentary-male timbre
once and render the whole script.

Setup:
    1. Get a key at https://elevenlabs.io (API Keys -> Create new key).
    2. Drop it into .env at the project root:
           ELEVENLABS_API_KEY=...
    3. pip install requests python-dotenv soundfile
    4. python demo/synthesize_uk_eleven.py

Output: demo/build/block_uk_00.wav … block_uk_07.wav at 48 kHz mono PCM.

Voice presets (well-known ElevenLabs voice IDs — change at the top of
the file or via env var DEMO_VOICE_ID):
    Brian   nPczCjzI2devNBz1zQrb   warm narrator (default)
    Daniel  onwK4e9ZLuTAKqWW03F9   deep documentary UK
    George  JBFqnCBsd6RMkjVDRZzb   newscaster UK
    Adam    pNInz6obpgDQGcFmaJgB   neutral male
    Drew    29vD33N1CtxCmqQRPOHJ   conversational
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

API_KEY = os.environ.get("ELEVENLABS_API_KEY")
if not API_KEY:
    raise SystemExit("Set ELEVENLABS_API_KEY in .env (https://elevenlabs.io -> API Keys)")

VOICE_ID = os.environ.get("DEMO_VOICE_ID", "nPczCjzI2devNBz1zQrb")  # Brian
MODEL_ID = os.environ.get("DEMO_MODEL_ID", "eleven_multilingual_v2")
OUT_DIR  = ROOT / "demo" / "build"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Voice settings — slightly slower / more deliberate than default for documentary feel.
VOICE_SETTINGS = {
    "stability": 0.55,        # 0..1; higher = steadier, less variation
    "similarity_boost": 0.85, # how closely to match the source voice timbre
    "style": 0.20,            # 0..1; mild expressive variation
    "use_speaker_boost": True,
}

# Pure Cyrillic text — ElevenLabs Multilingual v2 reads numbers and proper
# nouns natively without hand-spelled-out variants. Punctuation drives pacing.
BLOCKS_UK: list[str] = [
    "Простір-час — це не сцена. Це актор. "
    "Маса та енергія тиснуть на нього. "
    "Тензор Ейнштейна вимірює, наскільки глибоко вони тиснуть.",

    "Місяць. Його радіус Шварцшильда — лише 0,11 міліметра, "
    "менше за піщинку. "
    "Кривина, яку ви бачите, — це те, що насправді відчув би мураха на поверхні Місяця.",

    "Земля. Радіус Шварцшильда — 8,95 міліметра. "
    "Уся планета мала б стиснутися до такого розміру, щоб стати чорною дірою. "
    "Ми обертаємось навколо Сонця, ми відчуваємо гравітацію, "
    "але геометричне викривлення тут — лише одна частка з мільярда.",

    "Сонце. Радіус Шварцшильда — 2,95 кілометра, "
    "фізичний радіус — майже 700 000 кілометрів. "
    "Лійка виглядає глибокою тільки тому, що ми малюємо в одиницях радіуса Шварцшильда. "
    "Насправді простір-час навколо Сонця досі плоский на 99,9996 відсотка. "
    "Але цього достатньо, щоб відхилити світло зір на 1,75 кутової секунди — "
    "саме це вимірювання підтвердило загальну теорію відносності 1919 року.",

    "R-136-a-1 — найважча відома одиночна зоря, "
    "близько 200 мас Сонця, у туманності Тарантул. "
    "І все одно гравітаційне викривлення на її поверхні — лише 8 на 10 у мінус 5 степені. "
    "Зорі не можуть зламати простір-час самою лише масою. Тільки колапсом.",

    "Чорна діра 10 мас Сонця. Тепер радіус дорівнює радіусу Шварцшильда. "
    "Уся параболоїда Фламма відкрита. "
    "Усередині горизонту час і радіус міняються ролями. "
    "Ось так виглядає простір-час, продавлений за межу. "
    "Але в неї лише одна горлянка. Усе, що падає всередину, назовні не повертається.",

    "Зоряна Брама. Дві геометрії Шварцшильда, склеєні горлом — міст Ейнштейна-Розена. "
    "Дві горлянки, один тунель. "
    "Щоб утримати горло відкритим всупереч його прагненню колапсувати, "
    "потрібна екзотична матерія — матерія з від'ємною щільністю енергії.",

    "Скільки енергії це коштує? "
    "Рівняння Ейнштейна дають класичну оцінку: "
    "швидкість світла в четвертому степені, помножена на радіус горла, поділена на гравітаційну сталу. "
    "Для брами шириною 2 метри, достатньої для людини, — "
    "це 2,4 на 10 у 44 степені джоулів. "
    "Щоб уявити це число: приблизно 10 у 31 степені Хіросім. "
    "Одиниця з 31 нулем. "
    "Це дорівнює всій ядерній зброї Землі, підірваній одночасно, 16 септильйонів разів поспіль. "
    "400 секстильйонів років усієї світової енергетики. "
    "Або, найпряміше: 1,5 маси Юпітера, перетворені на чисту енергію. "
    "Квантові нерівності Форда-Романа дозволяють екзотичній енергії лише величину порядку "
    "редукованої сталої Планка, помноженої на швидкість світла, поділеної на радіус горла. "
    "Для тієї ж брами — менше за мільйонну частку мільярдної частки джоуля. "
    "Класична вимога перевищує квантовий ліміт на 70 порядків. "
    "Поки фізика не закриє цю прірву, Зоряна Брама лишається наукової фантастикою.",
]


def synthesize_block(i: int, text: str) -> float:
    """Render one block, return its duration in seconds."""
    out_wav = OUT_DIR / f"block_uk_{i:02d}.wav"
    tmp_mp3 = OUT_DIR / f"block_uk_{i:02d}.mp3"

    # Request high-quality MP3 (44.1 kHz / 192 kbps). The endpoint streams
    # bytes; we keep it simple with a single POST.
    # 128 kbps is available on the free tier; 192 kbps requires Creator+.
    output_format = os.environ.get("DEMO_OUTPUT_FORMAT", "mp3_44100_128")
    url = (
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
        f"?output_format={output_format}"
    )
    headers = {
        "xi-api-key": API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    body = {
        "text": text,
        "model_id": MODEL_ID,
        "voice_settings": VOICE_SETTINGS,
        "language_code": "uk",
    }
    r = requests.post(url, headers=headers, json=body, timeout=180)
    if r.status_code != 200:
        raise RuntimeError(f"block {i}: HTTP {r.status_code} {r.text[:300]}")
    tmp_mp3.write_bytes(r.content)

    # Transcode MP3 → 48 kHz mono PCM WAV (matches the rest of the pipeline).
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-i", str(tmp_mp3),
         "-ar", "48000", "-ac", "1",
         str(out_wav)],
        check=True,
    )
    tmp_mp3.unlink(missing_ok=True)

    import soundfile as sf
    return sf.info(str(out_wav)).duration


def main() -> None:
    print(f"[elevenlabs] voice={VOICE_ID}  model={MODEL_ID}")
    total = 0.0
    for i, text in enumerate(BLOCKS_UK):
        dur = synthesize_block(i, text)
        total += dur
        print(f"  [{i+1}/{len(BLOCKS_UK)}] block_uk_{i:02d}.wav  {dur:5.2f}s  ({len(text)} chars)")
    print(f"All Ukrainian blocks rendered via ElevenLabs. Total narration: {total:.1f}s")


if __name__ == "__main__":
    main()
