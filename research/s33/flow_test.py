"""s33 — приток и отток монеты на кошельках Binance (DefiLlama binance-cex) → фьючерс Binance (гипотезы — ВЫВОДЫ.md,
записаны до проверки). Остатки — s33/binance_cex.json (`curl https://api.llama.fi/protocol/binance-cex`), срез в 00:00 UTC.
Событие на срезе D: остаток монеты изменился за сутки на ≥ порога и на ≥ 1 млн $; живой остаток (за 30 сут менялся хотя
бы в половине суток, запас ≥ 1 млн $); цена DefiLlama к фьючерсу 0,8–1,25; фьючерс запущен ≥ 30 сут до D. Одно событие
на монету и сторону за 7 сут. Сделка — с закрытия в D + 1 ч: приток → шорт, отток → лонг, 7 сут (и 3 сут), стоп 50%,
комиссия 0,1%, фактический фандинг (s15/common.trade). Плацебо — та же монета за 45/90/135 сут, половины до и после
01.12.2025, t по дням. Итог — s33/trades.pkl. Запуск из папки с данными."""
import datetime
import json
import os
import pickle
import sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s15"))
from common import K, fut_of, live, trade  # noqa: E402

DAY = 86400
CUT = 1764547200
PL = (45, 90, 135)
T0 = datetime.datetime(2024, 10, 1, tzinfo=datetime.timezone.utc).timestamp()
T1 = datetime.datetime(2026, 10, 10, tzinfo=datetime.timezone.utc).timestamp()
SKIP = {"USDT", "USDC", "USDE", "USD1", "USDS", "DAI", "FDUSD", "TUSD", "USDP", "BUSD", "PYUSD", "RLUSD", "USDBRL",
        "BTCDOM", "DEFI", "XAU", "XAG", "XPT", "XPD", "PAXG", "XAUT", "COPPER", "CL", "BZ", "AAPL", "AMD", "AMZN", "COIN",
        "CRCL", "GOOGL", "HOOD", "INTC", "META", "MSFT", "MSTR", "NVDA", "PLTR", "QQQ", "SPY", "TSLA",
        "WBTC", "WETH", "BTCB", "WBNB", "STETH", "WSTETH", "CBBTC", "CBETH", "BETH", "WBETH"}


def load():
    D = json.load(open("s33/binance_cex.json"))
    B = pd.DataFrame({x["date"]: x["tokens"] for x in D["tokens"]}).T.sort_index()
    V = pd.DataFrame({x["date"]: x["tokens"] for x in D["tokensInUsd"]}).T.sort_index()
    B = B[(B.index >= T0 - 40 * DAY) & (B.index <= T1)]
    V = V.reindex(index=B.index, columns=B.columns)
    return B, V


def close_at(s, ts):
    """Закрытие 15-мин свечи фьючерса, закрывающейся в момент ts (или NaN)."""
    t = K[s]["t"]; i = int(np.searchsorted(t, ts - 900))
    return float(K[s]["c"][i]) if i < len(t) and t[i] == ts - 900 else np.nan


def events(B, V, thr):
    rows = []
    for sym in B.columns:
        if sym.upper() in SKIP:
            continue
        s, mult = fut_of(sym.upper())
        if s is None or s in SKIP:
            continue
        b = B[sym].values.astype(float); v = V[sym].values.astype(float); ts = B.index.values
        lo, hi = live(s)
        last = {+1: -np.inf, -1: -np.inf}
        for k in range(31, len(b)):
            d = float(ts[k])
            if not (T0 <= d <= T1) or d - 30 * DAY < lo or d > hi:
                continue
            b0, b1 = b[k - 1], b[k]
            if not (np.isfinite(b0) and np.isfinite(b1)) or b0 <= 0:
                continue
            w = b[k - 30:k]
            if not np.isfinite(w).all() or (np.diff(w) != 0).mean() < 0.5:
                continue
            px = v[k] / b1 if b1 > 0 and np.isfinite(v[k]) else np.nan
            if not np.isfinite(px) or b0 * px < 1e6:
                continue
            pf = close_at(s, d)
            if not np.isfinite(pf) or not 0.8 <= pf / (px * mult) <= 1.25:
                continue
            ch = b1 / b0 - 1; usd = (b1 - b0) * px
            side = +1 if ch >= thr and usd >= 1e6 else -1 if ch <= -thr and usd <= -1e6 else 0
            if side == 0 or d - last[side] < 7 * DAY:
                continue
            last[side] = d
            rows.append(dict(sym=sym, s=s, d=d, side=side, ch=ch, usd=usd))
    return pd.DataFrame(rows)


def idx(s, te):
    t = K[s]["t"]; i = int(np.searchsorted(t, te - 900))
    return i if i < len(t) and t[i] == te - 900 else None


def deal(s, te, h, side):
    i = idx(s, te)
    if i is None:
        return None
    r = trade(s, i, tp=None, sl=0.5, hold_h=h, side=-1 if side > 0 else +1)
    return r["net"] if r else None


def ct(x, T):
    d = pd.Series(np.asarray(x, float), index=pd.to_datetime(np.asarray(T), unit="s").date).dropna()
    if len(d) < 5:
        return np.nan, np.nan, len(d)
    q = d.groupby(level=0).mean()
    return d.mean(), (q.mean() / q.std() * np.sqrt(len(q)) if len(q) > 2 and q.std() > 0 else np.nan), len(d)


def run(E, h, label):
    out = {}
    for side, name in ((+1, "приток → шорт"), (-1, "отток → лонг")):
        rows = []
        for r in E[E.side == side].itertuples():
            te = r.d + 3600
            n = deal(r.s, te, h, side)
            if n is None:
                continue
            p = [deal(r.s, te - k * DAY, h, side) for k in PL]
            p = [x for x in p if x is not None]
            rows.append(dict(s=r.s, te=te, net=n, plac=np.mean(p) if p else np.nan, ch=r.ch, usd=r.usd))
        D = pd.DataFrame(rows); out[side] = D
        if D.empty:
            print(f"  {label}, {name}: сделок нет"); continue
        m, t, n = ct(D.net, D.te)
        h1, h2 = D[D.te < CUT].net, D[D.te >= CUT].net
        print(f"  {label}, {name}: n={n} {m:+.2%} (t {t:+.1f}), медиана {D.net.median():+.2%}, в плюсе {(D.net > 0).mean():.0%} | "
              f"половины {h1.mean():+.2%} ({len(h1)}) / {h2.mean():+.2%} ({len(h2)}) | плацебо {D.plac.mean():+.2%} → "
              f"разница {(D.net - D.plac).mean():+.2%} | монет {D.s.nunique()}", flush=True)
    return out


if __name__ == "__main__":
    B, V = load()
    res = {}
    for thr, h, lab in ((0.10, 168, "ОСНОВНОЕ: порог 10%, 7 сут"), (0.10, 72, "порог 10%, 3 сут"),
                        (0.05, 168, "порог 5%, 7 сут"), (0.25, 168, "порог 25%, 7 сут")):
        E = events(B, V, thr)
        if thr == 0.10 and h == 168:
            print(f"событий: приток {(E.side > 0).sum()}, отток {(E.side < 0).sum()}, монет {E.s.nunique()}")
        res[lab] = run(E, h, lab)
    pickle.dump(res, open("s33/trades.pkl", "wb"))
