"""Сверка журнала 🌊 в боте с бэктестом g19_rule.py (ставка ≤ −1%, интервал 4–8 ч, шорт T+15 мин на 2 ч). Правило бота
(scanner.funding_ebb_rule) вызывается на каждом начислении сетки 4 ч через 16 мин; ответы Binance — из архива:
/fapi/v1/fundingRate — начисления всех фьючерсов в момент T (s2/fund2y.pkl), premiumIndex — время следующего начисления
монеты, список бессрочных контрактов — фьючерсы с живыми свечами в этот момент без акций и металлов (TradFi у Binance —
отдельный тип контракта). Сравниваются входы (монета, начисление) с s23/rule_trades.pkl; для входов бота — доход по той же
методике (15-мин свечи, комиссия 0,1%, фандинг начислений внутри сделки). Запуск из папки с данными."""
import json
import os
import sys
import tempfile
import time
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ["STATE_FILE"] = os.path.join(tempfile.mkdtemp(), "state.json"); os.environ["POSITION_USDT"] = "1"
from common23 import CUT, FU, K, ct, live                           # noqa: E402
import pickle                                                        # noqa: E402

sys.path.insert(0, os.path.join(HERE, "..", "..", "bot"))
import scanner, trader                                               # noqa: E402

kind = pickle.load(open("s12/perp_kind.pkl", "rb"))
TRADFI = set(kind["tradfi"]) - {"BTC"}
ei = "/tmp/claude-0/-home-user/73eaf1da-1cd7-57de-90aa-695a4f698551/scratchpad/ei.json"
if os.path.exists(ei):                                               # текущий exchangeInfo: TRADIFI_PERPETUAL
    TRADFI |= {s["symbol"][:-4] for s in json.load(open(ei))["symbols"] if s.get("contractType") == "TRADIFI_PERPETUAL"}
CLOCK = [0.0]
time.time = lambda: CLOCK[0]
scanner.log = lambda *a: None
F = {s: np.asarray(f, float)[np.argsort(np.asarray(f, float)[:, 0])] for s, f in FU.items() if f is not None and len(f)}
BYT = {}
for s, f in F.items():
    for tf, ih, r in f:
        BYT.setdefault(int(tf), []).append((s, r))
LIVE = {s: live(s) for s in K}
OPEN = []


def fake_request(method, path, params=None, signed=True, **kw):
    params = params or {}
    if path == "/fapi/v1/exchangeInfo":
        return {"symbols": [{"symbol": f"{s}USDT", "contractType": "PERPETUAL", "status": "TRADING", "quoteAsset": "USDT",
                             "onboardDate": int(lo * 1000), "filters": []}
                            for s, (lo, hi) in LIVE.items() if lo <= CLOCK[0] <= hi and s not in TRADFI]}
    if path == "/fapi/v1/fundingRate":
        t0 = params["startTime"] // 1000
        return [{"symbol": f"{s}USDT", "fundingTime": t0 * 1000 + 1, "fundingRate": str(r)} for s, r in BYT.get(t0, [])]
    if path == "/fapi/v1/premiumIndex":
        f = F[params["symbol"][:-4]]
        k = np.searchsorted(f[:, 0], CLOCK[0], "right")
        return {"nextFundingTime": int(f[k, 0] * 1000) if k < len(f) else int((CLOCK[0] + 8 * 3600) * 1000)}
    raise AssertionError(path)


def fake_open(state, key, sym, rule, note, price=None):
    OPEN.append((sym, int(CLOCK[0] // 14400 * 14400)))
    return f"🌊 {sym}"


trader._request = fake_request
trader.virt_open = fake_open
scanner._virt_is_open = lambda state, key, sym: False
state = {}
grid = sorted(t for t in BYT if t % 14400 == 0)
for T in grid:
    trader._contracts.clear()
    CLOCK[0] = T + 16 * 60
    scanner.funding_ebb_rule(state)
bot = set(OPEN)
R = pd.read_pickle("s23/rule_trades.pkl")
bt = set(zip(R.s, R["T"].astype(int)))
print(f"начислений сетки 4 ч: {len(grid)}; входов бота {len(bot)}, событий бэктеста {len(bt)}, совпали {len(bot & bt)}")


def pnl(s, T):
    a = K[s]; t = a["t"].astype(np.int64); cl = a["c"].astype(np.float64)
    i = int(np.searchsorted(t, T)); j = i + 8
    if i < 1 or j >= len(t) or t[i] != T or not (a["qv"][i:j + 1] > 0).all():
        return np.nan
    f = F[s]; t0, t1 = t[i] + 900, t[j] + 900
    return 1 - cl[j] / cl[i] + f[(f[:, 0] > t0) & (f[:, 0] <= t1), 2].sum() - 0.001


for nm, d in (("только у бота", bot - bt), ("только в бэктесте", bt - bot)):
    why = {}
    for s, T in d:
        f = F.get(s); k = np.searchsorted(f[:, 0], T) if f is not None else 0
        ih = f[k, 1] if f is not None and k < len(f) and f[k, 0] == T else np.nan
        lo, hi = LIVE.get(s, (np.inf, -np.inf))
        key = ("интервал до начисления < 4 ч" if ih < 4 else "TradFi по списку исследования" if s in TRADFI else
               "свечи окна неполные (заглушки)" if not np.isfinite(pnl(s, T)) else "другое")
        why[key] = why.get(key, 0) + 1
    print(f"  {nm}: {len(d)} — {why}")
x = pd.Series({(s, T): pnl(s, T) for s, T in bot}).dropna()
Tm = np.array([T for _, T in x.index])
m, t, n = ct(x.values, Tm)
print(f"доход входов бота по методике бэктеста: {m * 100:+.2f}% на сделку (t {t:+.1f}, n {n}; половины "
      f"{x.values[Tm < CUT].mean() * 100:+.2f} / {x.values[Tm >= CUT].mean() * 100:+.2f}); в плюсе {(x > 0).mean():.0%}")
