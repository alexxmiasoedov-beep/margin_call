"""Всплеск доли Bitvavo (× к обычной за сутки) в корейских пампах и внутри 🇰🇷⭐; кандидат в седьмое условие счёта."""
import numpy as np, pandas as pd
D = pd.read_pickle("s6/feat.pkl"); B = pd.read_pickle("s5/pump_bvv.pkl")
D["q"] = pd.to_datetime(D.t, unit="s").dt.to_period("Q").astype(str)
Kr = D[D.kshare >= 0.2].merge(B[["s", "t", "has", "share", "norm", "x"]], on=["s", "t"], how="left")
Kr["s6"] = ((Kr.pumps24 >= 16).astype(int) + (Kr.btc24 >= 0).astype(int) + (Kr.hi7 >= 0).astype(int) + (Kr.tb_pump <= 0.51).astype(int)
            + (Kr.kshare >= 0.4).astype(int) + (Kr.dow == 6).astype(int))
Kr["bx"] = Kr.x.where(Kr.has == True)
def st(g, col):
    y1, y2 = g[g.y == 1], g[g.y == 2]
    return (f"{len(g):4d} WR {(g[col] > 0).mean():.1%} {g[col].mean() * 100:+.2f}% (1-й {(y1[col] > 0).mean():.1%} {y1[col].mean() * 100:+.2f}, "
            f"2-й {(y2[col] > 0).mean():.1%} {y2[col].mean() * 100:+.2f})")
for col in ("S_10_25", "S_7_20"):
    print(f"=== {col}: все корейские пампы")
    print(f"  {'нет пары на Bitvavo':30s}", st(Kr[Kr.bx.isna()], col))
    for lo, hi in ((0, 1), (1, 2), (2, 4), (4, 8), (8, 1e9)):
        print(f"  {f'× {lo:g}–{hi:g}':30s}", st(Kr[(Kr.bx >= lo) & (Kr.bx < hi)], col))
    for k in (2, 3, 4):
        print(f"  {f'× ≥ {k}':30s}", st(Kr[Kr.bx >= k], col), "| остальные", st(Kr[~(Kr.bx >= k)], col))
    print(f"=== {col}: внутри счёта из 6")
    for sc in (0, 1, 2, 3, 4, 5):
        g = Kr[Kr.s6 == sc] if sc < 5 else Kr[Kr.s6 >= 5]
        print(f"  счёт {sc}{'+' if sc == 5 else ''}: всплеск ≥ 4", st(g[g.bx >= 4], col), "| нет", st(g[~(g.bx >= 4)], col))
print("=== седьмое условие «всплеск Bitvavo ≥ ×k», шорт 7/20 (как в 🇰🇷⭐)")
col = "S_7_20"
def full(nm, g):
    qm = g.groupby("q")[col].mean()
    print(f"  {nm:34s}", st(g, col), f"| кварталов в плюсе {(qm > 0).sum()}/{len(qm)}, итог {g[col].sum() * 10:+.1f} USDT")
full("счёт из 6 ≥ 3 (сейчас)", Kr[Kr.s6 >= 3])
for k in (2, 3, 4):
    s7 = Kr.s6 + (Kr.bx >= k).astype(int)
    full(f"счёт из 7 ≥ 3, всплеск ≥ ×{k}", Kr[s7 >= 3]); full(f"   добавятся (счёт 6 = 2)", Kr[(Kr.s6 == 2) & (Kr.bx >= k)])
    full(f"счёт из 7 ≥ 4, всплеск ≥ ×{k}", Kr[s7 >= 4])
print("=== по кварталам: все корейские, всплеск ≥ 4 против остальных (7/20, на сделку)")
a = Kr[Kr.bx >= 4].groupby("q")[col].agg(["size", "mean"]); b = Kr[~(Kr.bx >= 4)].groupby("q")[col].agg(["size", "mean"])
print(pd.concat([a, b], axis=1, keys=["всплеск", "остальные"]).round(4).to_string())
print("=== турецкие пампы (доля лиры ≥ 10%), шорт 10/25, по всплеску Bitvavo")
T = D.merge(B[["s", "t", "has", "x", "fshare", "fhas"]].rename(columns={"fshare": "fs", "fhas": "fh"}), on=["s", "t"], how="inner")
T = T[(T.fh == True) & (T.fs >= 0.1) & (T.has == True)]
for lo, hi in ((0, 2), (2, 4), (4, 1e9)):
    print(f"  × {lo:g}–{hi:g}", st(T[(T.x >= lo) & (T.x < hi)], "S_10_25"))
