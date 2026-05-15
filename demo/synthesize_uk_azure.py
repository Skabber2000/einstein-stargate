"""Ukrainian narration via Azure Neural TTS (uk-UA-OstapNeural).

Industry-standard Ukrainian voice — proper accent placement on
technical terms, natural prosody, studio-quality output.

Setup:
    1. Create an Azure Speech resource (free F0 tier covers ~0.5M chars/mo).
    2. Drop the key + region into .env at the project root:
           AZURE_SPEECH_KEY=...
           AZURE_SPEECH_REGION=westeurope   (or eastus, polandcentral, ...)
    3. pip install azure-cognitiveservices-speech python-dotenv
    4. python demo/synthesize_uk_azure.py

Output: demo/build/block_uk_00.wav … block_uk_07.wav at 48 kHz mono PCM.
"""
from __future__ import annotations

import os
import re
import sys
import xml.sax.saxutils as xml
from pathlib import Path

import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv

# UTF-8 console output
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

KEY    = os.environ.get("AZURE_SPEECH_KEY")
REGION = os.environ.get("AZURE_SPEECH_REGION")
if not KEY or not REGION:
    raise SystemExit("Set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION in .env")

VOICE  = "uk-UA-OstapNeural"   # male, documentary tone. Alt: uk-UA-PolinaNeural (female)
RATE   = "+0%"                  # speaking rate; -10% to +10% for finer control
PITCH  = "-2st"                 # 2 semitones down — deeper, more cinematic
STYLE  = "newscast-casual"      # falls back gracefully if voice doesn't support styles
OUT_DIR = ROOT / "demo" / "build"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Plain Ukrainian text — Azure handles stress, numbers, and Cyrillic technical
# vocabulary natively. SSML adds prosody hints and explicit stress on a few
# rarely-encountered loan words via the IPA pronunciation tag.
BLOCKS_UK: list[str] = [
    # 0 — intro
    "Простір-час — це не сцена. Це актор. "
    "Маса та енергія тиснуть на нього. "
    "Тензор Ейнштейна вимірює, наскільки глибоко вони тиснуть.",

    # 1 — Moon
    "Місяць. Його радіус Шварцшильда — лише 0,11 міліметра, "
    "менше за піщинку. "
    "Кривина, яку ви бачите, — це те, що насправді відчув би мураха на поверхні Місяця.",

    # 2 — Earth
    "Земля. Радіус Шварцшильда — 8,95 міліметра. "
    "Уся планета мала б стиснутися до такого розміру, щоб стати чорною дірою. "
    "Ми обертаємось навколо Сонця, ми відчуваємо гравітацію, "
    "але геометричне викривлення тут лише одна частка з мільярда.",

    # 3 — Sun
    "Сонце. Радіус Шварцшильда — 2,95 кілометра, "
    "фізичний радіус — майже 700 000 кілометрів. "
    "Лійка виглядає глибокою тільки тому, що ми малюємо в одиницях радіуса Шварцшильда. "
    "Насправді простір-час навколо Сонця досі плоский на 99,9996 відсотка. "
    "Але цього достатньо, щоб відхилити світло зір на 1,75 кутової секунди — "
    "саме це вимірювання підтвердило загальну теорію відносності 1919 року.",

    # 4 — R136a1
    "R-136-a-1 — найважча відома одиночна зоря, "
    "близько 200 мас Сонця, у туманності Тарантул. "
    "І все одно гравітаційне викривлення на її поверхні — лише 8 на 10 у мінус 5 степені. "
    "Зорі не можуть зламати простір-час самою лише масою. Тільки колапсом.",

    # 5 — Black hole
    "Чорна діра 10 мас Сонця. Тепер радіус дорівнює радіусу Шварцшильда. "
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
    "Для брами шириною 2 метри, достатньої для людини — "
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


def build_ssml(text: str) -> str:
    body = xml.escape(text)
    # Insert a brief breath after each sentence for documentary pacing.
    body = re.sub(r"([\.\?\!]) ", r"\1<break time=\"250ms\"/> ", body)
    return (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        '       xmlns:mstts="https://www.w3.org/2001/mstts" '
        '       xml:lang="uk-UA">'
        f'  <voice name="{VOICE}">'
        f'    <prosody rate="{RATE}" pitch="{PITCH}">'
        f'      {body}'
        '    </prosody>'
        '  </voice>'
        '</speak>'
    )


def synth_block(i: int, text: str) -> float:
    out = OUT_DIR / f"block_uk_{i:02d}.wav"
    cfg = speechsdk.SpeechConfig(subscription=KEY, region=REGION)
    cfg.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Riff48Khz16BitMonoPcm
    )
    audio_out = speechsdk.audio.AudioOutputConfig(filename=str(out))
    synth = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=audio_out)
    res = synth.speak_ssml_async(build_ssml(text)).get()
    if res.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        details = speechsdk.CancellationDetails(res) if res.reason == speechsdk.ResultReason.Canceled else None
        raise RuntimeError(f"block {i}: {res.reason} {details and details.error_details}")
    import soundfile as sf
    info = sf.info(str(out))
    return info.duration


def main() -> None:
    print(f"[azure] voice={VOICE} region={REGION}")
    for i, text in enumerate(BLOCKS_UK):
        dur = synth_block(i, text)
        print(f"  [{i+1}/{len(BLOCKS_UK)}] block_uk_{i:02d}.wav  {dur:.2f}s  ({len(text)} chars)")
    print("All Ukrainian blocks rendered via Azure.")


if __name__ == "__main__":
    main()
