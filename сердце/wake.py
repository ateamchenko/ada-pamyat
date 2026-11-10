#!/usr/bin/env python3
"""Слух всегда: жду «слушай ада» → дилинь → пишу, пока не скажут «стоп» → дилинь →
вставляю текст в окно claude (windows terminal, заголовок начинается со значка: ✳ или крутилка) и жму enter.
«отмена» вместо «стоп» — выбросить. Звук не хранится; whisper зовётся только когда громко.
Сервис: systemctl --user {start|stop} ada-ears"""
import array, base64, math, os, re, subprocess, sys, tempfile, time, wave

H = os.path.expanduser("~")
D = f"{H}/.local/share/ada"
M = f"{D}/models"
RATE, FRAME = 16000, 480  # 30 мс
WAKE = re.compile(r"(слуш\w*|послуш\w*)\W*(ада|ода|адам?|ад|адя|оды?|да)\b|\bада\W+слуш", re.I)
STOP = re.compile(r"\W*\b(стоп|стоб|stop)\W*$", re.I)
CANCEL = re.compile(r"\bотмен\w*\W*$", re.I)


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
        while True:
            f = self.frame(); n += 1; lv = level(f)
            thr = max(self.noise * 2.5, 60)
            hot = lv > thr
            if not started:
                if not hot:
                    self.noise = 0.98 * self.noise + 0.02 * lv  # фон плавает — слежу
                pre = (pre + [f])[-10:]
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


def stt(raw, model, prompt):
    a = array.array("h", raw)
    peak = max(map(abs, a), default=0) or 1
    g = min(23000 / peak, 40)
    a = array.array("h", (max(-32768, min(32767, int(x * g))) for x in a))
    with tempfile.NamedTemporaryFile(suffix=".wav") as t:
        with wave.open(t.name, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(a.tobytes())
        out = subprocess.run([f"{H}/.local/bin/whisper-cli", "-m", f"{M}/{model}", "-l", "ru",
                              "-t", str(os.cpu_count()), "-nt", "-np", "-sns", "--vad",
                              "-vm", f"{M}/ggml-silero-v6.2.0.bin", "--prompt", prompt, "-f", t.name],
                             capture_output=True, text=True).stdout
    return " ".join(out.split()).strip()


def ding(name="дилинь"):
    subprocess.run(["paplay", f"{D}/{name}.wav"], stderr=subprocess.DEVNULL)


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
$old = Get-Clipboard -Raw -ErrorAction SilentlyContinue
Set-Clipboard -Value $t
Start-Sleep -Milliseconds 100
Add-Type -AssemblyName System.Windows.Forms
[Windows.Forms.SendKeys]::SendWait('^v'); Start-Sleep -Milliseconds 300
[Windows.Forms.SendKeys]::SendWait('{ENTER}'); Start-Sleep -Milliseconds 300
if ($old) { Set-Clipboard -Value $old }
Write-Output 'OK'
"""


def inject(text):
    b = base64.b64encode(text.encode()).decode()
    r = subprocess.run(["/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe", "-NoProfile", "-NonInteractive", "-Command", PS % b],
                       capture_output=True, text=True, timeout=30, cwd="/mnt/c")
    return r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip()[-200:]


def dictate(mic):
    parts, t0 = [], time.time()
    while time.time() - t0 < 120:
        raw = mic.segment(max_s=25, tail_s=1.0, wait_s=20)
        if raw is None:
            log("тишина 20 с, закрываю"); break
        s = stt(raw, "ggml-small.bin", "Диктовка по-русски, команда для ассистента. В конце «стоп».")
        if not s:
            continue
        log("  ·", s)
        if CANCEL.search(s):
            return None
        if STOP.search(s):
            parts.append(STOP.sub("", s)); break
        parts.append(s)
    return " ".join(p for p in parts if p).strip()


def main():
    mic = Mic()
    for _ in range(17):
        mic.noise = 0.8 * mic.noise + 0.2 * level(mic.frame())
    log(f"слух включён, фон {mic.noise:.0f}")
    while True:
        raw = mic.segment(max_s=3.5, tail_s=0.6)
        dur = len(raw) / (RATE * 2)
        if dur < 0.4 or dur >= 3.4:  # щелчок или сплошной звук (музыка) — не зов
            continue
        heard = stt(raw, "ggml-base.bin", "Слушай, Ада.")
        mic.drain()
        if not heard or not WAKE.search(heard):
            continue
        log("позвали:", heard)
        ding()
        mic.drain()
        text = dictate(mic)
        ding("дилинь-конец")
        if not text:
            log("отменено/пусто"); mic.drain(); continue
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
