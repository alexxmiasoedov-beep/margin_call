"""bookDepth фьючерса Binance (снимки ~30 с, накопленный объём стакана на ±1…±5%) → 15-мин ряды: для каждой глубины d средние
за свечу биды и аски в $ и последний снимок; файлы удаляются после свёртки. s9/bd/<SYM>.npz"""
import subprocess, io, zipfile, os, sys, datetime
import numpy as np
from concurrent.futures import ThreadPoolExecutor
SYM = sys.argv[1]; D0 = datetime.date(2024, 10, 15); D1 = datetime.date(2026, 10, 20)
os.makedirs("s9/bd", exist_ok=True)
def day(d):
    u = f"https://data.binance.vision/data/futures/um/daily/bookDepth/{SYM}/{SYM}-bookDepth-{d}.zip"
    for k in range(4):
        r = subprocess.run(["curl", "-sS", "-m", "90", "-w", "%{http_code}", "-o", "-", u], capture_output=True)
        code = r.stdout[-3:].decode(errors="ignore"); body = r.stdout[:-3]
        if code == "200":
            try:
                z = zipfile.ZipFile(io.BytesIO(body)); txt = z.read(z.namelist()[0]).decode()
            except Exception: continue
            rows = {}
            for ln in txt.splitlines()[1:]:
                p = ln.split(",")
                if len(p) < 4: continue
                try: ts = datetime.datetime.strptime(p[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc).timestamp()
                except ValueError: continue
                rows.setdefault(int(ts), {})[int(float(p[1]))] = float(p[3])
            out = []
            for ts, dd in rows.items():
                if all(k in dd for k in (-5, -4, -3, -2, -1, 1, 2, 3, 4, 5)):
                    out.append([ts] + [dd[-k] for k in (1, 2, 3, 4, 5)] + [dd[k] for k in (1, 2, 3, 4, 5)])
            return np.array(out) if out else None
        if code == "404": return None
    return None
days = [D0 + datetime.timedelta(n) for n in range((D1 - D0).days + 1)]
res = []
with ThreadPoolExecutor(6) as ex:
    for i, a in enumerate(ex.map(day, days)):
        if a is not None: res.append(a)
        if i % 60 == 0: print(SYM, days[i], len(res), flush=True)
A = np.concatenate(res); A = A[np.argsort(A[:, 0])]
# 15-мин свёртка: среднее и последний снимок
b = (A[:, 0] // 900).astype(np.int64)
ub, idx = np.unique(b, return_index=True); ends = np.r_[idx[1:], len(A)]
mean = np.add.reduceat(A[:, 1:], idx, axis=0) / (ends - idx)[:, None]; last = A[ends - 1, 1:]
np.savez_compressed(f"s9/bd/{SYM}.npz", t=ub * 900, mean=mean, last=last, n=(ends - idx))
print(SYM, "готово", len(ub), "свечей", flush=True)
