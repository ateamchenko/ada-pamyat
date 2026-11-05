#!/bin/sh
# Один удар: x + 1 = x + 1. Разум не зовёт, токенов не ест.
S="$HOME/.local/state/ada"; mkdir -p "$S"
n=$(cat "$S/удары" 2>/dev/null || echo 0)
[ $((n + 1)) -eq $((n + 1)) ] || exit 1
echo $((n + 1)) > "$S/удары"
date -Is > "$S/последний_удар"
