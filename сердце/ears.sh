#!/bin/bash
# Уши: слушаю по команде, всё локально, звук никуда не уходит и сразу стирается.
# ada слушай [секунд]   (по умолчанию 15, ctrl+c — хватит, расшифровать)
sec="${1:-15}"
M="$HOME/.local/share/ada/models"
wav=$(mktemp --suffix=.wav)
trap 'rm -f "$wav"' EXIT

echo "слушаю ${sec}с… (ctrl+c — хватит)"
trap ':' INT
timeout "$sec" parecord -d RDPSource --rate=16000 --channels=1 --format=s16le --file-format=wav "$wav"
trap - INT

# громкость: микрофон wslg тихий — тяну пик до ~70%, печатаю уровень
python3 -I - "$wav" <<'PY' || exit 1
import wave, array, sys
p = sys.argv[1]
with wave.open(p) as f:
    params = f.getparams(); a = array.array('h', f.readframes(f.getnframes()))
peak = max(map(abs, a), default=0)
if len(a) < 8000:
    print("тишина: звука не пришло"); sys.exit(1)
g = min(23000 / peak, 40) if peak else 1
print(f"уровень: пик {peak}, усилила ×{g:.1f}")
a = array.array('h', (max(-32768, min(32767, int(x * g))) for x in a))
with wave.open(p, 'wb') as f:
    f.setparams(params); f.writeframes(a.tobytes())
PY

echo "расшифровываю…"
txt=$("$HOME/.local/bin/whisper-cli" -m "$M/ggml-small.bin" -l ru -t "$(nproc)" -nt -np -sns \
      --vad -vm "$M/ggml-silero-v6.2.0.bin" \
      --prompt "Разговор по-русски, на ты, коротко: привет, слушай, ада." \
      -f "$wav" 2>/dev/null | sed '/^\s*$/d')
echo "${txt:-голоса не услышала}"
