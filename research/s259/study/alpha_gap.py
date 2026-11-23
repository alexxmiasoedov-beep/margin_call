"""s259, вопрос 1 (Alpha) — разрыв цены перпа без спота и цены Binance Alpha (часовые свечи Alpha s256/alpha, закрытие часа,
против закрытия 15-мин свечи перпа на конце того же часа): величина, частота, кто закрывает (error-correction за 1 ч).
Только часы без спота Binance и с оборотом Alpha > 0. Механика, не сделки.
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s259/study/alpha_gap.py"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common259 import BAR, DAY, OUT, T0, T1, load_k  # noqa: E402


def main():
    K = load_k()
    U = json.load(open(f"{OUT}/universe.json"))
    rows = []
    for path in sorted(glob.glob("s256/alpha/*.json")):
        s = os.path.basename(path)[:-5]
        if s not in U or s not in K:
            continue
        A = json.load(open(path))
        if not A.get("k"):
            continue
        k = np.array(A["k"], float)
        H = (k[:, 0] // 1000).astype(np.int64) + 3600                      # конец часа
        a = K[s]; t = a["t"].astype(np.int64) + BAR
        i = np.searchsorted(t, H); i2 = np.minimum(i, len(t) - 1)
        ok = (i < len(t)) & (t[i2] == H) & (k[:, 2] > 0) & (a["qv"][i2] > 0) & (H >= T0) & (H < T1)
        s0 = U[s]["spot0"] or np.inf
        ok &= H < s0
        if ok.sum() < 48:
            continue
        pc = a["c"][i2[ok]].astype(float); ac = k[ok, 1]
        mult = np.exp(np.round(np.log10(np.median(pc / ac))) * np.log(10))   # 1000X: цена перпа = 1000 · цена токена
        g = np.log(pc / (ac * mult))
        rows.append(pd.DataFrame({"s": s, "H": H[ok], "g": g, "lp": np.log(pc), "la": np.log(ac * mult),
                                  "share": k[ok, 2] / (k[ok, 2] + 0), "av": k[ok, 2],
                                  "self": U[s].get("self", np.nan), "alpha_w": U[s].get("alpha", np.nan), "snap": U[s]["snap"]}))
    X = pd.concat(rows, ignore_index=True)
    X = X[np.abs(X.g) < 0.5]                                               # отсев несопоставленных токенов
    print(f"перпов с Alpha (часы без спота): {X.s.nunique()}, часов {len(X):,}")
    ag = np.abs(X.g)
    print("|ln(перп/Alpha)|: медиана {:.2%}, 75% {:.2%}, 90% {:.2%}, 99% {:.2%}; доля часов ≥ 1 / 2 / 5%: {:.1%} / {:.1%} / {:.1%}; "
          "среднее ln {:+.3%}".format(ag.median(), ag.quantile(.75), ag.quantile(.9), ag.quantile(.99), (ag >= .01).mean(),
                                       (ag >= .02).mean(), (ag >= .05).mean(), X.g.mean()))
    X = X.sort_values(["s", "H"])
    X["g1"] = X.groupby("s").g.shift(1); X["dH"] = X.groupby("s").H.diff()
    X["rp"] = X.groupby("s").lp.diff(); X["ra"] = X.groupby("s").la.diff()
    Y = X[(X.dH == 3600) & X.g1.notna()]
    for nm, m in (("все часы", np.ones(len(Y), bool)), ("|g| ≥ 1%", np.abs(Y.g1) >= 0.01), ("|g| ≥ 2%", np.abs(Y.g1) >= 0.02)):
        y = Y[m]
        bp = np.polyfit(y.g1, y.rp, 1)[0]; ba = np.polyfit(y.g1, y.ra, 1)[0]
        print(f"  {nm}: часов {len(y):,}; за час закрыто {ba - bp:.0%} разрыва; перп α {bp:+.3f}, Alpha α {ba:+.3f} — доля Alpha {ba / (ba - bp) if ba != bp else np.nan:.0%}")
    for nm, m in (("Alpha в индексе (снимок)", X.snap & (X.alpha_w > 0)), ("Alpha не в индексе", X.snap & (X.alpha_w == 0))):
        x = X[m]
        print(f"  {nm}: перпов {x.s.nunique()}, |разрыв| медиана {np.abs(x.g).median():.2%}, доля ≥ 2% {(np.abs(x.g) >= .02).mean():.1%}")


if __name__ == "__main__":
    main()
