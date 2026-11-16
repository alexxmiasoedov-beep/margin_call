"""s35 — разбавление: монеты, у которых за 90 сут монет в обращении стало больше всех, отстают? (гипотезы — ВЫВОДЫ.md,
записаны до проверки). CMC по суткам — s28/hist/<cryptoId>.json ([дата, цена, оборот, капитализация, в обращении]),
символы — s28/unlock_listing.json; фьючерсы — s2/k2y.pkl, фандинг — s2/fund2y.pkl. Формирование по понедельникам
06.01.2025–31.08.2026, срок 28 сут: шорт верхней пятой части по D90, лонг нижней, к среднему вселенной; комиссия 0,1%,
фандинг фактический; t Ньюи — Уэста с лагом 3; половины до и после 01.12.2025. Итог — s35/dil.pkl. Запуск из папки с данными."""
import datetime
import json
import os
import pickle
import sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s15"))
from common import fut_of  # noqa: E402

BAR, DAY, FEE = 900, 86400, 0.001
CUT = 1764547200
UTC = datetime.timezone.utc
D0 = datetime.datetime(2025, 1, 6, tzinfo=UTC).timestamp()
D1 = datetime.datetime(2026, 8, 31, tzinfo=UTC).timestamp()

K = pickle.load(open("s2/k2y.pkl", "rb"))
FU = pickle.load(open("s2/fund2y.pkl", "rb"))
t0 = int(K["BTC"]["t"][0])
t_end = max(int(K[x]["t"][-1]) for x in K)
DAYS = np.arange(t0 + DAY, t_end + BAR + 1, DAY)
ROWS = {}
DC, DV, FIRST = [], [], []
for s, a in K.items():
    t = a["t"].astype(np.int64)
    k = np.searchsorted(t, DAYS - BAR); k2 = np.minimum(k, len(t) - 1)
    has = (k < len(t)) & (t[k2] == DAYS - BAR)
    cq = np.r_[0.0, np.cumsum(a["qv"].astype(np.float64))]
    k0 = np.searchsorted(t, DAYS - DAY)
    ROWS[s] = len(DC)
    DC.append(np.where(has, a["c"][k2], np.nan))
    DV.append(np.where(has, cq[np.minimum(k2 + 1, len(t))] - cq[np.minimum(k0, len(t))], 0.0))
    nz = np.flatnonzero(a["qv"] > 0)
    FIRST.append(a["t"][nz[0]] if len(nz) else np.inf)
DC, DV, FIRST = np.array(DC), np.array(DV), np.array(FIRST, dtype=float)
DCF = pd.DataFrame(DC).ffill(axis=1).values
del K
FUND = {}
for s in ROWS:
    f = FU.get(s)
    a = np.array([(int(r[0]), float(r[2])) for r in f]) if f is not None and len(f) else np.zeros((0, 2))
    a = a[np.argsort(a[:, 0])] if len(a) else a
    FUND[s] = (a[:, 0], np.r_[0.0, np.cumsum(a[:, 1])]) if len(a) else (np.zeros(0), np.zeros(1))


def jd(ts):
    return int(round((ts - DAYS[0]) / DAY))


def fund_sum(s, a, b):
    tt, cs = FUND[s]
    return cs[np.searchsorted(tt, b, "right")] - cs[np.searchsorted(tt, a, "right")]


def load_cmc():
    L = {str(x["cryptoId"]): x["symbol"] for x in json.load(open("s28/unlock_listing.json"))}
    out = {}
    for f in os.listdir("s28/hist"):
        cid = f.split(".")[0]
        sym = L.get(cid)
        if not sym:
            continue
        s, mult = fut_of(sym)
        if s is None or s in out:
            continue
        rows = json.load(open(f"s28/hist/{f}"))
        if not rows:
            continue
        d = {r[0]: (float(r[1] or np.nan), float(r[4] or np.nan)) for r in rows}
        out[s] = (mult, d)
    return out


def day_str(ts):
    return datetime.datetime.fromtimestamp(ts, UTC).strftime("%Y-%m-%d")


def run(C, look=90, q=0.2, hold=28):
    rows = []
    for t in np.arange(D0, D1 + 1, 7 * DAY):
        j = jd(t); je = j + hold
        if je >= len(DAYS):
            break
        sig = {}
        for s, (mult, d) in C.items():
            r = ROWS[s]
            if FIRST[r] > t - 60 * DAY or DV[r, max(j - 29, 0):j + 1].sum() < 1e7 or not np.isfinite(DC[r, j]):
                continue
            a, b = d.get(day_str(t - DAY)), d.get(day_str(t - (look + 1) * DAY))
            if not a or not b or not (a[1] > 0 and b[1] > 0) or not np.isfinite(a[0]):
                continue
            if not 0.8 <= DC[r, j] / (a[0] * mult) <= 1.25:
                continue
            sig[s] = a[1] / b[1] - 1
        if len(sig) < 25:
            continue
        S = pd.Series(sig).sort_values()
        n = max(int(round(len(S) * q)), 3)
        lo, hi = list(S.index[:n]), list(S.index[-n:])
        ret = {s: DCF[ROWS[s], je] / DC[ROWS[s], j] - 1 for s in S.index}
        U = float(np.mean(list(ret.values())))
        sn = np.mean([-ret[s] + fund_sum(s, t, t + hold * DAY) - FEE for s in hi])
        ln = np.mean([ret[s] - fund_sum(s, t, t + hold * DAY) - FEE for s in lo])
        rows.append(dict(t=t, n=len(S), d_hi=S[hi].median(), d_lo=S[lo].median(), S=sn, L=ln, U=U, SU=sn + U, LS=(sn + ln) / 2))
    return pd.DataFrame(rows)


def nw_t(x, lag):
    x = np.asarray(x, float); x = x[np.isfinite(x)]; n = len(x)
    if n < 10:
        return np.nan
    e = x - x.mean(); v = e @ e / n
    for l in range(1, lag + 1):
        v += 2 * (1 - l / (lag + 1)) * (e[l:] @ e[:-l]) / n
    return x.mean() / np.sqrt(v / n)


def show(R, label, lag):
    print(f"{label}: дат {len(R)}, монет в срезе {R.n.median():.0f}, D верхней части {R.d_hi.median():+.1%}, нижней {R.d_lo.median():+.1%}")
    for c, name in (("SU", "шорт разбавляемых к вселенной"), ("S", "шорт разбавляемых"), ("L", "лонг неразбавляемых"),
                    ("LS", "лонг-шорт")):
        x = R[c]; h1, h2 = R[R.t < CUT][c], R[R.t >= CUT][c]
        print(f"    {name:30s} {x.mean():+.2%} (t {nw_t(x, lag):+.1f}) | половины {h1.mean():+.2%} (t {nw_t(h1, lag):+.1f}) / "
              f"{h2.mean():+.2%} (t {nw_t(h2, lag):+.1f}) | в плюсе {(x > 0).mean():.0%}")


if __name__ == "__main__":
    C = load_cmc()
    print(f"монет CMC с фьючерсом Binance: {len(C)}")
    res = {}
    for kw, lab, lag in ((dict(), "ОСНОВНОЕ: D90, пятые части, 28 сут", 3), (dict(look=30), "D30", 3),
                         (dict(q=0.1), "десятые части", 3), (dict(hold=14), "срок 14 сут", 1)):
        R = run(C, **kw); res[lab] = R
        show(R, lab, lag)
    pickle.dump(res, open("s35/dil.pkl", "wb"))
