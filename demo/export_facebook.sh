#!/usr/bin/env bash
# Facebook-ready export from the lossless master.
# Targets the 2026 Facebook video spec for 16:9 landscape:
#   - 1920 × 1080 @ 30 fps (h.264 high profile, yuv420p, +faststart)
#   - AAC stereo @ 192 kbps
#   - Loudness normalized to -14 LUFS (streaming standard) via 2-pass EBU R128
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:$PATH"

cd "$(dirname "$0")/.."

LANG_CODE="${LANG:-en}"
if [[ "$LANG_CODE" == "en" ]]; then
  SUFFIX=""
else
  SUFFIX="_${LANG_CODE}"
fi
SRC="demo/build/spacetime_full${SUFFIX}.mp4"
OUT="demo/build/spacetime_facebook_1080p${SUFFIX}.mp4"
echo "[export] lang=$LANG_CODE  src=$(basename "$SRC")  out=$(basename "$OUT")"

if [[ ! -f "$SRC" ]]; then echo "missing $SRC"; exit 1; fi

# --- Pass 1: measure loudness ---
echo "[1/2] Measuring loudness…"
STATS=$(ffmpeg -hide_banner -i "$SRC" \
  -af "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json" \
  -f null - 2>&1 | awk '/^{$/{f=1} f; /^}$/{exit}')
echo "$STATS"

IL=$(echo "$STATS"  | python3 -c "import sys,json; print(json.load(sys.stdin)['input_i'])")
TP=$(echo "$STATS"  | python3 -c "import sys,json; print(json.load(sys.stdin)['input_tp'])")
LRA=$(echo "$STATS" | python3 -c "import sys,json; print(json.load(sys.stdin)['input_lra'])")
THR=$(echo "$STATS" | python3 -c "import sys,json; print(json.load(sys.stdin)['input_thresh'])")
TGT=$(echo "$STATS" | python3 -c "import sys,json; print(json.load(sys.stdin)['target_offset'])")

# --- Pass 2: encode with high quality + normalized loudness ---
echo "[2/2] Encoding 1080p high-quality MP4…"
ffmpeg -y -i "$SRC" \
  -vf "scale=1920:1080:flags=lanczos:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,format=yuv420p" \
  -c:v h264_videotoolbox -b:v 12M -maxrate 16M -bufsize 24M -allow_sw 1 \
    -profile:v high -level 4.2 \
    -movflags +faststart \
  -af "loudnorm=I=-14:TP=-1.5:LRA=11:measured_I=$IL:measured_TP=$TP:measured_LRA=$LRA:measured_thresh=$THR:offset=$TGT:linear=true:print_format=summary" \
  -c:a aac -b:a 192k -ar 48000 -ac 2 \
  -metadata title="How Much Energy to Open a Star-Gate?" \
  -metadata author="Eugene Nayshtetik" \
  -metadata description="A 3-minute primer in General Relativity" \
  "$OUT"

echo ""
echo "✓ $OUT"
ls -lh "$OUT"
ffprobe -v error -show_entries format=duration,size,bit_rate:stream=codec_name,width,height,r_frame_rate,channels,sample_rate -of default "$OUT" | grep -E '^[a-z_]+='
