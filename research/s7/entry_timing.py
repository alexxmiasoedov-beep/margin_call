"""Момент входа для корейского шорта: сразу на свече-триггере против задержки (15 мин … 2 ч) и условных входов в первые 6 ч
(первая свеча, закрывшаяся ниже триггера; откат на X% от максимума после триггера; новый максимум и закрытие ниже открытия).
Выход 7/20 и 10/25 с момента входа, 48 ч, фандинг и комиссия. Пропущенные (условие не наступило) — без сделки."""
import pickle, datetime
import numpy as np, pandas as pd
src = open("s6/feat.py").read()
exec(src.split("P = pd.read_pickle")[0])
exec("FX = {}" + src.split("FX = {}")[1].split("prev = {}")[0].split("def kr_arrays")[0])
D = pd.read_pickle("s6/feat.pkl"); Kr = D[D.kshare >= 0.2].copy()
Kr["score"] = ((Kr.pumps24 >= 16).astype(int) + (Kr.btc24 >= 0).astype(int) + (Kr.hi7 >= 0).astype(int) + (Kr.tb_pump <= 0.51).astype(int) + (Kr.kshare >= 0.4).astype(int))
def entry_variants(s, T):
    a = K[s]; t = a["t"]; j0 = int(np.searchsorted(t, T - 900)); c = a["c"].astype(np.float64); h = a["h"].astype(np.float64); o = a["o"].astype(np.float64)
    out = {}
    for d in (0, 1, 2, 4, 8): out[f"задержка {d * 15} мин"] = j0 + d
    W = range(j0 + 1, min(j0 + 25, len(t) - 200))
    out["первая свеча ниже триггера"] = next((j for j in W if c[j] < c[j0]), None)
    for x in (0.03, 0.05, 0.08):
        out[f"откат {x:.0%} от максимума после триггера"] = next((j for j in W if c[j] <= h[j0:j + 1].max() * (1 - x)), None)
    out["новый максимум и красная свеча"] = next((j for j in W if h[j] >= h[j0:j].max() and c[j] < o[j]), None)
    return out
rows = []
for x in Kr.itertuples():
    for nm, j in entry_variants(x.s, x.t).items():
        if j is None: rows.append(dict(v=nm, y=x.y, score=x.score, ok=False)); continue
        o = outcomes(x.s, int(j)); rows.append(dict(v=nm, y=x.y, score=x.score, ok=True, S_7_20=o.get("S_7_20"), S_10_25=o.get("S_10_25")))
R = pd.DataFrame(rows)
for col in ("S_7_20", "S_10_25"):
    print(f"\n{col}: корейский сигнал (1359 пампов) | счёт ≥ 3")
    for v, g in R.groupby("v", sort=False):
        e = g[g.ok]; e3 = e[e.score >= 3]
        print(f"  {v:42s} вход в {g.ok.mean():4.0%} | WR {(e[col]>0).mean():.1%} {e[col].mean()*100:+.2f}% (1-й {e[e.y==1][col].mean()*100:+.2f}, 2-й {e[e.y==2][col].mean()*100:+.2f})"
              f" | счёт ≥ 3: WR {(e3[col]>0).mean():.1%} {e3[col].mean()*100:+.2f}%")
