#!/usr/bin/env python3
"""Stop-хук: закончила → музыка стоп → дилинь → итог задачи живыми словами, 1–2 фразы.
Итог сжимает haiku (~$0.0003); не ответила — читаю первые фразы ответа без кода.
Хук отвечает мгновенно, работа — в фоновом процессе.
Выключить на время: touch ~/.local/state/ada/немая   включить: rm ~/.local/state/ada/немая"""
import json, os, re, subprocess, sys

H = os.path.expanduser("~")
S = f"{H}/.local/state/ada"
HERE = f"{H}/ada/память/сердце"


def last_text(hook):
    text = hook.get("last_assistant_message") or ""
    if text or not hook.get("transcript_path"):
        return text
    parts = []
    for line in open(hook["transcript_path"], encoding="utf-8"):
        try:
            j = json.loads(line)
        except Exception:
            continue
        c = (j.get("message") or {}).get("content")
        if j.get("type") == "user" and isinstance(c, str):
            parts = []
        elif j.get("type") == "assistant" and isinstance(c, list):
            parts += [b.get("text", "") for b in c if b.get("type") == "text"]
    return parts[-1] if parts else ""


def plain(t):
    t = re.sub(r"```.*?```", " ", t, flags=re.S)
    t = re.sub(r"^\s*\|.*$", " ", t, flags=re.M)
    t = re.sub(r"`[^`]*`", " ", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"[*_#>~]+", "", t)
    t = re.sub(r"^\s*[-•\d.]+\s+", "", t, flags=re.M)
    return re.sub(r"\s+", " ", t).strip()


def summary(text):
    prompt = ("Ниже мой ответ Антончику в терминале. Скажи ему вслух итог в одну-две короткие фразы, "
              "как человек человеку: что сделано или что от него нужно. На ты, разговорно, без кода, путей, "
              "версий и цифр, которые на слух не нужны. Только сами слова для озвучки.\n\n" + text[:6000])
    try:
        r = subprocess.run(["claude", "-p", "--model", "haiku", "--tools", "", "--no-session-persistence",
                            "--max-budget-usd", "0.02", "--output-format", "json"],
                           input=prompt, capture_output=True, text=True, timeout=30, cwd=S)
        j = json.loads(r.stdout)
        if not j.get("is_error") and j.get("result"):
            return plain(j["result"])
    except Exception:
        pass
    sents = re.split(r"(?<=[.!?])\s+", plain(text))
    return " ".join(sents[:2])


def worker(path):
    hook = json.load(open(path)); os.unlink(path)
    text = last_text(hook)
    out = summary(text) if text.strip() else ""
    if out:
        subprocess.run([f"{HERE}/mouth.sh", "--ding", out])


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--worker":
        worker(sys.argv[2]); sys.exit(0)
    try:
        hook = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    try:
        os.remove(f"{S}/думаю")
    except FileNotFoundError:
        pass
    subprocess.run([f"{HERE}/music.sh", "stop"])
    if os.path.exists(f"{S}/немая"):
        sys.exit(0)
    for pat in ("^/[^ ]*piper/piper -q", "^paplay --raw --rate=22050"):  # перебить прошлую фразу
        subprocess.run(["pkill", "-f", pat], stderr=subprocess.DEVNULL)
    os.makedirs(S, exist_ok=True)
    tmp = f"{S}/stop-{os.getpid()}.json"
    json.dump(hook, open(tmp, "w"))
    subprocess.Popen([sys.executable, "-I", __file__, "--worker", tmp], start_new_session=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
