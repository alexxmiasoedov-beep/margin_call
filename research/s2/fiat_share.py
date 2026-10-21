"""Доля фиатной (по умолчанию турецкой) спотовой торговли Binance в объёме за час на момент пампа; шорт 10/25/48 ч по группам."""
import pickle, sys, datetime
import numpy as np, pandas as pd
Q = sys.argv[1] if len(sys.argv) > 1 else "TRY"
X = pickle.load(open(f"s2/fiat_{Q}.pkl", "rb")); pairs, D = X["pairs"], X["D"]; fx = D[f"USDT{Q}"]
EV = pickle.load(open("mm2/pumps2y.pkl", "rb"))["EV"]; R = pickle.load(open("mm2/bt2y.pkl", "rb"))
rows = []
for e, r in zip(EV, R):
    s = e["s"]; w = e["w"]; j = e["j"]; T = e["t_in"]
    fut = w[j - 3:j + 1, 4].sum()
    f_usd = np.nan
    if s in pairs and f"{pairs[s]}{Q}" in D:
        a = D[f"{pairs[s]}{Q}"]; m = (a[:, 0] >= T - 3600) & (a[:, 0] < T)
        if (a[:, 0] < T - 3600).any():                                  # пара уже торговалась до пампа
            rate = np.interp(a[m, 0], fx[:, 0], fx[:, 1]) if m.any() else np.array([])
            f_usd = float((a[m, 2] / rate).sum()) if m.any() else 0.0
    rows.append(dict(s=s, t=T, korea=r["korea"], kshare=r["share"], pnl=r["pnl_10"], fut=fut, fiat=f_usd))
P = pd.DataFrame(rows); P["has"] = P.fiat.notna(); P["fshare"] = P.fiat / (P.fiat + P.fut)
P["year"] = np.where(P.t < datetime.datetime(2025, 10, 1, tzinfo=datetime.timezone.utc).timestamp(), "1-й год", "2-й год")
P.to_pickle(f"s2/pump_{Q}.pkl")
def show(name, m):
    d = P[m]; y = d.groupby("year").pnl.mean() * 100
    print(f"{name:52s} {len(d):5d} | шорт {d.pnl.mean() * 100:+.2f}% | 1-й год {y.get('1-й год', np.nan):+.2f}% ({(d.year == '1-й год').sum()}) | 2-й год {y.get('2-й год', np.nan):+.2f}% ({(d.year == '2-й год').sum()})")
print(f"=== {Q}: пампы, у которых есть пара к {Q}: {P.has.sum()} из {len(P)}")
show("все пампы", P.has | ~P.has)
show(f"есть пара к {Q}", P.has); show(f"нет пары к {Q}", ~P.has)
for lo, hi in ((0, 0.002), (0.002, 0.01), (0.01, 0.03), (0.03, 0.06), (0.06, 1)):
    show(f"доля {Q} {lo:.1%}–{hi:.1%}", P.has & (P.fshare >= lo) & (P.fshare < hi))
print("--- монеты без Кореи:")
N = ~P.korea
for lo, hi in ((0, 0.002), (0.002, 0.01), (0.01, 0.03), (0.03, 1)):
    show(f"не в Корее, доля {Q} {lo:.1%}–{hi:.1%}", N & P.has & (P.fshare >= lo) & (P.fshare < hi))
print("--- монеты в Корее, доля Кореи < 20% (корейский шорт не сработал бы):")
for lo, hi in ((0, 0.01), (0.01, 0.03), (0.03, 1)):
    show(f"Корея < 20%, доля {Q} {lo:.1%}–{hi:.1%}", P.korea & (P.kshare < 0.2) & P.has & (P.fshare >= lo) & (P.fshare < hi))
