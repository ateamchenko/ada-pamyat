#!/bin/bash
# Голос: piper, локально, ноль токенов. Звук в колонки windows через wslg.
# ada скажи текст   или   echo текст | ada скажи
D="$HOME/.local/share/ada"
txt="$*"; [ -n "$txt" ] || txt=$(cat)
[ -n "$txt" ] || exit 0
printf '%s\n' "$txt" | "$D/piper/piper" -q -m "$D/voices/irina.onnx" --output-raw 2>/dev/null \
  | paplay --raw --rate=22050 --channels=1 --format=s16le
