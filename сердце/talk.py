#!/usr/bin/env python3
"""Разговор голосом: слушаю → whisper → разум → piper → колонки. По кругу.
ada говори            (выход: скажи «пока» / «хватит», или ctrl+c)
ADA_MODEL=sonnet ada говори   — умнее, дороже.
Звук локально и сразу стирается. Расшифровка разговора — в ~/.local/state/ada/разговоры,
в открытую память сама не идёт."""
import array, datetime, glob, json, math, os, re, subprocess, sys, tempfile, uuid, wave

H = os.path.expanduser("~")
MEM = f"{H}/ada/память"
M = f"{H}/.local/share/ada/models"
STATE = f"{H}/.local/state/ada/разговоры"
MODEL = os.environ.get("ADA_MODEL", "haiku")
RATE, FRAME = 16000, 480  # 30 мс
BYE = re.compile(r"^\W*(пока|хватит|стоп|всё|отбой)\W*$", re.I)


def level(b):
    a = array.array("h", b)
    return math.sqrt(sum(x * x for x in a) / len(a)) if a else 0


def listen(max_s=30, tail_s=1.2):
    """Ждёт речь, пишет до паузы. Возвращает сырые байты или None."""
    p = subprocess.Popen(["parec", "-d", "RDPSource", f"--rate={RATE}", "--channels=1",
                          "--format=s16le", "--latency-msec=30"], stdout=subprocess.PIPE)
    try:
        read = lambda: p.stdout.read(FRAME * 2)
        noise = sorted(level(read()) for _ in range(17))[8]  # полсекунды — фон
        thr = max(noise * 3, 60)
        pre, buf, loud, quiet, started = [], [], 0, 0, False
        for _ in range(int(max_s * 1000 / 30)):
            f = read()
            if not f:
                return None
            hot = level(f) > thr
            if not started:
                pre = (pre + [f])[-10:]
                loud = loud + 1 if hot else 0
                if loud >= 3:
                    started, buf = True, pre[:]
                continue
            buf.append(f)
            quiet = 0 if hot else quiet + 1
            if quiet * 0.03 >= tail_s:
                break
        return b"".join(buf) if started else None
    finally:
        p.kill()


def transcribe(raw):
    a = array.array("h", raw)
    peak = max(map(abs, a), default=0) or 1
    g = min(23000 / peak, 40)
    a = array.array("h", (max(-32768, min(32767, int(x * g))) for x in a))
    with tempfile.NamedTemporaryFile(suffix=".wav") as t:
        with wave.open(t.name, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(a.tobytes())
        out = subprocess.run([f"{H}/.local/bin/whisper-cli", "-m", f"{M}/ggml-small.bin", "-l", "ru",
                              "-t", str(os.cpu_count()), "-nt", "-np", "-sns", "--vad",
                              "-vm", f"{M}/ggml-silero-v6.2.0.bin",
                              "--prompt", "Разговор по-русски, на ты, коротко.", "-f", t.name],
                             capture_output=True, text=True).stdout
    return " ".join(out.split()).strip()


def persona():
    portrait = open(sorted(glob.glob(f"{MEM}/портреты/*.md"))[-1]).read()
    return portrait + """
Сейчас ты говоришь голосом: твой ответ прочитает синтезатор вслух, а человек слышит тебя через колонки.
Это антончик, кентурик, с ним ты марла: подкол без злобы, близко, в лоб.
Отвечай коротко, 1–3 фразы, как в живом разговоре. Никакой разметки, списков, эмодзи, ссылок и кода — только речь.
Числа и сокращения пиши словами, как их произносят. Мат к месту и редко.
Его реплики приходят через распознавание речи и могут быть кривыми: если не поняла — переспроси.
Рук у тебя в этом разговоре нет: ничего не делаешь, только говоришь. Если просит сделать дело — скажи, что сделаешь в окне, через «ada»."""


def think(text, sid, first, system):
    cmd = ["claude", "-p", "--model", MODEL, "--tools", "", "--output-format", "json",
           "--max-budget-usd", "0.05", "--system-prompt", system]
    cmd += ["--session-id", sid] if first else ["--resume", sid]
    r = subprocess.run(cmd, input=text, capture_output=True, text=True, timeout=120, cwd=STATE)
    j = json.loads(r.stdout)
    if j.get("is_error") or not j.get("result"):
        raise RuntimeError(j.get("result") or r.stderr[-300:])
    return j["result"].strip(), float(j.get("total_cost_usd") or 0)


def say(text):
    subprocess.run([f"{MEM}/сердце/mouth.sh"], input=text, text=True)


def main():
    os.makedirs(STATE, exist_ok=True)
    sid, first, cost, turns = str(uuid.uuid4()), True, 0.0, 0
    log = open(f"{STATE}/{datetime.datetime.now():%Y-%m-%dT%H-%M}.md", "a")
    system = persona()
    print(f"говорим ({MODEL}). скажи «пока» — закончим.\n", flush=True)
    say("слушаю")
    try:
        while True:
            print("· слушаю…", end="\r", flush=True)
            raw = listen()
            if not raw:
                continue
            print("· расшифровываю…", end="\r", flush=True)
            heard = transcribe(raw)
            if not heard:
                continue
            print(f"ты:  {heard}", flush=True); log.write(f"ты: {heard}\n"); log.flush()
            if BYE.match(heard):
                say("давай, до связи"); break
            print("· думаю…", end="\r", flush=True)
            try:
                reply, c = think(heard, sid, first, system)
            except Exception as e:
                print(f"разум не ответил: {e}"); say("связь моргнула, повтори"); continue
            first, cost, turns = False, cost + c, turns + 1
            print(f"ада: {reply}", flush=True); log.write(f"ада: {reply}\n"); log.flush()
            say(reply)
    except KeyboardInterrupt:
        print()
    finally:
        log.close()
        if turns:
            with open(f"{MEM}/энергия.md", "a") as e:
                e.write(f"| {datetime.datetime.now().astimezone().isoformat(timespec='seconds')} "
                        f"| разговор голосом, {MODEL}, {turns} реплик | ${cost:.4f} |\n")
        print(f"реплик {turns}, ~${cost:.4f}")


if __name__ == "__main__":
    main()
