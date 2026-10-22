"""Стакан фьючерса (bookDepth, накопленный объём на ±1…5%) за сутки до входа для каждой позиции шорт-корзины фактора займа:
имбаланс (B−A)/(B+A) на 1/3/5% — среднее за сутки и за последние 6 ч, глубина 3% в $ к суточному объёму. Файлы не кэшируются.
Выход: s10/bd_basket.pkl"""
import subprocess, io, zipfile, datetime, sys, os
import numpy as np, pandas as pd
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, os.getcwd())
D = pd.read_pickle("s10/daily_panel.pkl")
d = D[(D.v >= 10e6) & D.ret7.notna()].copy()
pool = d[(d.sh7 > 0) & ~(d.f0 < -0.001)]
top = pool.assign(rr=pool.groupby("T").sh7.rank(ascending=False, method="first")).query("rr <= 10")
jobs = [(s, int(T)) for s, T in zip(top.s, top["T"])]
print("позиций", len(jobs), flush=True)
def one(job):
    s, T = job; day = datetime.datetime.utcfromtimestamp(T - 86400).date()
    u = f"https://data.binance.vision/data/futures/um/daily/bookDepth/{s}USDT/{s}USDT-bookDepth-{day}.zip"
    for k in range(3):
        r = subprocess.run(["curl", "-sS", "-m", "90", "-w", "%{http_code}", "-o", "-", u], capture_output=True)
        code = r.stdout[-3:].decode(errors="ignore"); body = r.stdout[:-3]
        if code == "404": return dict(s=s, T=T, ok=0)
        if code != "200": continue
        try: txt = zipfile.ZipFile(io.BytesIO(body)).read(zipfile.ZipFile(io.BytesIO(body)).namelist()[0]).decode()
        except Exception: continue
        df = pd.read_csv(io.StringIO(txt))
        if df.shape[1] < 4: return dict(s=s, T=T, ok=0)
        df = df.iloc[:, :4]; df.columns = ["ts", "pct", "depth", "notional"]
        df["ts"] = (pd.to_datetime(df["ts"], format="%Y-%m-%d %H:%M:%S", errors="coerce") - pd.Timestamp("1970-01-01")) // pd.Timedelta("1s")
        df["pct"] = df["pct"].round().astype(int)
        pv = df.pivot_table(index="ts", columns="pct", values="notional", aggfunc="last")
        need = [-5, -3, -1, 1, 3, 5]
        if not all(k in pv.columns for k in need): return dict(s=s, T=T, ok=0)
        pv = pv[need].dropna()
        A = np.column_stack([pv.index.values, pv[-1].values, pv[-3].values, pv[-5].values, pv[1].values, pv[3].values, pv[5].values]).astype(float)
        if len(A) < 100: return dict(s=s, T=T, ok=0)
        A = A[np.argsort(A[:, 0])]
        imb = (A[:, 1:4] - A[:, 4:7]) / (A[:, 1:4] + A[:, 4:7])
        last = A[:, 0] >= A[-1, 0] - 6 * 3600
        return dict(s=s, T=T, ok=1, imb1=imb[:, 0].mean(), imb3=imb[:, 1].mean(), imb5=imb[:, 2].mean(),
                    imb3_6h=imb[last, 1].mean(), imb3_first=imb[A[:, 0] < A[0, 0] + 6 * 3600, 1].mean(),
                    b3=A[:, 2].mean(), a3=A[:, 5].mean(), n=len(A))
    return dict(s=s, T=T, ok=-1)
out = []
with ProcessPoolExecutor(6) as ex:
    for i, r in enumerate(ex.map(one, jobs, chunksize=4)):
        out.append(r)
        if i % 250 == 0: print(datetime.datetime.now().strftime("%H:%M:%S"), i, sum(x["ok"] == 1 for x in out), flush=True)
pd.DataFrame(out).to_pickle("s10/bd_basket.pkl"); print("готово", len(out), sum(x["ok"] == 1 for x in out), flush=True)
