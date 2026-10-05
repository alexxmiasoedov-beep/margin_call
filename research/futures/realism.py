"""Чувствительность бэктеста к отличиям от реальности: задержка входа, проскальзывание, фандинг от текущей стоимости позиции, дневной лимит."""
import bisect, datetime
import numpy as np, pandas as pd
from sim import SIG, FUND, N, TAKER, MAKER, fh_entry, summ
def trade2(s, tp, sl, hold_h=48, delay=1, slip_in=0.0, slip_sl=0.001, fund_mark=True):
    k0 = delay - 1                                      # вход по open минуты (post + delay); open минуты k ≈ close минуты k−1
    if k0 < 0 or k0 >= len(s["t"]) - 2: return None
    e = (s["entry"] if k0 == 0 else s["c"][k0 - 1]) * (1 - slip_in)   # шорт продаёт по рынку чуть ниже
    t, h, l, c, mh = s["t"][k0:], s["h"][k0:], s["l"][k0:], s["c"][k0:], s["mh"][k0:]
    n = min(int(hold_h * 60), len(t)); slp, tpp = e * (1 + sl / 100), (e * (1 - tp / 100) if tp else None)
    a = np.nonzero(mh[:n] >= slp)[0]; j_sl = a[0] if len(a) else n
    b = np.nonzero(l[:n] < tpp)[0] if tpp else []; j_tp = b[0] if len(b) else n
    j = min(j_sl, j_tp)
    if j == n: j = n - 1; px = c[j]; kind = "время" if n >= hold_h * 60 else "обрыв"; fx = TAKER
    elif j == j_sl: px = max(slp * (1 + slip_sl), 0); kind = "стоп"; fx = TAKER
    else: px = tpp; kind = "тейк"; fx = MAKER
    xt = t[j] + 60; te = t[0]; fund = 0.0; F = FUND.get(s["sym"])
    if F is not None:
        for ft, r in F[(F[:, 0] > te) & (F[:, 0] <= xt)]:
            kk = min(np.searchsorted(t, ft) , len(c) - 1)
            fund += r * N * (c[kk] / e if fund_mark else 1)
    price = (1 - px / e) * N; fee = N * TAKER + N * (px / e) * fx
    return dict(kind=kind, price=price, fund=fund, fee=fee, pnl=price + fund - fee, xt=xt)
def run2(tp, sl, pause_h=48, day_limit=None, **kw):
    open_until = {}; last_stop = {}; rows = []; day_pnl = {}; pend = []
    for s in SIG:
        dkey = datetime.datetime.utcfromtimestamp(s["ep"]).date()
        realized = sum(r["pnl"] for r in rows if r["xt"] <= s["ep"] and datetime.datetime.utcfromtimestamp(r["xt"]).date() == dkey) if day_limit else 0
        if day_limit and realized <= -day_limit: continue
        if open_until.get(s["sym"], 0) > s["ep"]: continue
        if pause_h and s["ep"] - last_stop.get(s["sym"], -1e18) < pause_h * 3600: continue
        r = trade2(s, tp, sl, **kw)
        if r is None: continue
        open_until[s["sym"]] = r["xt"]
        if r["kind"] == "стоп": last_stop[s["sym"]] = r["xt"]
        rows.append(dict(ep=s["ep"], sym=s["sym"], rule=s["rule"], **r))
    return pd.DataFrame(rows)
if __name__ == "__main__":
  for tp, sl in ((6, 20), (15, 25)):
      print(f"\n===== {tp}/{sl} =====")
      print(summ(run2(tp, sl, fund_mark=False), "как в бэктесте"))
      print(summ(run2(tp, sl), "фандинг от тек. стоимости"))
      for d in (2, 3, 5): print(summ(run2(tp, sl, delay=d), f"задержка входа {d} мин"))
      print(summ(run2(tp, sl, slip_in=0.001), "вход −0,1% проскальз."))
      print(summ(run2(tp, sl, slip_in=0.003), "вход −0,3% проскальз."))
      for x in (0.005, 0.01, 0.02): print(summ(run2(tp, sl, slip_sl=x), f"стоп +{x*100:g}% проскальз."))
      print(summ(run2(tp, sl, day_limit=16), "дневной лимит 16"))
      print(summ(run2(tp, sl, delay=5, slip_in=0.003, slip_sl=0.01, day_limit=16), "всё плохое сразу"))
