"""Сверка журнала 💸 в боте с бэктестом repay_wide.py. Правило бота (scanner.repay_wide_rule + trader.virt_open) идёт
по архиву MarginData час за часом: посты канала — из s7/margin.pkl (строки с займом и отдачей, как их видит бот), свечи
Binance — из s2/k2y.pkl (только в окне торгов фьючерсом), проход — через 2 мин после закрытия часа. Выход сделки
считается как в бэктесте (s15/common.trade, стоп 50%, 168 ч), чтобы монета освобождалась в тот же момент. Сравниваются
входы (монета, час). Запуск из папки с данными: python3 s21/rw_fidelity.py"""
import os
import pickle
import re
import sys
import tempfile
import time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s15")); sys.path.insert(0, HERE)
os.environ["STATE_FILE"] = os.path.join(tempfile.mkdtemp(), "state.json"); os.environ["POSITION_USDT"] = "1"
from common import BAR, K, live, trade
import repay_wide                                                    # бэктест: та же таблица монето-часов s21/panel.pkl

sys.path.insert(0, os.path.join(HERE, "..", "..", "bot"))
import scanner, trader

H = 3600
CLOCK = [0.0]
time.time = lambda: CLOCK[0]
scanner.log = lambda *a: None
trader.contract = lambda s: None
trader._contracts.clear(); trader._contracts.update({f"{s}USDT": {} for s in K})
trader.mark_price = lambda s: None                                  # вход — по закрытию свечи T (price=c), как в бэктесте
trader.funding_hourly = lambda s: 0.0
trader.funding_paid = lambda s, a, b=None: 0.0


def http_json(url, timeout=30):
    m = re.search(r"symbol=(.+)USDT&interval=15m&limit=(\d+)", url)
    if not m:
        raise AssertionError(url)
    s, n = m.group(1), int(m.group(2))
    a = K.get(s)
    if a is None:
        return {"code": -1121, "msg": "Invalid symbol."}
    T = int(CLOCK[0] // 900 * 900); lo, hi = live(s); t = a["t"].astype(np.int64)
    i1 = int(np.searchsorted(t, T)); out = []
    for i in range(max(i1 - (n - 1), 0), min(i1 + 1, len(t))):
        if lo <= t[i] <= hi:                                         # свечи-заглушки вне торгов Binance не отдаёт
            out.append([int(t[i]) * 1000, float(a["o"][i]), float(a["h"][i]), float(a["l"][i]), float(a["c"][i]), 0,
                        (int(t[i]) + 900) * 1000 - 1])
    return out
scanner.http_json = http_json

G = pickle.load(open("s7/margin.pkl", "rb"))["G"]
COINS = list(G)
TS = np.concatenate([g[:, 0] for g in G.values()]); CI = np.concatenate([np.full(len(g), n) for n, g in enumerate(G.values())])
B = np.concatenate([g[:, 1] for g in G.values()]); R = np.concatenate([g[:, 2] for g in G.values()])
BR = np.concatenate([g[:, 3] for g in G.values()])
o = np.argsort(TS, kind="stable"); TS, CI, B, R, BR = TS[o], CI[o], B[o], R[o], BR[o]


def posts_at(T):
    """Посты канала за 10 ч до T и 5 мин после, от новых к старым: на закрытии часа бот тянет посты на глубину ↩️
    (scanner.LOOKBACK_RP_H) и видит посты после закрытия часа."""
    i0, i1 = np.searchsorted(TS, T - scanner.LOOKBACK_RP_H * H), np.searchsorted(TS, T + 300, "right")
    P = {}
    for j in range(i0, i1):
        if np.isfinite(B[j]) and np.isfinite(R[j]):
            P.setdefault(float(TS[j]), {})[COINS[CI[j]]] = (repr(float(B[j])), repr(float(R[j])), str(BR[j]), "0")
    return [{"id": int(ts), "ts": ts, "rows": {}, "rows_all": rows} for ts, rows in sorted(P.items(), reverse=True)]


if __name__ == "__main__":
    bt = repay_wide.journal(repay_wide.mask(), sl=0.5, hold=168)
    BT = {(s, int(T)) for s, T in zip(bt.s, bt["T"])}
    state = scanner.load_state(); v = trader._virt(state, "virtual_RW"); exits = {}
    t_end = int(max(bt["T"])) + 7 * 86400
    for T in range(int(TS[0] // H + 6) * H, t_end, H):
        for tr in v["trades"]:
            if not tr.get("closed") and exits[id(tr)] <= T:
                tr["closed"] = exits[id(tr)]; tr["reason"] = "время"
        CLOCK[0] = T + 120
        scanner.repay_wide_rule(state, posts_at(T))
        for tr in [x for x in v["trades"] if x["opened"] == CLOCK[0]]:
            t = K[tr["sym"]]["t"]; j = int(np.searchsorted(t, T - BAR))
            x = trade(tr["sym"], j, sl=0.5, hold_h=168) if j < len(t) and t[j] == T - BAR else None
            if x is None:
                v["trades"].remove(tr)                               # бэктест такую сделку не считает — монета свободна
            else:
                exits[id(tr)] = float(t[j + x["bars"]]) + BAR
    BOT = {(x["sym"], int(x["opened"] - 120)) for x in v["trades"]}
    both = BT & BOT
    print(f"бэктест {len(BT)} входов, бот {len(BOT)}, совпали {len(both)} ({len(both) / max(len(BT), 1):.1%} бэктеста)")
    for nm, d in (("только в бэктесте", sorted(BT - BOT, key=lambda x: x[1])), ("только в боте", sorted(BOT - BT, key=lambda x: x[1]))):
        print(f"  {nm}: {len(d)}" + (" — " + ", ".join(f"{s} {time.strftime('%d.%m.%y %H:%M', time.gmtime(T))}" for s, T in d[:15]) if d else ""))
