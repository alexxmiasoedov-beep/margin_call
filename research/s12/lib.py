"""Функции сделок s12: (A) новые токены с займом, (B) объявления Binance."""
import re
from s12.common import *
def listing_events():
    """Новые крипто-фьючерсы эпохи канала со спотовым листингом Binance (±10 сут): (символ, свечи, запуск, посты канала)."""
    ev = []
    for s, a in K.items():
        T0 = int(a["t"][0])
        if T0 < CH0 or s in TF or s.endswith("USDC") or len(a["t"]) < 96 * 4: continue
        sa = spot_ann.get(strip(s)) or spot_ann.get(s)
        if not (sa is not None and abs(sa - T0) <= 10 * 86400): continue
        tt = ch.get(strip(s)); ev.append((s, a, T0, tt if tt is not None else np.array([])))
    return ev
def listing_trade(s, a, ent_h, hold_d, stop, fcut, fexit):
    T0 = int(a["t"][0]); te = T0 + ent_h * 3600; e, je = px(a, te)
    f = FU.get(s)
    if f is not None and fcut is not None:
        k = np.searchsorted(f[:, 0], te, "right") - 1
        if k >= 0 and f[k, 2] / f[k, 1] * 8 < fcut: return None
    tx = te + hold_d * 86400
    if tx > T_END: return None
    if f is not None and fexit is not None:
        ff = f[(f[:, 0] > te) & (f[:, 0] <= tx)]; bad = ff[:, 2] / ff[:, 1] * 8 <= fexit
        two = np.flatnonzero(bad[1:] & bad[:-1])
        if len(two): tx = int(ff[two[0] + 1, 0])
    x, jx = px(a, tx); seg = a["h"][je:jx].astype(float) / e - 1 if jx > je else np.array([0.0])
    hit = np.flatnonzero(seg >= stop)
    sp = (-stop - 0.005 if len(hit) else -(x / e - 1)) + fsum(s, te, tx) - 0.001
    be, _ = px(btc, te); bx, _ = px(btc, tx)
    return te, sp, sp + bx / be - 1 - 0.001
def ann_events():
    """(тип, фьючерс, время объявления): делистинг спота, делистинг фьючерса, Monitoring Tag (с 10.2024)."""
    ev = []
    for a in A.values():
        if not a["ts"] or a["ts"] < 1727740800000: continue
        t, ts = a["title"], a["ts"] // 1000
        if re.search(r"Monitoring Tag", t):
            m = re.search(r"Include (.+?) on \d", t) or re.search(r"Include (.+)$", t)
            if m: ev += [("monitoring", c.strip(), ts) for c in re.split(r",|&| and ", m.group(1)) if c.strip()]
        elif re.search(r"^Binance Will Delist", t):
            m = re.search(r"Delist (.+?) on \d", t)
            if m: ev += [("spot delist", c.strip(), ts) for c in re.split(r",|&| and ", m.group(1)) if c.strip()]
        elif re.search(r"Futures Will Delist", t):
            ev += [("perp delist", c, ts) for c in re.findall(r"\b([A-Z0-9]{2,20})USDT\b", t)]
    out = []
    for kind_, c, ts in ev:
        s = next((p + c for p in ("", "1000", "10000", "100000", "1000000") if p + c in K), None)
        if s and s not in TF: out.append((kind_, s, ts))
    return sorted(out, key=lambda x: x[2])
def ann_trade(s, ts, delay_m, hold, stop):
    a = K[s]; te = ((ts + delay_m * 60) // 900 + 1) * 900
    if te >= a["t"][-1] - 86400: return None
    e, je = px(a, te); tx = te + hold * 86400; x, jx = px(a, tx)
    seg = a["h"][je:jx].astype(float) / e - 1 if jx > je else np.array([0.0])
    hit = np.flatnonzero(seg >= stop)
    sp = (-stop - 0.005 if len(hit) else -(x / e - 1)) + fsum(s, te, tx) - 0.001
    be, _ = px(btc, te); bx, _ = px(btc, tx)
    return te, sp, sp + bx / be - 1 - 0.001, fnow(s, te)
