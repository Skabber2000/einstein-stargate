#!/usr/bin/env bash
# Download the Piper neural-TTS voice used by demo/make_demo.cjs.
# Default voice: en_US-ryan-high (male, US, 22 kHz). Swap by editing demo/script.json.
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p demo/voices
BASE="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/high"
echo "Downloading en_US-ryan-high ONNX model (~115 MB)…"
curl -L --fail -o demo/voices/en_US-ryan-high.onnx       "$BASE/en_US-ryan-high.onnx"
curl -L --fail -o demo/voices/en_US-ryan-high.onnx.json  "$BASE/en_US-ryan-high.onnx.json"
echo "Done."
ls -lh demo/voices/
