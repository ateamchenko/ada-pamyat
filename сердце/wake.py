#!/usr/bin/env python3
"""Слух всегда: «ада» → дилинь + «привет» → говоришь сколько хочешь → «делай» →
дилинь, текст в окно claude (windows terminal, заголовок со значка: ✳ или крутилка) + enter → там хук включает музыку.
«отмена» — выбросить; 20 с тишины — отбой, ничего не шлю.
Звук не хранится; whisper зовётся только на короткие громкие куски.
Сервис: systemctl --user {start|stop} ada-ears"""
import array, base64, io, math, os, re, subprocess, sys, tempfile, time, urllib.error, urllib.request, wave

H = os.path.expanduser("~")
D = f"{H}/.local/share/ada"
M = f"{D}/models"
RATE, FRAME = 16000, 480  # 30 мс
WAKE = re.compile(r"(^|[^\w])(ада|адa|ода|ада|ade|ada)([^\w]|$)", re.I)
DO = re.compile(r"(^|[^\w])дела[йюи]\w*[^\w]*$", re.I)  # «…делай.» в конце куска
HALLU = re.compile(r"субтитр|продолжение следует|спасибо за просмотр|подписывайтесь|редактор|корректор|семкин|dimatorzok", re.I)
CANCEL = re.compile(r"\bотмен\w*|^\W*(забей|отбой)\W*$", re.I)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def level(b):
    a = array.array("h", b)
    return math.sqrt(sum(x * x for x in a) / len(a)) if a else 0


class Mic:
    def __init__(self):
        self.p = subprocess.Popen(["parec", "-d", "RDPSource", f"--rate={RATE}", "--channels=1",
                                   "--format=s16le", "--latency-msec=30"], stdout=subprocess.PIPE)
        self.noise = 40.0

    def frame(self):
        f = self.p.stdout.read(FRAME * 2)
        if len(f) < FRAME * 2:
            raise EOFError("микрофон отвалился")
        return f

    def drain(self):  # выкинуть то, что накопилось, пока мы думали
        os.set_blocking(self.p.stdout.fileno(), False)
        try:
            while self.p.stdout.read(65536):
                pass
        except (BlockingIOError, TypeError):
            pass
        os.set_blocking(self.p.stdout.fileno(), True)

    def segment(self, max_s, tail_s=0.8, wait_s=None):
        """Кусок речи от начала громкого до паузы. None — если не дождались (wait_s)."""
        pre, buf, loud, quiet, started, n = [], [], 0, 0, False, 0
        talk_until = 0
        while True:
            f = self.frame(); n += 1; lv = level(f)
            if n % 5 == 0 and i_am_talking():
                talk_until = n + 10  # и ещё 0.3 с хвоста эха
            if n < talk_until:  # мой голос из колонок — не слушаю, кусок выбрасываю
                pre, buf, loud, quiet, started = [], [], 0, 0, False
                continue
            thr = max(self.noise * 2.5, 60)
            hot = lv > thr
            if not started:
                if not hot:
                    self.noise = 0.98 * self.noise + 0.02 * lv  # фон плавает — слежу
                pre = (pre + [f])[-15:]
                loud = loud + 1 if hot else 0
                if loud >= 3:
                    started, buf = True, pre[:]
                elif wait_s and n * 0.03 > wait_s:
                    return None
                continue
            buf.append(f)
            quiet = 0 if hot else quiet + 1
            if quiet * 0.03 >= tail_s or len(buf) * 0.03 >= max_s:
                return b"".join(buf)


SERVERS = {  # модель держится в памяти — ответ за доли секунды
    "ggml-base.bin": (8765, ["-ac", "320", "-bs", "1"]),   # зов и да/нет: окно 5 с
    "ggml-small.bin": (8766, ["-ac", "768"]),              # диктовка: окно 15 с
}


def start_servers():
    procs = []
    for model, (port, extra) in SERVERS.items():
        procs.append(subprocess.Popen([f"{H}/.local/bin/whisper-server", "-m", f"{M}/{model}", "-l", "ru",
                                       "-t", str(os.cpu_count()), "--port", str(port), "-sns", *extra],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    for port, _ in SERVERS.values():
        for _ in range(150):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1); break
            except urllib.error.HTTPError:
                break
            except Exception:
                time.sleep(0.2)
    return procs


def stt(raw, model, prompt, fast=False):
    a = array.array("h", raw)
    peak = max(map(abs, a), default=0) or 1
    g = min(23000 / peak, 40)
    a = array.array("h", (max(-32768, min(32767, int(x * g))) for x in a))
    bio = io.BytesIO()
    with wave.open(bio, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(a.tobytes())
    b = "adaboundary"
    fields = {"response_format": "text", "temperature": "0", "prompt": prompt}
    body = b"".join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
                    for k, v in fields.items())
    body += (f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="a.wav"\r\n'
             f'Content-Type: audio/wav\r\n\r\n').encode() + bio.getvalue() + f"\r\n--{b}--\r\n".encode()
    port = SERVERS[model][0]
    req = urllib.request.Request(f"http://127.0.0.1:{port}/inference", data=body,
                                 headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    try:
        out = urllib.request.urlopen(req, timeout=60).read().decode(errors="ignore")  # whisper бывает режет букву пополам
    except Exception as e:
        log("whisper не ответил:", e); return ""
    out = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", out)  # [музыка], (смех)
    out = " ".join(out.split()).strip()
    if HALLU.search(out) or (len(out) > 3 and out == out.upper() and re.search("[А-ЯЁA-Z]{3}", out)):  # whisper на шуме выдумывает титры
        log("  · (выдумка whisper, выкинула:", out + ")"); return ""
    return out


def ding(name="дилинь"):
    subprocess.run([f"{H}/ada/память/сердце/music.sh", "stop"])  # голос и музыка не пересекаются
    subprocess.run(["paplay", f"{D}/{name}.wav"], stderr=subprocess.DEVNULL)


def i_am_talking():
    """Говорю ли я сейчас: mouth.sh держит файл говорю.<pid>, пока звучит. Дёшево — можно звать на каждом кадре."""
    import glob
    for f in glob.glob(f"{H}/.local/state/ada/говорю.*"):
        try:
            os.kill(int(f.rsplit(".", 1)[1]), 0); return True
        except (ProcessLookupError, ValueError):
            try: os.remove(f)
            except OSError: pass
        except PermissionError:
            return True
    return False


PHRASES = {"привет": "привет", "всё": "это всё?", "дальше": "говори", "непоняла": "не поняла. это всё?",
           "отмена": "отбой", "пусто": "ничего не услышала"}


def prepare_phrases():
    """Фразы заранее в wav — звучат сразу, без запуска piper."""
    os.makedirs(f"{D}/фразы", exist_ok=True)
    for k, t in PHRASES.items():
        f = f"{D}/фразы/{k}.wav"
        if not os.path.exists(f):
            subprocess.run([f"{D}/piper/piper", "-q", "-m", f"{D}/voices/irina.onnx",
                            "--length_scale", os.environ.get("ADA_TEMPO", "0.5"), "-f", f],
                           input=t, text=True, stderr=subprocess.DEVNULL)


def say(k):
    subprocess.run(["paplay", f"{D}/фразы/{k}.wav"], stderr=subprocess.DEVNULL)


PS = r"""
$t = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('%s'))
Add-Type @'
using System; using System.Runtime.InteropServices;
public class W { [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
                 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
                 [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
                 [DllImport("user32.dll")] public static extern void keybd_event(byte k, byte s, uint f, UIntPtr e);
                 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c); }
'@
$isClaude = { param($s) $s.Length -gt 0 -and -not [char]::IsLetterOrDigit($s[0]) -and -not [char]::IsWhiteSpace($s[0]) }
$w = Get-Process WindowsTerminal -ErrorAction SilentlyContinue | ? { $_.MainWindowHandle -ne 0 -and (& $isClaude $_.MainWindowTitle) } | select -First 1
if (-not $w) { Write-Output 'NOWIN'; exit 1 }
$h = $w.MainWindowHandle
for ($i = 0; $i -lt 5 -and [W]::GetForegroundWindow() -ne $h; $i++) {
  if ([W]::IsIconic($h)) { [W]::ShowWindow($h, 9) | Out-Null }
  [W]::keybd_event(0x12, 0, 0, [UIntPtr]::Zero); [W]::keybd_event(0x12, 0, 2, [UIntPtr]::Zero)  # alt: windows отдаёт фокус
  [W]::SetForegroundWindow($h) | Out-Null
  Start-Sleep -Milliseconds 150
}
if ([W]::GetForegroundWindow() -ne $h) { Write-Output 'NOFOCUS'; exit 1 }  # в чужое окно не вставляю
Add-Type -AssemblyName System.Windows.Forms
# печатаю буквами: ctrl+v в окне claude code — это вставка картинки, доходит только «v»
$k = [regex]::Replace(($t -replace '[\r\n]+', ' '), '[+^%%~(){}\[\]]', '{$0}')
[Windows.Forms.SendKeys]::SendWait($k); Start-Sleep -Milliseconds 300
[Windows.Forms.SendKeys]::SendWait('{ENTER}'); Start-Sleep -Milliseconds 300
Write-Output 'OK'
"""


def inject(text):
    b = base64.b64encode(text.encode()).decode()
    r = subprocess.run(["/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe", "-NoProfile", "-NonInteractive", "-Command", PS % b],
                       capture_output=True, text=True, timeout=30, cwd="/mnt/c")
    return r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip()[-200:]


def dictate(mic, first=""):
    """Говоришь сколько хочешь, в конце «делай» → уходит. «отмена» — выбросить. 20 с тишины — отбой."""
    parts = []
    pending = [first] if first else []
    for _ in range(40):
        if pending:
            s = pending.pop()
            log("  ·", s)
            if CANCEL.search(s):
                say("отмена"); return None
            m = DO.search(s)
            if m:
                return " ".join(s[:m.start()].split()).strip(" ,.") or None
            parts.append(s); continue
        raw = mic.segment(max_s=14, tail_s=1.3, wait_s=20)
        if raw is None:
            log(f"тишина, закрываю (фон {mic.noise:.0f}, порог {max(mic.noise*2.5,60):.0f})")
            if parts:
                say("отмена")
            return None
        s = stt(raw, "ggml-small.bin", "Диктовка по-русски, команда для ассистента. В конце: делай.")
        if not s:
            log(f"  · (пусто: {len(raw)/(RATE*2):.1f} с, пик {max(map(abs, array.array('h', raw)), default=0)}, фон {mic.noise:.0f})")
            continue
        log("  ·", s)
        if CANCEL.search(s):
            say("отмена"); return None
        m = DO.search(s)
        if m:
            parts.append(s[:m.start()])
            text = " ".join(" ".join(parts).split()).strip(" ,.")
            if not text:
                say("пусто")
            return text or None
        parts.append(s)
        mic.drain()
    return None


def main():
    prepare_phrases()
    servers = start_servers()
    import atexit; atexit.register(lambda: [p.kill() for p in servers])
    mic = Mic()
    for _ in range(17):
        mic.noise = 0.8 * mic.noise + 0.2 * level(mic.frame())
    log(f"слух включён, фон {mic.noise:.0f}")
    while True:
        raw = mic.segment(max_s=6, tail_s=0.5)
        dur = len(raw) / (RATE * 2)
        if dur < 0.25 or dur >= 5.9:  # щелчок или сплошной звук (музыка) — не зов
            continue
        if i_am_talking():  # это я сама говорю — себя не зову
            mic.drain(); continue
        heard = stt(raw, "ggml-base.bin", "Ада.", fast=True)
        mic.drain()
        wm = WAKE.search(heard or "")
        if not wm:
            continue
        log("позвали:", heard)
        rest = heard[wm.end():].strip(" ,.!?")  # «ада, открой браузер, делай» — одним духом
        lock = f"{H}/.local/state/ada/слушаю"
        open(lock, "w").close()  # пока диктуют, музыка не включается (music.sh это проверяет)
        try:
            ding()
            if not rest:
                say("привет")
            mic.drain()
            text = dictate(mic, rest)
        finally:
            os.remove(lock)
        if not text:
            log("отменено/пусто")
            if os.path.exists(f"{H}/.local/state/ada/думаю"):
                subprocess.run([f"{H}/ada/память/сердце/music.sh", "start"])
            mic.drain(); continue
        ding("дилинь-конец")
        r = inject(text)
        log("→ окно:", text, "|", r)
        if r != "OK":
            subprocess.run([f"{H}/ada/память/сердце/mouth.sh",
                            "не смогла вывести окно клода вперёд" if r == "NOFOCUS" else "окно клода не нашла"])
        mic.drain()


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt) as e:
        log("стоп:", e); sys.exit(1)
