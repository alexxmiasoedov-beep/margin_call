"""Г6, зеркальная часть: лонг монет с наибольшим падением OI после каскада ликвидаций (Bian et al.: вынужденные
распродажи откатываются за 30–40 дней). Каскады — s22/h6_cascades.pkl (h6_cascade.py). OI в монетах есть по 50 самым
торгуемым перпам (s20/metrics). Вход — на закрытии первого часа после каскада.
  1) Рынок: медиана доходности всех фьючерсов за 1/3/7/14/30 суток после каскада против всех часов периода.
  2) Внутри топ-50: 10 монет с наибольшим падением OI за час до каскада против остальных — лонг к рынку.
t — по каскадам (их 16). Запуск из папки с данными."""
import sys
import numpy as np, pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common22 import GR, H, HSET, fwd
from h6_cascade import series

if __name__ == "__main__":
    C = pd.read_pickle("s22/h6_cascades.pkl")
    top = open("s22/top50.txt").read().split()
    S = {s: series(s) for s in top}
    g = GR["grid"]; MK = GR["MK"]
    t0, t1 = C.t.min() - 30 * 86400, C.t.max() + 1
    base = {h: np.nanmean(MK[h][(g >= t0) & (g <= t1)]) for h in HSET}
    print("1) Рынок (медиана всех фьючерсов, лонг) после каскада против всех часов периода:")
    rows = []
    for c in C.itertuples():
        T = int((c.t // H + 1) * H); k = int(np.searchsorted(g, T))
        rows.append({h: float(MK[h][k]) for h in HSET})
    R = pd.DataFrame(rows)
    for h in HSET:
        x = R[h].dropna()
        print(f"  {h // 24:2d} сут: после каскада {x.mean() * 100:+.2f}% (медиана {x.median() * 100:+.2f}%, в плюсе {(x > 0).mean():.0%}, "
              f"n={len(x)}), все часы {base[h] * 100:+.2f}%, разница t {(x.mean() - base[h]) / x.std() * np.sqrt(len(x)):+.1f}")
    print("\n2) Внутри топ-50: 10 монет с наибольшим падением OI за час до каскада, лонг к рынку, против остальных:")
    out = []
    for c in C.itertuples():
        T = int((c.t // H + 1) * H); d = {}
        for s, a in S.items():
            if a is None:
                continue
            i1 = np.searchsorted(a[:, 0], c.t, "right") - 1; i0 = np.searchsorted(a[:, 0], c.t - 3600, "right") - 1
            if i0 >= 0 and i1 >= 0 and c.t - a[i1, 0] <= 900 and a[i0, 1] > 0:
                d[s] = a[i1, 1] / a[i0, 1] - 1
        if len(d) < 20:
            continue
        rk = sorted(d, key=d.get)
        lo, rest = rk[:10], rk[10:]
        r = {"t": c.t}
        for h in (168, 336, 720):
            a1 = np.nanmean([-fwd(s, T, h) for s in lo]); a2 = np.nanmean([-fwd(s, T, h) for s in rest])
            r[f"top{h}"], r[f"rest{h}"] = a1, a2
        r["doi_top"], r["doi_rest"] = np.mean([d[s] for s in lo]), np.mean([d[s] for s in rest])
        out.append(r)
    O = pd.DataFrame(out)
    print(f"  каскадов с данными: {len(O)}; падение OI за час: у 10 худших {O.doi_top.mean() * 100:+.1f}%, у остальных {O.doi_rest.mean() * 100:+.1f}%")
    for h in (168, 336, 720):
        dif = O[f"top{h}"] - O[f"rest{h}"]
        print(f"  {h // 24:2d} сут: 10 с наибольшим падением OI {O[f'top{h}'].mean() * 100:+.2f}% к рынку, остальные "
              f"{O[f'rest{h}'].mean() * 100:+.2f}%; разница {dif.mean() * 100:+.2f}% (t {dif.mean() / dif.std() * np.sqrt(len(dif)):+.1f}, "
              f"в плюсе {(dif > 0).mean():.0%})")
