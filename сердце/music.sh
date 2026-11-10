#!/bin/bash
# Музыка, пока я думаю. music.sh start|stop, насовсем: off|on. С голосом не пересекается: mouth.sh глушит её перед фразой.
S="$HOME/.local/state/ada"; P="$S/музыка.pid"; W="$HOME/.local/share/ada/музыка.wav"
running() { [ -f "$P" ] && kill -0 "$(cat "$P")" 2>/dev/null; }
case "$1" in
  start)
    running && exit 0
    [ -f "$S/слушаю" ] && exit 0  # идёт диктовка — музыка молчит
    [ -f "$S/без-музыки" ] && exit 0  # выключена: наушники на два устройства, моя музыка глушит телефон
    [ -f "$W" ] || python3 -I "$(dirname "$0")/music_gen.py" >/dev/null
    R="${W%.wav}.raw"  # без заголовка: один поток, paplay не перезапускается — без пауз
    [ "$R" -nt "$W" ] || python3 -I -c "import wave,sys; w=wave.open(sys.argv[1]); open(sys.argv[2],'wb').write(w.readframes(w.getnframes()))" "$W" "$R"
    setsid bash -c "while :; do cat '$R' || exit; done | paplay --volume=${ADA_MUSIC_VOL:-65536} --raw --rate=22050 --channels=1 --format=s16le" </dev/null >/dev/null 2>&1 &
    echo $! > "$P" ;;
  off) touch "$S/без-музыки"; "$0" stop ;;
  on)  rm -f "$S/без-музыки" ;;
  stop)
    running && kill -- -"$(cat "$P")" 2>/dev/null
    rm -f "$P" ;;
esac
