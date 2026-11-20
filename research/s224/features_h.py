"""s224a — те же 37 признаков s216 на часовой сетке (каждый час, когда монета в канале: вся панель s21/panel.pkl) и четыре
шорта с хеджем индексом альтов, как в s223: y_hs4 (стоп 10%), y_hs24 (25%), y_hs48 (25%), y_hs168 (50%); u_e_<исход> —
время выхода для честных сделок. Метод — research/s224/ВЫВОДЫ.md (записан до расчёта). Функции признаков — из
research/s216/features.py без изменений; меняется только сетка. Итог — s224h_feat.pkl.
Запуск из /home/user/mc_data: python3 <repo>/research/s224/features_h.py"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s216", "s187"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
import features as F216  # noqa: E402  (s216)
import fastbt as FB  # noqa: E402

DAY = 86400
OUTS = {"hs4": (-1, 0.10, 4), "hs24": (-1, 0.25, 24), "hs48": (-1, 0.25, 48), "hs168": (-1, 0.50, 168)}


def hedged(G):
    out = {}
    for k in OUTS:
        out[f"y_{k}"] = np.full(len(G), np.nan); out[f"u_e_{k}"] = np.full(len(G), np.nan)
    for s, idx in G.groupby("s").groups.items():
        if s not in FB.K:
            continue
        t = FB.K[s]["t"].astype(np.int64)
        pos = G.index.get_indexer(idx)
        st = G.loc[idx, "T"].to_numpy(np.int64) - 900
        I = np.searchsorted(t, st)
        ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == st)
        lo, _ = FB.live(s)
        ok &= t[np.minimum(I, len(t) - 1)] >= lo + DAY
        if not ok.any():
            continue
        for k, (side, sl, hold) in OUTS.items():
            okt, net, _, _, tend = FB.trades(s, I[ok], sl, hold, side)
            mv = FB.alt_mv(t[I[ok]] + 900, tend)
            out[f"y_{k}"][pos[ok]] = np.where(okt, net - side * mv, np.nan)
            out[f"u_e_{k}"][pos[ok]] = np.where(okt, tend, np.nan)
    return out


def main():
    D = pd.read_pickle("s21/panel.pkl")
    G = D.sort_values(["T", "s"]).reset_index(drop=True)                 # часовая сетка: все строки панели
    F = G[["s", "T", "bor", "rep"]].copy()
    F["net"] = G.bor - G.rep
    F["rb"] = np.where(G.bor > 0, G.rep / G.bor, np.nan)
    F["b4"] = np.where(G.in4 & (G.bor4 > 0), G.bor / G.bor4.where(G.bor4 > 0), np.nan)
    F["r4x"] = np.where(G.in4 & (G.rep4 > 0), G.rep / G.rep4.where(G.rep4 > 0), np.nan)
    print("наблюдений", len(F), flush=True)
    for k, v in F216.loan_features(D, G).items():
        F[k] = v
    F["hold"] = np.clip(F.net7 / np.maximum(G.rep, 1e3), -1000, 1000)
    for k, v in F216.market_features(G).items():
        F[k] = v
    F["bqv"] = F.bor / F.qv24.where(F.qv24 > 0)
    for k, v in F216.rate_features(G).items():
        F[k] = v
    F["mcap"] = F216.mcap_table(G)
    F["bmc"] = F.bor / F.mcap
    for k, v in F216.metric_features(G).items():
        F[k] = v
    F["oiq"] = F.oiv / F.qv24.where(F.qv24 > 0)
    K = FB.K
    bt = K["BTC"]["t"].astype(np.int64) + 900; bc = K["BTC"]["c"].astype(float)
    F["btc24"] = [bc[i] / bc[j] - 1 if i >= 0 and j >= 0 else np.nan
                  for i, j in zip(np.searchsorted(bt, F["T"], "right") - 1, np.searchsorted(bt, F["T"] - DAY, "right") - 1)]
    acc = D[D.in4 & (D.bor >= 1.5 * D.bor4) & (D.bor >= 50e3)][["s", "T"]]
    at = np.sort(acc["T"].to_numpy(np.int64)); sa = acc.sort_values("T").s.to_numpy()
    F["wave"] = [len(set(sa[np.searchsorted(at, T - DAY, "right"):np.searchsorted(at, T, "right")])) for T in F["T"]]
    for k, v in hedged(G).items():
        F[k] = v
    F = F.drop(columns=["oiv", "mcap"])
    F.to_pickle("s224h_feat.pkl")
    print("готово:", F.shape, flush=True)
    four = F[F["T"] % (4 * 3600) == 0]
    old = pd.read_pickle("s223_feat.pkl")
    m = four.merge(old, on=["s", "T"], suffixes=("", "_o"))
    bad = [c for c in old.columns if c in F.columns and c not in ("s", "T") and pd.api.types.is_numeric_dtype(old[c])
           and not np.allclose(m[c].to_numpy(float), m[c + "_o"].to_numpy(float), equal_nan=True, rtol=1e-9, atol=0)]
    print(f"сверка с s223 на сетке 4 ч: строк {len(m)} из {len(old)}; расходятся признаки: {bad or 'нет'}")


if __name__ == "__main__":
    main()
