"""s23: признаки потоков на часовой сетке (DataFrame: час × символ) и проверка.
Все признаки на часе T считаются по свечам, закрывшимся не позже T. Базы «нормы монеты» — медианы за 30 суток до начала
окна. Проверка — регрессии Фамы — Макбета по срезам раз в сутки (00:00 UTC) и децили; t — Ньюи — Уэст с лагом = горизонт
в сутках. Запуск — из папки с данными."""
import os
import pickle
import sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common23 import CRYPTO, CUT, G, P, SY  # noqa: E402

BASE_H, MIN_BASE_H = 720, 240           # «норма монеты» — 30 суток, не меньше 10 суток истории
LIQ = 50e3                              # вселенная: нормальный часовой оборот ≥ 50 тыс. $ (≈ 1,2 млн $ в сутки)
CSY = [s for s, c in zip(SY, CRYPTO) if c]


def frame(k):
    a = P[k][CRYPTO].T.astype(np.float64)
    return pd.DataFrame(a, index=G, columns=CSY)


def build(W=24):
    """Признаки окна W часов. Кэш s23/feat_W{W}.pkl."""
    path = f"s23/feat_W{W}.pkl"
    if os.path.exists(path):
        return pickle.load(open(path, "rb"))
    C, Q, TB, N = frame("C"), frame("Q"), frame("TB"), frame("N")
    HI, LO, PM, F8 = frame("HI"), frame("LO"), frame("PM"), frame("F8")
    r = np.log(C).diff()                                        # часовой лог-доход (NaN через разрыв)
    m = r.median(axis=1)                                         # рынок — медиана монет
    e = r.sub(m, axis=0)                                         # доход к рынку
    f = 2 * TB - Q                                               # чистый агрессивный поток, $
    Vb = Q.rolling(BASE_H, min_periods=MIN_BASE_H).median().shift(W)        # норма оборота до окна
    phi = f / Q.rolling(BASE_H, min_periods=MIN_BASE_H).median().shift(1)   # часовой поток в «нормальных часах»
    # цена потока λ: наклон часового дохода к рынку по часовому потоку за 30 суток до окна
    cov = (e * phi).rolling(BASE_H, min_periods=MIN_BASE_H).mean() - e.rolling(BASE_H, min_periods=MIN_BASE_H).mean() * \
        phi.rolling(BASE_H, min_periods=MIN_BASE_H).mean()
    var = phi.rolling(BASE_H, min_periods=MIN_BASE_H).var()
    lam = (cov / var).shift(W)
    R = e.rolling(W, min_periods=W).sum()
    PHI = (f.rolling(W, min_periods=W).sum()) / Vb
    D = R - lam * PHI                                            # доход сверх того, что «положено» по потоку
    ts = Q / N
    TSb = np.log(ts).rolling(BASE_H, min_periods=MIN_BASE_H).median().shift(W)
    TS = np.log(Q.rolling(W, min_periods=W).sum() / N.rolling(W, min_periods=W).sum()) - TSb
    A = np.log(Q.rolling(W, min_periods=W).sum() / (W * Vb))     # оборот окна к норме
    B = f.rolling(W, min_periods=W).sum() / Q.rolling(W, min_periods=W).sum()   # доля чистых покупок в обороте окна
    pk = (np.log(HI / LO)) ** 2 / (4 * np.log(2))
    VOL = np.sqrt(pk.rolling(W, min_periods=W).sum())
    VOLb = np.sqrt(pk.rolling(BASE_H, min_periods=MIN_BASE_H).mean().shift(W) * W)
    dPM = PM - PM.shift(W)
    PMW = PM.rolling(W, min_periods=W // 2).mean()
    out = dict(C=C, e=e, m=m, R=R, PHI=PHI, lam=lam, D=D, TS=TS, A=A, B=B, VOL=VOL, VOLb=VOLb, dPM=dPM, PMW=PMW, F8=F8,
               Vb=Vb, W=W)
    pickle.dump(out, open(path, "wb"), protocol=4)
    return out


def fwd_ex(C, h):
    """Доход монеты за h ч вперёд (простой) минус медиана монет — лонг к рынку; от закрытия T до закрытия T + h."""
    y = C.shift(-h) / C - 1
    return y.sub(y.median(axis=1), axis=0)


def days(F, start_h=24 * 40):
    """Срезы раз в сутки в 00:00 UTC, после 40 суток истории."""
    g = F["C"].index.values
    return g[(g % 86400 == 0) & (g >= g[0] + start_h * 3600)]


def universe(F, T):
    """Монеты среза: живые, с нормой оборота ≥ LIQ."""
    vb = F["Vb"].loc[T]
    return vb.index[(vb >= LIQ) & F["C"].loc[T].notna()]


def rk(x):
    """Ранги в [−0,5; 0,5]."""
    return x.rank(pct=True) - 0.5


def nw_t(b, lag):
    b = np.asarray(b, float); b = b[np.isfinite(b)]
    n = len(b)
    if n < 20:
        return np.nan
    d = b - b.mean(); v = d @ d / n
    for l in range(1, lag + 1):
        v += 2 * (1 - l / (lag + 1)) * (d[l:] @ d[:-l]) / n
    return b.mean() / np.sqrt(v / n) if v > 0 else np.nan


def fm(F, Y, names, dates, extra=None, wins=0.01):
    """Фама — Макбет: на каждом срезе — МНК дохода вперёд (винсоризация 1%) на ранги признаков; extra(T, idx) → dict
    дополнительных столбцов (например, взаимодействия). Возвращает DataFrame коэффициентов по датам."""
    rows = []
    for T in dates:
        idx = universe(F, T)
        y = Y.loc[T, idx]
        X = pd.DataFrame({n: F[n].loc[T, idx] for n in names})
        ok = y.notna() & X.notna().all(axis=1)
        if ok.sum() < 30:
            continue
        y, X = y[ok], X[ok].apply(rk)
        if extra:
            for k, v in extra(X).items():
                X[k] = v
        lo, hi = y.quantile(wins), y.quantile(1 - wins)
        y = y.clip(lo, hi)
        Z = np.column_stack([np.ones(len(X)), X.values])
        b = np.linalg.lstsq(Z, y.values, rcond=None)[0]
        rows.append(pd.Series(b, index=["const"] + list(X.columns), name=T))
    return pd.DataFrame(rows)


def report(B, h, title=""):
    """Средние коэффициенты (в п. п. дохода на разницу рангов от середины до края) и t по половинам."""
    lag = max(1, h // 24)
    out = [f"{title} (горизонт {h // 24} сут, срезов {len(B)})"]
    for c in B.columns:
        if c == "const":
            continue
        b = B[c]; b1, b2 = b[b.index < CUT], b[b.index >= CUT]
        out.append(f"  {c:>10}: {b.mean() * 100:+6.2f} п. п. (t {nw_t(b, lag):+4.1f}) | первая {b1.mean() * 100:+6.2f} "
                   f"(t {nw_t(b1, lag):+4.1f}) | вторая {b2.mean() * 100:+6.2f} (t {nw_t(b2, lag):+4.1f})")
    return "\n".join(out)


def deciles(F, Y, name, dates, q=10, cond=None):
    """Средний доход вперёд по децилям признака (cond(T, idx) → маска монет); строка по децилям и D10 − D1 с t."""
    M = []
    for T in dates:
        idx = universe(F, T)
        x, y = F[name].loc[T, idx], Y.loc[T, idx]
        ok = x.notna() & y.notna()
        if cond is not None:
            ok &= cond(T, idx)
        if ok.sum() < 3 * q:
            M.append([np.nan] * q); continue
        g = pd.qcut(x[ok].rank(method="first"), q, labels=False)
        M.append(y[ok].groupby(g).mean().reindex(range(q)).values)
    M = pd.DataFrame(M, index=dates[:len(M)])
    return M
