"""Пробуждение спящей монеты: вход с задержкой D часов после первого срабатывания (цена на входе — какая будет)."""
import numpy as np, pandas as pd
exec(open("s2/explode.py").read().split('if __name__ == "__main__":')[0])
res = []
for X, lo, hi in ((20, 0.1, 0.3), (30, 0.1, 0.3), (30, 0.05, 0.15), (50, 0.1, 0.3), (20, 0.05, 0.4), (30, 0.05, 0.4)):
    ev = events(X, lo, hi)
    for D in (0, 1, 2, 4, 6, 8, 12):
        ev2 = [(s, j + D * 4) for s, j in ev if j + D * 4 + 2 < len(K[s]["t"])]
        d = table(ev2, 0.1, 0.15, 96); qm = d.groupby("q").p.mean()
        res.append((X, f"{lo:.0%}–{hi:.0%}", D, len(d), round(d.p.mean() * 100, 2), round((d.p > 0).mean() * 100), f"{(qm > 0).sum()}/{len(qm)}",
                    " ".join(f"{k[2:]}:{v * 100:+.1f}" for k, v in qm.items())))
pd.set_option("display.width", 300)
print(pd.DataFrame(res, columns=["объём ×", "рост", "задержка, ч", "сделок", "итог %", "в плюсе %", "кв.+", "по кварталам"]).to_string(index=False))
