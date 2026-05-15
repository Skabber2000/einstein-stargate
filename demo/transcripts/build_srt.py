"""Generate SRT caption files for Facebook upload.

Probes the actual F5-TTS block durations, splits each block by sentence,
and timestamps each cue proportionally to its character count. Output
files follow Facebook's required pattern: ``{video_basename}.{locale}.srt``
so they can be uploaded directly from the post composer.

Run from project root:
    python demo/transcripts/build_srt.py
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BUILD = ROOT / "demo" / "build"
OUT   = ROOT / "demo" / "transcripts"

# Match the timing constants in demo/assemble.sh
INTRO_DUR  = 8.0
XFADE1     = 5.0
MAIN_START = INTRO_DUR - XFADE1     # 3.0 s — when block 0 narration begins
GAP        = 0.4                    # silence between narration blocks

# Facebook requires SRT filenames in the form {video_basename}.{locale}.srt
VIDEO_BASENAME = "spacetime_facebook_1080p"
LANG_TO_LOCALE = {"en": "en_US", "uk": "uk_UA"}


def probe(path: Path) -> float:
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path),
    ], text=True)
    return float(out.strip())


def fmt_ts(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms == 1000:
        ms = 0
        s += 1
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def sentence_split(text: str) -> list[str]:
    """Split a paragraph into display-friendly subtitle cues.

    Splits at sentence boundaries, then further breaks long sentences at
    semicolons or commas if they exceed ~120 characters.
    """
    sents = re.split(r"(?<=[\.\!\?])\s+", text.strip())
    out: list[str] = []
    for s in sents:
        s = s.strip()
        if not s:
            continue
        if len(s) <= 120:
            out.append(s)
            continue
        # Break long sentences at ; or , if there's a comfortable midpoint
        parts = re.split(r"(?<=[;,])\s+", s)
        buf = ""
        for p in parts:
            if not buf:
                buf = p
            elif len(buf) + 1 + len(p) <= 120:
                buf = f"{buf} {p}"
            else:
                out.append(buf.strip())
                buf = p
        if buf:
            out.append(buf.strip())
    return out


# Per-language sentence-split scripts. The English version mirrors what
# F5-TTS actually spoke (so timings line up); the Ukrainian version uses
# the same sentence structure for parallel cue boundaries.
SCRIPTS = {
    "en": [
        # block 0 — intro
        ["Spacetime is not a stage. It is the cast.",
         "Mass and energy press on it; the Einstein tensor measures how deeply they press."],
        # block 1 — Moon
        ["The Moon.",
         "Its Schwarzschild radius is only 0.11 millimeters — smaller than a grain of sand.",
         "The curvature you see here is what an ant on the lunar surface would actually feel."],
        # block 2 — Earth
        ["The Earth.",
         "r-sub-s equals 8.95 millimeters.",
         "The entire planet would have to collapse to that size to become a black hole.",
         "We orbit the Sun, we feel gravity, yet the geometric distortion is only one part in ten to the nine."],
        # block 3 — Sun
        ["The Sun.",
         "Schwarzschild radius 2.95 kilometers; physical radius nearly 700 000 kilometers.",
         "The well looks deep here only because we plot in r-s units.",
         "In reality, spacetime around the Sun is still 99.9996 % flat.",
         "But enough to bend starlight by 1.75 arc-seconds — the measurement that confirmed General Relativity in 1919."],
        # block 4 — R136a1
        ["R136a1 — the most massive single star known.",
         "Roughly 200 solar masses, in the Tarantula Nebula.",
         "Despite that, the gravitational distortion at its surface is still only 8 × 10⁻⁵.",
         "Stars cannot break spacetime by mass alone — only by collapse."],
        # block 5 — Black hole
        ["A 10 M☉ black hole.",
         "Now the radius equals r-s. The full Flamm paraboloid is exposed.",
         "Inside the horizon, time and radius swap roles.",
         "This is what spacetime pressed past its breaking point looks like.",
         "But it has only one mouth. Whatever falls in cannot come out."],
        # block 6 — Star-Gate
        ["The Star-Gate.",
         "Two Schwarzschild geometries glued at a throat — an Einstein-Rosen bridge.",
         "Two mouths, one shortcut.",
         "To hold the throat open against its urge to collapse, you need exotic matter — matter with negative energy density."],
        # block 7 — energy
        ["How much energy does that cost?",
         "The Einstein equations give a classical estimate: c⁴ × b₀ divided by big-G.",
         "For a two-meter gate, wide enough for a person to walk through, that is 2.4 × 10⁴⁴ joules.",
         "To make that real: it equals about 10³¹ Hiroshima bombs.",
         "A one with thirty-one zeros after it.",
         "It equals every nuclear weapon currently on Earth, detonated at once, sixteen septillion times in a row.",
         "It equals four hundred sextillion years of total world energy production.",
         "Or, most directly: it equals one and a half Jupiters, annihilated into pure energy.",
         "Ford and Roman's quantum inequalities allow exotic energy only on the order of ℏc divided by b₀.",
         "For the same gate: less than a millionth of a billionth of a joule.",
         "The classical requirement exceeds the quantum allowance by seventy orders of magnitude.",
         "Until physics closes that gap, the Star-Gate stays science fiction."],
    ],
    "uk": [
        ["Простір-час — це не сцена. Це актор.",
         "Маса та енергія тиснуть на нього; тензор Ейнштейна вимірює, наскільки глибоко вони тиснуть."],
        ["Місяць.",
         "Його радіус Шварцшильда — лише 0,11 міліметра, менше за піщинку.",
         "Кривина, яку ви бачите, — це те, що насправді відчув би мураха на поверхні Місяця."],
        ["Земля.",
         "r-індекс-s дорівнює 8,95 міліметра.",
         "Уся планета мала б стиснутися до такого розміру, щоб стати чорною дірою.",
         "Ми обертаємось навколо Сонця, ми відчуваємо гравітацію — але геометричне викривлення тут лише одна частка з мільярда."],
        ["Сонце.",
         "Радіус Шварцшильда — 2,95 кілометра; фізичний радіус — майже 700 000 кілометрів.",
         "Лійка виглядає глибокою тільки тому, що ми малюємо в одиницях r-s.",
         "Насправді простір-час навколо Сонця досі плоский на 99,9996 відсотка.",
         "Але цього достатньо, щоб відхилити світло зір на 1,75 кутової секунди — саме це підтвердило загальну теорію відносності 1919 року."],
        ["R136a1 — найважча відома одиночна зоря.",
         "Близько 200 мас Сонця, у Тарантулі.",
         "І все одно гравітаційне викривлення на її поверхні — лише 8 × 10⁻⁵.",
         "Зорі не можуть зламати простір-час самою лише масою — тільки колапсом."],
        ["Чорна діра 10 мас Сонця.",
         "Тепер R дорівнює r-s. Уся параболоїда Фламма відкрита.",
         "Усередині горизонту час і радіус міняються ролями.",
         "Ось так виглядає простір-час, продавлений за межу.",
         "Але в неї лише одна горлянка. Усе, що падає всередину, назовні не повертається."],
        ["Зоряна Брама.",
         "Дві геометрії Шварцшильда, склеєні горлом — міст Ейнштейна-Розена.",
         "Дві горлянки, один тунель.",
         "Щоб утримати горло відкритим всупереч його прагненню колапсувати, потрібна екзотична матерія — матерія з від'ємною щільністю енергії."],
        ["Скільки енергії це коштує?",
         "Рівняння Ейнштейна дають класичну оцінку: c⁴ × b₀, поділене на G.",
         "Для брами шириною два метри, достатньої для людини, — це 2,4 × 10⁴⁴ джоулів.",
         "Щоб уявити це число: приблизно 10³¹ Хіросім.",
         "Одиниця з тридцяти однома нулями.",
         "Це дорівнює всій ядерній зброї Землі, підірваній одночасно, шістнадцять септильйонів разів поспіль.",
         "Чотириста секстильйонів років усієї світової енергетики.",
         "Або, найпряміше: півтори маси Юпітера, перетворені на чисту енергію.",
         "Квантові нерівності Форда-Романа дозволяють екзотичній енергії лише ℏc, поділене на b₀.",
         "Для тієї ж брами — менше за мільйонну частку мільярдної частки джоуля.",
         "Класична вимога перевищує квантовий ліміт на сімдесят порядків.",
         "Поки фізика не закриє цю прірву — Зоряна Брама лишається наукової фантастикою."],
    ],
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    block_durations = []
    for i in range(8):
        p = BUILD / f"block_{i:02d}.wav"
        if not p.exists():
            raise SystemExit(f"missing {p} — run synthesize.py first")
        block_durations.append(probe(p))

    # Compute the start time of each block in the final video timeline.
    block_starts = []
    t = MAIN_START
    for d in block_durations:
        block_starts.append(t)
        t += d + GAP
    print(f"timeline: narration 0 starts at {block_starts[0]:.2f}s, ends at {t:.2f}s")

    for lang, blocks in SCRIPTS.items():
        if len(blocks) != len(block_durations):
            raise SystemExit(f"{lang}: expected {len(block_durations)} blocks, got {len(blocks)}")

        srt_lines: list[str] = []
        cue = 1
        for bi, sentences in enumerate(blocks):
            # Re-split anything we missed; preserves long-sentence safety.
            cues = []
            for s in sentences:
                cues.extend(sentence_split(s))
            total_chars = sum(len(c) for c in cues) or 1
            t0 = block_starts[bi]
            block_dur = block_durations[bi]
            running = 0.0
            for c in cues:
                share = len(c) / total_chars
                dur = block_dur * share
                start = t0 + running
                end = start + dur
                # Trim trailing gap inside the block so display doesn't overrun next cue
                if c is cues[-1]:
                    end = t0 + block_dur
                srt_lines.append(
                    f"{cue}\n{fmt_ts(start)} --> {fmt_ts(end)}\n{c}\n"
                )
                cue += 1
                running += dur
        locale = LANG_TO_LOCALE.get(lang, lang)
        srt_path = OUT / f"{VIDEO_BASENAME}.{locale}.srt"
        srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
        print(f"  → {srt_path.relative_to(ROOT)}  ({cue-1} cues)")


if __name__ == "__main__":
    main()
