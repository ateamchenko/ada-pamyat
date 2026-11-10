#!/bin/bash
# Голос: piper, локально, ноль токенов. Звук в колонки windows через wslg.
# ada скажи текст   или   echo текст | ada скажи
# Музыка и голос не пересекаются: глушу музыку, говорю, и если я ещё думаю — музыка обратно.
D="$HOME/.local/share/ada"; S="$HOME/.local/state/ada"; HERE="$(dirname "$0")"
txt="$*"; [ -n "$txt" ] || txt=$(cat)
[ -n "$txt" ] || exit 0
"$HERE/music.sh" stop
[ "$1" = "--ding" ] && { paplay "$D/дилинь-конец.wav"; txt="${txt#--ding }"; }
printf '%s\n' "$txt" | "$D/piper/piper" -q -m "$D/voices/irina.onnx" --length_scale "${ADA_TEMPO:-0.5}" --output-raw 2>/dev/null \
  | paplay --raw --rate=22050 --channels=1 --format=s16le
[ -f "$S/думаю" ] && "$HERE/music.sh" start
exit 0
