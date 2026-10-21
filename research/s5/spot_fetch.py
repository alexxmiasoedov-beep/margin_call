"""Спот Binance к USDT: 15-мин свечи за 09.2024–18.10.2026 для всех монет с фьючерсом → s5/spot/<пара>.npy
(t, закрытие, объём в $, покупки тейкеров в $, сделок). Архив data.binance.vision, zip не сохраняется."""
import io, zipfile, subprocess, pickle, re, os, datetime
import numpy as np
from concurrent.futures import ThreadPoolExecutor
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
K = pickle.load(open("s2/k2y.pkl", "rb")); syms = set(open("s2/spot_syms.txt").read().split())
pairs = sorted({f"{n}USDT" for s in K for n in (s, strip(s)) if f"{n}USDT" in syms})
MONTHS = [f"{y}-{m:02d}" for y in (2024, 2025, 2026) for m in range(1, 13) if "2024-09" <= f"{y}-{m:02d}" <= "2026-09"]
DAYS = [f"2026-10-{d:02d}" for d in range(1, 19)]
B = "https://data.binance.vision/data/spot"
def get(url):
    for k in range(4):
        r = subprocess.run(["curl", "-sS", "-m", "90", "-w", "%{http_code}", "-o", "-", url], capture_output=True)
        code = r.stdout[-3:].decode(errors="replace"); body = r.stdout[:-3]
        if code == "200": return body
        if code == "404": return None
    return None
def parse(body):
    out = []
    if not body: return out
    z = zipfile.ZipFile(io.BytesIO(body))
    for ln in z.read(z.namelist()[0]).decode().splitlines():
        p = ln.split(",")
        if not p[0][:1].isdigit(): continue
        t = int(p[0]); t = t // 1000000 if t > 10**14 else t // 1000
        out.append((t, float(p[4]), float(p[7]), float(p[10]), float(p[8])))
    return out
def job(pair):
    fn = f"s5/spot/{pair}.npy"
    if os.path.exists(fn): return pair, -1
    rows = []
    for m in MONTHS: rows += parse(get(f"{B}/monthly/klines/{pair}/15m/{pair}-15m-{m}.zip"))
    for d in DAYS: rows += parse(get(f"{B}/daily/klines/{pair}/15m/{pair}-15m-{d}.zip"))
    a = np.array(sorted(set(rows)), dtype=np.float64) if rows else np.zeros((0, 5)); np.save(fn, a); return pair, len(a)
print(len(pairs), "пар", flush=True)
with ThreadPoolExecutor(16) as ex:
    for i, (p, n) in enumerate(ex.map(job, pairs)):
        if i % 25 == 0: print(i, p, n, flush=True)
print("готово", flush=True)
