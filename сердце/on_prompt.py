#!/usr/bin/env python3
"""UserPromptSubmit-хук: задачу получила → коротко «ага» голосом → музыка, пока думаю.
Хук отвечает мгновенно, всё звуковое — в фоне."""
import os, random, subprocess, sys

H = os.path.expanduser("~")
S = f"{H}/.local/state/ada"
if os.path.exists(f"{S}/немая"):
    sys.exit(0)
os.makedirs(S, exist_ok=True)
open(f"{S}/думаю", "w").close()
ack = random.choice(["ага, щас", "принято", "поняла, делаю", "щас гляну", "окей, погнали", "секунду"])
subprocess.Popen([f"{H}/ada/память/сердце/mouth.sh", ack], start_new_session=True,
                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
