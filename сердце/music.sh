#!/bin/bash
# Музыка, пока я думаю. music.sh start|stop. С голосом не пересекается: mouth.sh глушит её перед фразой.
S="$HOME/.local/state/ada"; P="$S/музыка.pid"; W="$HOME/.local/share/ada/музыка.wav"
running() { [ -f "$P" ] && kill -0 "$(cat "$P")" 2>/dev/null; }
case "$1" in
  start)
    running && exit 0
    [ -f "$W" ] || python3 -I "$(dirname "$0")/music_gen.py" >/dev/null
    setsid bash -c "while :; do paplay --volume=${ADA_MUSIC_VOL:-65536} '$W' || exit; done" </dev/null >/dev/null 2>&1 &
    echo $! > "$P" ;;
  stop)
    running && kill -- -"$(cat "$P")" 2>/dev/null
    rm -f "$P" ;;
esac
