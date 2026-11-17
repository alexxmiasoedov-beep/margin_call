"""Сверка журнала 👀 в боте с бэктестом s83 (union_test.py): правило бота scanner.retail_top_rule идёт по часам
10.2024–10.2026. Обороты за 24 ч — суммы часовых оборотов: Upbit и Bithumb по отдельности (s15/kr_candles_<биржа>.pkl,
вона → $ по KRW-USDT той же биржи) и пары к лире Binance (s67/try1h.pkl, лиры → $ по USDTTRY того же часа); контракты
и даты запуска фьючерсов — по свечам s2/k2y.pkl; входы 🔝, 🛒, 🇰🇷 — из бэктестов s65, s49, s20; вход 👀 — подмена
trader.virt_open с кулдауном 7 суток. Первые 7 суток бот только копит историю, поэтому сравниваются входы после них.
Запуск из папки с данными: python3 <repo>/research/s83/rt_fidelity.py"""
import os
import pickle
import sys
import tempfile

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["STATE_FILE"] = os.path.join(tempfile.mkdtemp(), "state.json")
sys.path.insert(0, os.path.join(HERE, "..", "..", "bot"))
sys.path.insert(0, os.path.join(HERE, "..", "s15"))
import scanner, trader  # noqa: E402
from common import K, live  # noqa: E402

scanner.log = lambda *a: None


def kr_panel(ex):
    C = pickle.load(open(f"s15/kr_candles_{ex}.pkl", "rb"))
    u = C["USDT"]; rate = pd.Series(u["c"].astype(float), index=u["t"].astype(np.int64))
    cols = {}
    for b, x in C.items():
        if not len(x["t"]):
            continue
        t = x["t"].astype(np.int64)
        r = rate.reindex(np.union1d(rate.index, t)).ffill().bfill().reindex(t).values
        cols[b] = pd.Series(x["v"].astype(float) / r, index=t + 3600)
    return pd.DataFrame(cols)


def try_panel():
    TR = pickle.load(open("s67/try1h.pkl", "rb"))
    fx = TR["USDTTRY"]; fxs = pd.Series(fx[:, 2], index=fx[:, 0].astype(np.int64) + 3600)
    cols = {}
    for pair, a in TR.items():
        v = pd.Series(a[:, 1], index=a[:, 0].astype(np.int64) + 3600)
        cols[pair[:-3]] = (v / fxs.reindex(v.index).ffill()).dropna()
    return pd.DataFrame(cols)


def main():
    P = {ex: kr_panel(ex) for ex in ("upbit", "bithumb")}
    P["try"] = try_panel()
    grid = pd.Index(sorted(set(P["upbit"].index) | set(P["bithumb"].index)))
    grid = grid[grid >= pd.Timestamp("2024-10-01", tz="UTC").timestamp()]
    V24 = {k: v.reindex(grid).fillna(0.0).rolling(24, min_periods=24).sum() for k, v in P.items()}
    trader._contracts = {f"{s}USDT": {} for s in K}
    trader.contract = lambda sym: {"symbol": sym, "onboard": live(sym)[0] if sym in K else 0}
    state = {}
    S65 = pd.read_pickle("s65/trades.pkl"); S49 = pd.read_pickle("s49/trades.pkl"); S49 = S49[S49.share >= 0.259]
    S20 = pd.read_pickle("s20/trades.pkl"); S20 = S20[S20.journal == "🇰🇷"]
    for key, rows in (("virtual_KT", zip(S65.s, S65.t)), ("virtual_SP", zip(S49.s, S49.t)), ("virtual_KR", zip(S20.s, S20.te))):
        state[key] = {"trades": [{"sym": s, "opened": float(t) + 60, "closed": 1, "reason": "время"} for s, t in rows]}
    entries = []

    def fake_open(st, key, sym, rule, note, price=None, hold_h=None):
        if any(e[0] == sym and T - e[1] < 168 * 3600 for e in entries):
            return None
        entries.append((sym, T))
        return "ok"

    trader.virt_open = fake_open
    for T in grid[23:]:
        T = int(T)
        scanner.candle_due = lambda st, key, name, step=3600, T=T: T
        state["kt_last_T"] = T
        per = {ex: {c: float(v) for c, v in V24[ex].loc[T].items() if v > 0} for ex in ("upbit", "bithumb")}
        tv = {c: float(v) for c, v in V24["try"].loc[T].items() if v > 0}
        scanner._kt_fetch = lambda per=per: (per, "")
        scanner._rt_try_volumes = lambda tv=tv: (tv, "")
        scanner.retail_top_rule(state)
    start = int(grid[23]) + 168 * 3600
    B = pd.read_pickle("s83/trades.pkl")
    b = {(r.s, int(r.t)) for r in B.itertuples() if r.t >= start}
    m = {(s, int(t)) for s, t in entries if t >= start}
    print(f"После первых 7 суток: бэктест {len(b)} входов, бот {len(m)}; совпали {len(b & m)}")
    only_b, only_m = sorted(b - m, key=lambda x: x[1]), sorted(m - b, key=lambda x: x[1])
    near = sum(1 for s, t in only_b if any(s == s2 and abs(t - t2) <= 6 * 3600 for s2, t2 in only_m))
    print(f"Только в бэктесте: {len(only_b)}; только у бота: {len(only_m)}; из них та же монета в пределах 6 ч: {near}")
    print("  примеры только в бэктесте:", [(s, str(pd.Timestamp(t, unit='s'))[:16]) for s, t in only_b[:6]])
    print("  примеры только у бота:", [(s, str(pd.Timestamp(t, unit='s'))[:16]) for s, t in only_m[:6]])
    pickle.dump(dict(entries=entries, only_b=only_b, only_m=only_m), open("s83/rt_fidelity.pkl", "wb"))


if __name__ == "__main__":
    main()
