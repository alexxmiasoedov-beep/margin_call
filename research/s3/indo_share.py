"""Доля индонезийской розницы (Indodax, рупия) в объёме за час на момент пампа; шорт 10/25/48 ч по группам, по годам;
отдельно — пампы, где не срабатывают ни корейский шорт (доля Кореи < 20%), ни турецкий набег (доля лиры < 10%)."""
import pickle, re, os, glob, datetime
import numpy as np, pandas as pd
EV = pickle.load(open("mm2/pumps2y.pkl", "rb"))["EV"]; R = pickle.load(open("mm2/bt2y.pkl", "rb")); TR = pd.read_pickle("s2/pump_TRY.pkl")
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
fx = np.vstack([np.load(f) for f in glob.glob("s3/indo/USDTIDR_*.npy") if os.path.getsize(f) > 200]); fx = fx[np.argsort(fx[:, 0])]
rows = []
for e, r, tr in zip(EV, R, TR.itertuples()):
    fn = f"s3/indo/{strip(e['s'])}_{int(e['t_in'])}.npy"; T = e["t_in"]; w, j = e["w"], e["j"]; fut = w[j - 3:j + 1, 4].sum()
    ish = np.nan
    if os.path.exists(fn):
        a = np.load(fn)
        if len(a) and (a[:, 0] < T - 86400).any():                       # пара торговалась хотя бы сутки до пампа
            m = (a[:, 0] >= T - 3600) & (a[:, 0] < T)
            usd = float((a[m, 1] * a[m, 2] / np.interp(a[m, 0], fx[:, 0], fx[:, 1])).sum()) if m.any() else 0.0
            ish = usd / (usd + fut) if usd + fut > 0 else 0.0
    rows.append(dict(s=e["s"], t=T, pnl=r["pnl_10"], korea=r["korea"], kshare=r["share"], tshare=tr.fshare, ishare=ish))
D = pd.DataFrame(rows); D["year"] = np.where(D.t < datetime.datetime(2025, 10, 1, tzinfo=datetime.timezone.utc).timestamp(), "1-й год", "2-й год")
D.to_pickle("s3/pump_IDR.pkl")
def show(name, m):
    d = D[m]; y = d.groupby("year").pnl.mean() * 100
    print(f"{name:58s} {len(d):5d} | шорт {d.pnl.mean() * 100:+.2f}% | 1-й год {y.get('1-й год', np.nan):+.2f}% ({(d.year == '1-й год').sum()}) | 2-й год {y.get('2-й год', np.nan):+.2f}% ({(d.year == '2-й год').sum()})")
has = D.ishare.notna()
print(f"пампов с данными Indodax: {has.sum()} из {len(D)}")
show("есть пара на Indodax", has); show("нет пары на Indodax", ~has)
for lo, hi in ((0, 0.005), (0.005, 0.02), (0.02, 0.05), (0.05, 0.1), (0.1, 1)):
    show(f"доля Индонезии {lo:.1%}–{hi:.1%}", has & (D.ishare >= lo) & (D.ishare < hi))
other = ~(D.korea & (D.kshare >= 0.2)) & ~(D.tshare >= 0.1)
print("--- пампы, где не срабатывают корейский и турецкий сигналы:")
for lo, hi in ((0, 0.02), (0.02, 0.05), (0.05, 1)):
    show(f"доля Индонезии {lo:.0%}–{hi:.0%}", other & has & (D.ishare >= lo) & (D.ishare < hi))
