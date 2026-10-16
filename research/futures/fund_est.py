"""Оценка выплат фандинга Binance по минутному индексу премии, когда архива ставок ещё нет.
Ставка за период = (взвешенная премия + clamp(0,01% − премия, ±0,05%)) × часов/8, предел ±2%.
Интервал: последний из архива; после выплаты на пределе −2% при 4/8 ч → 1 ч (правило Binance с мая 2025);
обратно на прежний — после 4 подряд часовых ставок выше −0,05% (приближение)."""
import datetime, numpy as np
import bv
UTC = datetime.timezone.utc
day = lambda t: datetime.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d")
def estimate(sym, start_t, start_iv, t_end, orig_iv=None):
    """Выплаты [(время, ставка доля)] с момента start_t (последняя известная выплата) до t_end."""
    orig = orig_iv or (start_iv if start_iv in (4, 8) else 4)
    days = sorted({day(t) for t in range(int(start_t) - 86400, int(t_end) + 86400, 86400)})
    A = bv.kfull(sym, "premiumIndexKlines", "1m", (), days)
    if A is None: return []
    tm, pr = A[:, 0].astype(int), A[:, 4]
    out = []; t = int(start_t); iv = start_iv; calm = 0
    while t + iv * 3600 <= t_end:
        nt = t + iv * 3600; m = (tm >= t) & (tm < nt)
        if m.sum() < iv * 20: t = nt; continue
        p = np.average(pr[m], weights=np.arange(1, m.sum() + 1))
        r = float(np.clip((p + np.clip(0.0001 - p, -0.0005, 0.0005)) * iv / 8, -0.02, 0.02))
        out.append((nt, r))
        if iv in (4, 8) and r <= -0.01999: iv = 1; calm = 0
        elif iv == 1 and orig != 1:
            calm = calm + 1 if r > -0.0005 else 0
            if calm >= 4: iv = orig; calm = 0
        t = nt
    return out
