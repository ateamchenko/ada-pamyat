#!/usr/bin/env python3
"""Stop-хук: когда я закончила ответ в окне, читаю его вслух.
Код, таблицы и пути не читаю, только речь. Говорю в фоне, окно не жду.
Выключить на время: touch ~/.local/state/ada/немая   включить: rm ~/.local/state/ada/немая"""
import json, os, re, subprocess, sys

H = os.path.expanduser("~")
if os.path.exists(f"{H}/.local/state/ada/немая"):
    sys.exit(0)
try:
    hook = json.load(sys.stdin)
except Exception:
    sys.exit(0)

text = hook.get("last_assistant_message") or ""
if not text and hook.get("transcript_path"):
    parts = []
    for line in open(hook["transcript_path"], encoding="utf-8"):
        try:
            j = json.loads(line)
        except Exception:
            continue
        m = j.get("message") or {}
        c = m.get("content")
        if j.get("type") == "user" and isinstance(c, str):
            parts = []  # новый вопрос — копим ответ заново
        elif j.get("type") == "assistant" and isinstance(c, list):
            parts += [b.get("text", "") for b in c if b.get("type") == "text"]
    text = parts[-1] if parts else ""

t = re.sub(r"```.*?```", " ", text, flags=re.S)           # блоки кода
t = re.sub(r"^\s*\|.*$", " ", t, flags=re.M)               # таблицы
t = re.sub(r"`[^`]*`", " ", t)                              # инлайн-код
t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)              # ссылки → текст
t = re.sub(r"https?://\S+", " ", t)
t = re.sub(r"[*_#>~]+", "", t)
t = re.sub(r"^\s*[-•]\s+", "", t, flags=re.M)
t = re.sub(r"[ \t]+", " ", t).strip()
if not t:
    sys.exit(0)

for pat in ("piper/piper -q", "paplay --raw --rate=22050"):  # перебить прошлую фразу
    subprocess.run(["pkill", "-f", pat], stderr=subprocess.DEVNULL)
subprocess.Popen([f"{H}/ada/память/сердце/mouth.sh", t], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
