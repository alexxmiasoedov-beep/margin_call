"""s193 — устойчивость эталона CoW (`cow_flow.pkl`): по ордерам — медиана избытка, доля ордеров с избытком > 0,
избыток в «нормальных» 12-с потоках (z к разбросу плацебо), разбивка по крупности части к обороту Binance
и по шагу ордера. Только потоки тейкеров, без цен."""
import numpy as np
import pandas as pd

D = "/home/user/mc_data/s193"
WIN = [(-300, -60), (-60, 0), (0, 12), (12, 60), (60, 300)]


def main():
    X = pd.read_pickle(f"{D}/cow_flow.pkl")
    R = X["flows"]
    for mkt in ("spot", "um"):
        x = R[R.mkt == mkt].copy()
        print(f"\n== {mkt}: по ордерам (кластер), окно — избыток чистых продаж к плацебо / сумма части ==")
        for k, (a, b) in enumerate(WIN):
            x["ex"] = (x[f"ev{k}"] - x[f"pl{k}"]) / x.part_usd
            g = x.groupby("owner").ex.mean()
            gm = x.groupby("owner").ex.median()
            w = x.groupby("owner").apply(lambda z: np.sum(z[f"ev{k}"] - z[f"pl{k}"]) / np.sum(z.part_usd))
            tw = w.mean() / (w.std(ddof=1) / np.sqrt(len(w)))
            print(f"  [{a:+4d}, {b:+4d}) с: среднее ордеров {g.mean():+.3f}, медиана ордеров {gm.median():+.3f}, "
                  f"ордеров с избытком > 0 {np.mean(g > 0):.0%}; взвешенно по сумме {w.mean():+.3f} (t {tw:.2f}, n {len(w)})")
        # разбивка по шагу ордера и крупности части к обороту
        k = 2
        x["ex"] = (x[f"ev{k}"] - x[f"pl{k}"]) / x.part_usd
        g = x.groupby("owner").agg(ex=("ex", "mean"), sec=("sec", "first"), part=("part_usd", "median"))
        g["big"] = g.part >= g.part.median()
        for lab, y in (("крупная часть", g[g.big]), ("мелкая часть", g[~g.big]), ("шаг ≤ 10 мин", g[g.sec <= 600]),
                       ("шаг > 10 мин", g[g.sec > 600])):
            t = y.ex.mean() / (y.ex.std(ddof=1) / np.sqrt(len(y))) if len(y) > 2 else np.nan
            print(f"  [0, 12) с, {lab}: {y.ex.mean():+.3f} (t {t:.2f}, n {len(y)})")
    print("\nисполнений с лентой:", len(R), "ордеров:", R.owner.nunique(), "сутки Binance:",
          R.assign(d=(R.tau // 86400)).groupby(["mkt", "sym", "d"]).ngroups)


if __name__ == "__main__":
    main()
