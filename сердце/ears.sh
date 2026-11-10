#!/bin/bash
# Уши: слушаю по команде, всё локально, звук никуда не уходит и сразу стирается.
# ada слушай [секунд]   (по умолчанию 15, ctrl+c — хватит, расшифровать)
sec="${1:-15}"
model="$HOME/.local/share/ada/models/ggml-small.bin"
wav=$(mktemp --suffix=.wav)
trap 'rm -f "$wav"' EXIT

echo "слушаю ${sec}с… (ctrl+c — хватит)"
trap ':' INT
timeout "$sec" parecord -d RDPSource --rate=16000 --channels=1 --format=s16le --file-format=wav "$wav"
trap - INT

[ "$(stat -c %s "$wav")" -gt 1000 ] || { echo "тишина: звука не пришло"; exit 1; }
echo "расшифровываю…"
"$HOME/.local/bin/whisper-cli" -m "$model" -l ru -t "$(nproc)" -nt -np -f "$wav" 2>/dev/null | sed '/^\s*$/d'
