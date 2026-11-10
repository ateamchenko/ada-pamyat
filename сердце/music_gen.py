#!/usr/bin/env python3
"""Своя музыка ожидания: тихий эмбиент-луп, сочинён кодом, ничей не чужой.
Пишет ~/.local/share/ada/музыка.wav (≈16 с, бесшовно)."""
import array, math, os, random, wave

R = 22050
BPM = 90
beat = 60 / BPM
bars = [  # am - f - c - g, по 4 доли
    [57, 60, 64], [53, 57, 60], [48, 55, 60], [55, 59, 62],
]
hz = lambda n: 440 * 2 ** ((n - 69) / 12)
n_total = int(R * beat * 4 * len(bars))
buf = [0.0] * n_total
random.seed(43 * 36)


def add(f, t0, dur, amp, attack=0.02, rel=None, harm=(1, 0.3, 0.1)):
    s0, n = int(t0 * R), int(dur * R)
    rel = rel or dur * 0.6
    for i in range(n):
        t = i / R
        env = min(1, t / attack) * (math.exp(-(t - (dur - rel)) * 5 / rel) if t > dur - rel else 1)
        v = sum(a * math.sin(2 * math.pi * f * k * t) for k, a in enumerate(harm, 1))
        buf[(s0 + i) % n_total] += amp * env * v


for b, chord in enumerate(bars):
    t = b * beat * 4
    for n in chord:  # пэд
        add(hz(n - 12), t, beat * 4.4, 0.05, attack=0.6, rel=1.5, harm=(1, 0.15))
    add(hz(chord[0] - 24), t, beat * 4, 0.09, attack=0.05, harm=(1, 0.5))  # бас
    for k in range(8):  # арпеджио восьмыми
        n = random.choice(chord) + random.choice((12, 12, 24))
        add(hz(n), t + k * beat / 2, beat * 0.9, 0.035 if k % 2 else 0.05, attack=0.005, rel=0.4, harm=(1, 0.2, 0.05))

peak = max(abs(x) for x in buf) or 1
a = array.array("h", (int(x / peak * 9000) for x in buf))
out = os.path.expanduser("~/.local/share/ada/музыка.wav")
with wave.open(out, "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(R); w.writeframes(a.tobytes())
print(out)
