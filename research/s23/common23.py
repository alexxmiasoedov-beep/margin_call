"""s23 — потоки денег по всем фьючерсам. Часовая панель из 15-мин свечей s2/k2y.pkl на сетке s22/grid.pkl (час T —
четыре свечи, закрывшиеся в (T − 1 ч, T]): цена закрытия, открытие, high/low, оборот, агрессивные покупки (taker buy),
число сделок, число живых 15-мин свечей; премия к индексу на закрытии часа (s12/prem.pkl); фандинг на 8 ч (последнее
начисление). Кэш s23/panel.npz. Вселенная — криптофьючерсы (без акций, индексов, металлов, нефти, стейблкоинов).
Запуск скриптов — из папки с данными."""
import os
import pickle
import sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s22"))
from common22 import CUT, DAY, GR, H, K, NONCRYPTO, ct, fwd, funding, live, mk, summ, trade   # noqa: E402,F401
from common import FU                                                                            # noqa: E402

G = GR["grid"]; SY = GR["syms"]; ROW = GR["row"]
_kind = pickle.load(open("s12/perp_kind.pkl", "rb"))
TRADFI = (set(_kind["tradfi"]) - {"BTC"}) | NONCRYPTO | {
    "AAPL", "MSFT", "QQQ", "SPY", "TSM", "AVGO", "AMD", "BABA", "XAG", "XPT", "XPD", "COPPER", "NATGAS", "CL", "BZ", "PAXG",
    "OPENAI", "ANTHROPIC", "SPCX", "HK0625", "QCOM", "ANET", "AMC", "CVX", "DIA", "APLD", "GPRO", "POPMART", "UNITREE",
    "SKHY", "USDC", "FDUSD", "TUSD", "USDP", "BUSD", "DAI", "USDE", "USD1", "BTCDOM", "DEFI", "XAUT"}


def build():
    """Часовые массивы (символы × часы сетки)."""
    S, n = len(SY), len(G)
    out = {k: np.full((S, n), np.nan, np.float32) for k in ("C", "O", "HI", "LO", "Q", "TB", "N", "PM", "F8")}
    out["NB"] = np.zeros((S, n), np.int8)
    for j, s in enumerate(SY):
        a = K[s]; t = a["t"].astype(np.int64)
        # часы, у которых все четыре свечи есть в архиве
        end = t + 900                                          # время закрытия свечи
        idx = np.searchsorted(G, end)                          # час, в который попадает свеча (закрытие в (T−1ч, T])
        ok = (idx < n) & (G[np.minimum(idx, n - 1)] - end < 3600) & (G[np.minimum(idx, n - 1)] >= end)
        idx, sel = idx[ok], np.flatnonzero(ok)
        livebar = a["qv"][sel] > 0
        np.add.at(out["NB"][j], idx[livebar], 1)
        for k, f in (("Q", "qv"), ("TB", "tb"), ("N", "n")):
            v = np.zeros(n, np.float64); np.add.at(v, idx, a[f][sel].astype(np.float64)); out[k][j] = v
        last = end[sel] == G[idx]                              # свеча, закрывшаяся ровно в T, — цена закрытия часа
        out["C"][j, idx[last]] = a["c"][sel][last]
        first = end[sel] == G[idx] - 2700
        out["O"][j, idx[first]] = a["o"][sel][first]
        hi = np.full(n, -np.inf); np.maximum.at(hi, idx, a["h"][sel].astype(np.float64)); out["HI"][j] = hi
        lo = np.full(n, np.inf); np.minimum.at(lo, idx, a["l"][sel].astype(np.float64)); out["LO"][j] = lo
        dead = out["NB"][j] < 4
        for k in ("C", "O", "HI", "LO", "Q", "TB", "N"):
            out[k][j, dead] = np.nan
        p = PREM.get(s)
        if p is not None:                                      # премия на закрытии 15-мин свечи, начатой в t → время t + 900
            pt, pv = p[0].astype(np.int64) + 900, p[1]
            m = np.isin(pt, G)
            out["PM"][j, np.searchsorted(G, pt[m])] = pv[m]
            out["PM"][j, dead] = np.nan
        f = FU.get(s)
        if f is not None and len(f):                           # последнее начисление фандинга до T, в пересчёте на 8 ч
            f = np.asarray(f, float); f = f[np.argsort(f[:, 0])]
            i = np.searchsorted(f[:, 0], G, "right") - 1
            v = np.where(i >= 0, f[np.maximum(i, 0), 2] * 8 / np.maximum(f[np.maximum(i, 0), 1], 1), np.nan)
            out["F8"][j] = v
            out["F8"][j, dead] = np.nan
        if j % 100 == 0:
            print(f"  панель: {j}/{S}", flush=True)
    return out


PATH = "s23/panel.npz"
if os.path.exists(PATH):
    P = dict(np.load(PATH))
else:
    PREM = pickle.load(open("s12/prem.pkl", "rb"))
    P = build()
    np.savez(PATH, **P)
    del PREM

CRYPTO = np.array([s not in TRADFI for s in SY])
