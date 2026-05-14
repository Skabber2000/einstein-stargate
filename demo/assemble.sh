#!/usr/bin/env bash
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:$PATH"

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
B="$ROOT/demo/build"
G="$ROOT/demo/grok"
OV="$ROOT/demo/overlays"
M="$ROOT/demo/music"

INTRO="$G/intro.mp4"           # 8 s, golden Gμν symbol
MAIN="$B/spacetime_demo.mp4"    # 156 s, narrated walkthrough
OUTRO="$G/outro2.mp4"           # 8 s, spaceship into wormhole

TITLE="$OV/intro_title.png"
MSG="$OV/outro_message.png"
MUSIC="$M/Aces_High.mp3"        # Kevin MacLeod, CC-BY 4.0 — incompetech.com

OUT="$B/spacetime_full.mp4"

# Timing
INTRO_DUR=8
MAIN_DUR=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$MAIN")
OUTRO_DUR=8
XFADE1=5     # intro → main crossfade
XFADE2=1     # main → outro crossfade
# Output start of main:   intro_dur - xfade1   = 3
# Output start of outro:  3 + main_dur - xfade2
MAIN_START=$(python3 -c "print($INTRO_DUR - $XFADE1)")
OUTRO_START=$(python3 -c "print($MAIN_START + $MAIN_DUR - $XFADE2)")
TOTAL=$(python3 -c "print($OUTRO_START + $OUTRO_DUR)")
echo "main_start=$MAIN_START  outro_start=$OUTRO_START  total=$TOTAL"

ffmpeg -y \
  -i "$INTRO" \
  -i "$MAIN" \
  -i "$OUTRO" \
  -loop 1 -t $INTRO_DUR -i "$TITLE" \
  -loop 1 -t $OUTRO_DUR -i "$MSG" \
  -i "$MUSIC" \
  -filter_complex "\
    [0:v]scale=1600:900:flags=lanczos:force_original_aspect_ratio=increase,crop=1600:900,setsar=1,fps=25,format=yuva420p[iv]; \
    [3:v]format=rgba,fade=t=in:st=0.5:d=1.0:alpha=1,fade=t=out:st=5.5:d=2.5:alpha=1[ovi]; \
    [iv][ovi]overlay=0:0:format=auto[iv2]; \
    [1:v]setsar=1,fps=25,format=yuv420p[mv]; \
    [2:v]scale=1600:900:flags=lanczos:force_original_aspect_ratio=increase,crop=1600:900,setsar=1,fps=25,format=yuva420p[ov]; \
    [4:v]format=rgba,fade=t=in:st=1.5:d=1.0:alpha=1,fade=t=out:st=7.0:d=1.0:alpha=1[ovo]; \
    [ov][ovo]overlay=0:0:format=auto[ov2]; \
    [iv2]format=yuv420p[iv3]; \
    [ov2]format=yuv420p[ov3]; \
    [iv3][mv]xfade=transition=fade:duration=${XFADE1}:offset=$(python3 -c "print($INTRO_DUR-$XFADE1)")[vab]; \
    [vab][ov3]xfade=transition=fade:duration=${XFADE2}:offset=$(python3 -c "print($MAIN_START+$MAIN_DUR-$XFADE2)")[vfinal]; \
    [1:a]aresample=48000,aformat=channel_layouts=stereo,adelay=${MAIN_START}s:all=1,volume=1.0[narrpre]; \
    [narrpre]asplit=2[narr][narrkey]; \
    [5:a]aresample=48000,aformat=channel_layouts=stereo,atrim=duration=$TOTAL,volume=0.55,afade=t=in:st=0:d=2,afade=t=out:st=$(python3 -c "print(round($TOTAL-3,2))"):d=3[muspre]; \
    [muspre][narrkey]sidechaincompress=threshold=0.04:ratio=8:attack=12:release=380:makeup=2.0:level_sc=0.8[musduck]; \
    [narr][musduck]amix=inputs=2:duration=longest:weights='3 1':normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[afinal]" \
  -map "[vfinal]" -map "[afinal]" \
  -t $TOTAL \
  -c:v h264_videotoolbox -b:v 10M -allow_sw 1 -pix_fmt yuv420p \
    -profile:v high -level 4.2 \
  -c:a aac -b:a 192k -movflags +faststart \
  "$OUT"

echo "→ $OUT"
ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$OUT"
