"""Откуп в коридоре, падение в «собственных сигмах»: z = доходность за 4 ч / σ 4-часовых доходностей монеты за 7 суток до движения.
Сетка VR × z × падение: итог лонга (тейк 10 / стоп 15 / 48 ч) отдельно на 1-м и 2-м году."""
import pickle, datetime, itertools
import numpy as np, pandas as pd
exec(open("s3/vr_long.py").read().split('if __name__ == "__main__":')[0])
CUT = datetime.datetime(2025, 10, 1, tzinfo=UTC).timestamp()
SIG = {}
for s, a in K.items():
    if s not in PRE: continue
    c = a["c"].astype(np.float64); n = len(c); r16 = np.zeros(n); r16[16:] = np.log(c[16:] / c[:-16]); W = 672
    p1, p2 = roll(r16, W - 15), roll(r16 * r16, W - 15); SIG[s] = np.sqrt(np.maximum((p2 - p1 ** 2 / (W - 15)) / (W - 16), 1e-12))
rows = []
for s, (vr16, mv, v24) in PRE.items():
    t = K[s]["t"]; last = -10**9; sg = SIG[s]
    for j in np.flatnonzero((mv <= -0.05) & (mv > -0.5)):
        if j < 700 or j + 2 >= len(t) or j - last < 96 or v24[j] < 3e6: continue
        last = j; z = np.log(1 + mv[j]) / sg[j - 16]
        rows.append((s, int(j), vr16[j - 16], z, mv[j]))
E = pd.DataFrame(rows, columns=["s", "j", "vr", "z", "mv"])
E["p"] = [trade(s, j, 0.10, 0.15, 192)[1] for s, j in zip(E.s, E.j)]; E["t"] = [K[s]["t"][j] + 900 for s, j in zip(E.s, E.j)]
E["y"] = np.where(E.t < CUT, 1, 2); E.to_pickle("s3/vr_z.pkl")
print(f"всех падений ≥ 5% за 4 ч: {len(E)}; лонг 10/15/48 в среднем {E.p.mean() * 100:+.2f}% (1-й год {E[E.y == 1].p.mean() * 100:+.2f}, 2-й {E[E.y == 2].p.mean() * 100:+.2f})")
G = []
for vr_max, z_max, drop in itertools.product((0.6, 0.7, 0.8, 0.9, 9), (-2, -3, -4, -5, -6), (0.05, 0.08)):
    m = (E.vr <= vr_max) & (E.z <= z_max) & (E.mv <= -drop)
    a1, a2 = E[m & (E.y == 1)].p, E[m & (E.y == 2)].p
    if len(a1) >= 150: G.append((vr_max, z_max, drop, len(a1), a1.mean() * 100, len(a2), a2.mean() * 100))
G = pd.DataFrame(G, columns=["VR ≤", "z ≤", "падение ≥", "n1", "1-й год %", "n2", "2-й год %"]).sort_values("1-й год %", ascending=False)
pd.set_option("display.width", 200); print(G.head(15).round(2).to_string(index=False))
print(f"\nвсего вариантов {len(G)}; 2-й год в плюсе у {(G['2-й год %'] > 0).sum()}; корреляция рангов годов {G['1-й год %'].rank().corr(G['2-й год %'].rank()):.2f}")
