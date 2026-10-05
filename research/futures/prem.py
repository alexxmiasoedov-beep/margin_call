"""Динамика прогнозной ставки фандинга перед входом: минутный индекс премии Binance (premiumIndexKlines 1m).
Прогнозная ставка Binance = средняя премия с начала периода выплаты + clamp(процентная − средняя, ±0,05%).
Для каждого сигнала: премия и прогнозная ставка сейчас и 15/30/60 мин назад."""
import datetime, numpy as np, pandas as pd, pickle
from concurrent.futures import ThreadPoolExecutor
import bv
from sim import SIG, FUND
UTC = datetime.timezone.utc
day = lambda t: datetime.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d")
def pred_rate(tm, pr, t, start, ih):
    """Прогнозная ставка на момент t (за период выплаты длиной ih ч, начавшийся в start), %."""
    m = (tm >= start) & (tm < t)
    if m.sum() < 3: return np.nan
    w = np.arange(1, m.sum() + 1)                          # Binance усредняет с растущими весами
    p = np.average(pr[m], weights=w)
    return (p + np.clip(0.0001 - p, -0.0005, 0.0005)) * ih / 8 * 100     # ставка за период: премия масштабируется на часы/8
def job(s):
    te = s["te"]; A = bv.kfull(s["sym"], "premiumIndexKlines", "1m", (), sorted({day(te - 86400), day(te)}))
    if A is None: return None
    A = A[A[:, 0] < te]; tm, pr = A[:, 0], A[:, 4]
    if len(tm) < 120 or np.all(pr == 0): return None
    F = FUND.get(s["sym"]); ih = 8.0; last = te - (te % (8 * 3600))
    if F is not None and len(F) > 1:
        k = np.searchsorted(F[:, 0], te) - 1
        if k >= 1: ih = (F[k, 0] - F[k - 1, 0]) / 3600; last = F[k, 0]
    f = {"sym": s["sym"], "ep": s["ep"], "ih": ih}
    pnow = lambda T, w=5: pr[(tm >= T - w * 60) & (tm < T)].mean() * 100 if ((tm >= T - w * 60) & (tm < T)).any() else np.nan
    f["prem_now"] = pnow(te)
    for lab, T in (("15m", 900), ("30m", 1800), ("60m", 3600)):
        f[f"prem_ch_{lab}"] = f["prem_now"] - pnow(te - T)
    f["pred_now"] = pred_rate(tm, pr, te, last, ih)
    for lab, T in (("15m", 900), ("30m", 1800), ("60m", 3600)):
        st = last if te - T >= last else last - ih * 3600    # 15–60 мин назад могли быть в прошлом периоде
        f[f"pred_{lab}"] = pred_rate(tm, pr, te - T, st, ih)
        f[f"pred_ch_{lab}"] = f["pred_now"] - f[f"pred_{lab}"]
        f[f"pred_ch_{lab}_h"] = f[f"pred_ch_{lab}"] / ih      # в % за час
    f["pred_now_h"] = f["pred_now"] / ih
    return f
with ThreadPoolExecutor(12) as ex:
    out = [x for x in ex.map(job, SIG) if x]
pd.DataFrame(out).to_csv("prem.csv", index=False); print("готово", len(out), "из", len(SIG))
