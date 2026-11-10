"""Отставание монет канала после сильного хода — относительное (к рынку альтов), а шорт с хеджем BTC его почти теряет.
Проверка: хедж корзиной — лонг поровну 10 самых торгуемых фьючерсов за 30 суток до входа (без BTC, самой монеты,
стейблкоинов, индексов, металлов, нефти и акций) на ту же сумму, комиссия 0,1% и фактический фандинг корзины. Сделки — как в
borrow_wide.py (T1, T2) и borrow_trades.py (ячейка A), 168 ч, стоп 25% по монете. Запуск из папки с данными."""
import os
import sys
from collections import Counter
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s15")); sys.path.insert(0, HERE)
from common import BAR, FEE, K, funding
from borrow_trades import sims, thin

SKIP = {"BTC", "USDC", "FDUSD", "TUSD", "BUSD", "DAI", "USDP", "USDE", "BTCDOM", "DEFI",               # стейблкоины, индексы
        "XAU", "XAG", "XPT", "XPD", "PAXG", "XAUT", "COPPER", "CL", "BZ",                               # металлы, нефть
        "AAPL", "AMD", "AMZN", "COIN", "CRCL", "GOOGL", "HOOD", "INTC", "META", "MSFT", "MSTR", "NVDA", "PLTR",
        "QQQ", "SPY", "TSLA"}                                                                               # акции, фонды
D = pd.read_pickle("s21/panel.pkl")
SY = [s for s in K if s not in SKIP]
d0 = min(int(K[s]["t"][0]) for s in SY) // 86400; d1 = max(int(K[s]["t"][-1]) for s in SY) // 86400 + 1
V = np.zeros((d1 - d0 + 1, len(SY)))
for n, s in enumerate(SY):
    d = K[s]["t"].astype(np.int64) // 86400 - d0
    V[:, n] = np.bincount(d, weights=K[s]["qv"].astype(float), minlength=len(V))[:len(V)]
CS = np.vstack([np.zeros(len(SY)), np.cumsum(V, axis=0)])
TOP = Counter()


def px(s, T):
    t = K[s]["t"]; i = int(np.searchsorted(t, T - BAR))
    return float(K[s]["c"][i]) if i < len(t) and t[i] == T - BAR and K[s]["qv"][i] > 0 else np.nan


def basket(s0, T, t1):
    d = int(T // 86400) - d0
    vol = CS[d] - CS[max(d - 30, 0)]
    order = [SY[i] for i in np.argsort(-vol) if SY[i] != s0][:10]
    TOP.update(order)
    r = []
    for s in order:
        a, b = px(s, T), px(s, t1)
        if np.isfinite(a) and np.isfinite(b):
            fr = funding(s); f = float(fr[(fr[:, 0] > T) & (fr[:, 0] <= t1), 1].sum()) if len(fr) else 0.0
            r.append(b / a - 1 - f)
    return np.mean(r) - FEE if len(r) >= 8 else np.nan


def show(R, name):
    tt = lambda v: v.mean() / v.std() * np.sqrt(len(v))
    R = R.dropna(subset=["bsk"]); x = R.bsk; cut = R["T"].median(); h = R["T"] < cut
    q = R.groupby(pd.to_datetime(R["T"], unit="s").dt.to_period("Q")).bsk.mean()
    print(f"  {name}: n={len(R)}, без хеджа {R.net.mean() * 100:+.2f}% (t {tt(R.net):+.1f}), хедж BTC {R.hedged.mean() * 100:+.2f}% "
          f"(t {tt(R.hedged.dropna()):+.1f}), хедж корзиной {x.mean() * 100:+.2f}% (t {tt(x):+.1f}; медиана {x.median() * 100:+.1f}%, "
          f"в плюсе {(x > 0).mean():.0%}) | половины {x[h].mean() * 100:+.2f}/{x[~h].mean() * 100:+.2f}% | кварталов в плюсе "
          f"{(q > 0).sum()}/{len(q)}: " + ", ".join(f"{k} {v * 100:+.1f}%" for k, v in q.items()))


if __name__ == "__main__":
    acc_b = (D.bor >= 1.5 * D.bor4) & (D.bor >= 50e3) & D.in4
    acc_r = (D.rep >= 1.5 * D.rep4) & (D.rep >= 20e3) & D.in4
    for nm, m in (("A займ ускорился, цена −5%−", acc_b & ~acc_r & (D.r4 <= -0.05)),
                  ("T1 монета канала, цена −5%−", D.in4 & (D.r4 <= -0.05)),
                  ("T2 монета канала, цена +5%+", D.in4 & (D.r4 >= 0.05))):
        E = thin(D[m]); R = sims(E, sl=0.25, hold_h=168)
        R["bsk"] = [r.net + basket(r.s, float(r.T), float(K[r.s]["t"][int(np.searchsorted(K[r.s]["t"], r.T - BAR)) + r.bars]) + BAR)
                    for r in R.itertuples()]
        show(R, nm)
    print("\nчаще всего в корзине: " + ", ".join(f"{s} {n}" for s, n in TOP.most_common(20)))
