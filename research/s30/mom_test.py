"""s30 — моментум ликвидных фьючерсов (гипотезы — ВЫВОДЫ.md, записаны до проверки).
Каждый день в 00:00 UTC: вселенная — 100 крупнейших по обороту за 30 сут фьючерсов, запущенных ≥ 60 сут назад и торговавшихся
в последние сутки, без стейблкоинов, индексов, металлов и акций; сигнал — доход за L сут; лонг N лидеров, шорт N отстающих,
вход на закрытии в d, выход через H сут (после делистинга архив держит цену расчёта); фандинг фактический (s2/fund2y.pkl),
комиссия 0,1% на ногу. Статистика — по датам формирования, t Ньюи — Уэста с лагом H − 1, половины до и после 01.12.2025.
Итог — s30/mom.pkl. Запуск из папки с данными."""
import datetime
import pickle
import numpy as np, pandas as pd

BAR, DAY, FEE = 900, 86400, 0.001
CUT = 1764547200                                            # 01.12.2025
D0 = datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc).timestamp()
D1 = datetime.datetime(2026, 9, 22, tzinfo=datetime.timezone.utc).timestamp()
SKIP = {"USDT", "USDC", "USDE", "USD1", "USDS", "DAI", "FDUSD", "TUSD", "USDP", "BUSD", "PYUSD", "RLUSD", "USDBRL",
        "BTCDOM", "DEFI", "XAU", "XAG", "XPT", "XPD", "PAXG", "XAUT", "COPPER", "CL", "BZ", "AAPL", "AMD", "AMZN", "COIN",
        "CRCL", "GOOGL", "HOOD", "INTC", "META", "MSFT", "MSTR", "NVDA", "PLTR", "QQQ", "SPY", "TSLA"}

K = pickle.load(open("s2/k2y.pkl", "rb"))
FU = pickle.load(open("s2/fund2y.pkl", "rb"))
SYMS = [s for s in sorted(K) if s not in SKIP]
t0 = int(K["BTC"]["t"][0])
t_end = max(int(K[x]["t"][-1]) for x in SYMS)
DAYS = np.arange(t0 + DAY, t_end + BAR + 1, DAY)                         # границы суток 00:00 UTC
DC = np.zeros((len(SYMS), len(DAYS))); DV = np.zeros_like(DC); FIRST = np.zeros(len(SYMS))
for n, s in enumerate(SYMS):
    a = K[s]; t = a["t"].astype(np.int64)
    k = np.searchsorted(t, DAYS - BAR); k2 = np.minimum(k, len(t) - 1)
    has = (k < len(t)) & (t[k2] == DAYS - BAR)                            # у символа есть свеча на границе
    DC[n] = np.where(has, a["c"][k2], np.nan)
    cq = np.r_[0.0, np.cumsum(a["qv"].astype(np.float64))]
    k0 = np.searchsorted(t, DAYS - DAY)                                   # первая свеча суток до границы
    DV[n] = np.where(has, cq[np.minimum(k2 + 1, len(t))] - cq[np.minimum(k0, len(t))], 0.0)
    nz = np.flatnonzero(a["qv"] > 0)
    FIRST[n] = a["t"][nz[0]] if len(nz) else np.inf
del K
DCF = pd.DataFrame(DC).ffill(axis=1).values                                # цена выхода после конца данных — последняя
FUND = {}
for s in SYMS:
    f = FU.get(s)
    a = np.array([(int(r[0]), float(r[2])) for r in f]) if f is not None and len(f) else np.zeros((0, 2))
    a = a[np.argsort(a[:, 0])] if len(a) else a
    FUND[s] = (a[:, 0], np.r_[0.0, np.cumsum(a[:, 1])]) if len(a) else (np.zeros(0), np.zeros(1))
BTC = SYMS.index("BTC")


def jd(ts):
    """Номер границы суток ts в DAYS."""
    return int(round((ts - DAYS[0]) / DAY))


def fund_sum(s, a, b):
    tt, cs = FUND[s]
    return cs[np.searchsorted(tt, b, "right")] - cs[np.searchsorted(tt, a, "right")]


def run(L=14, N=10, H=7, skip=0, d1=D1):
    rows = []
    for d in np.arange(D0, d1 + 1, DAY):
        j = jd(d); je = j + H
        if je >= len(DAYS):
            break
        ok = ((DV[:, j] > 0) & (FIRST <= d - 60 * DAY) & np.isfinite(DC[:, j]) & np.isfinite(DC[:, j - skip])
              & np.isfinite(DC[:, j - skip - L]))
        vol = DV[:, max(j - 29, 0):j + 1].sum(axis=1)
        cand = np.flatnonzero(ok)
        U = cand[np.argsort(-vol[cand])][:100]
        if len(U) < 4 * N:
            continue
        sig = DC[U, j - skip] / DC[U, j - skip - L] - 1
        order = U[np.argsort(sig)]
        lo, hi = order[:N], order[-N:]
        r = DCF[:, je] / DC[:, j] - 1
        fl = np.array([fund_sum(SYMS[k], d, d + H * DAY) for k in hi])
        fs = np.array([fund_sum(SYMS[k], d, d + H * DAY) for k in lo])
        Lg = r[hi] - fl - FEE
        Sg = -r[lo] + fs - FEE
        rows.append(dict(d=d, L=Lg.mean(), S=Sg.mean(), LS=(Lg.mean() + Sg.mean()) / 2, LU=Lg.mean() - r[U].mean(),
                         LB=Lg.mean() - r[BTC], U=r[U].mean(), fl=fl.mean(), fs=fs.mean(),
                         hi=[SYMS[k] for k in hi], lo=[SYMS[k] for k in lo]))
    return pd.DataFrame(rows)


def nw_t(x, lag):
    x = np.asarray(x, float); x = x[np.isfinite(x)]; n = len(x)
    if n < 20:
        return np.nan
    e = x - x.mean(); v = e @ e / n
    for l in range(1, lag + 1):
        v += 2 * (1 - l / (lag + 1)) * (e[l:] @ e[:-l]) / n
    return x.mean() / np.sqrt(v / n)


def show(R, label, H):
    out = [f"{label}: дат {len(R)}"]
    for c, name in (("LS", "лонг-шорт"), ("L", "лонг"), ("S", "шорт"), ("LU", "лонг к корзине"), ("LB", "лонг с хеджем BTC")):
        x = R[c]; h1, h2 = R[R.d < CUT][c], R[R.d >= CUT][c]
        out.append(f"    {name:17s} {x.mean():+.2%} (t {nw_t(x, H - 1):+.1f}) | половины {h1.mean():+.2%} (t {nw_t(h1, H - 1):+.1f}) "
                   f"/ {h2.mean():+.2%} (t {nw_t(h2, H - 1):+.1f}) | в плюсе {(x > 0).mean():.0%}, худшая {x.min():+.1%}")
    out.append(f"    фандинг за срок: лонг платит {R.fl.mean():+.2%}, шорт получает {R.fs.mean():+.2%}; вселенная {R.U.mean():+.2%}")
    print("\n".join(out), flush=True)


if __name__ == "__main__":
    res = {}
    R = run(); res["main"] = R
    show(R, "ОСНОВНОЕ: 14 сут, 10 монет, 7 сут", 7)
    print("\nЧувствительность:")
    for kw, lab in ((dict(L=7), "окно 7 сут"), (dict(L=28), "окно 28 сут"), (dict(skip=1), "14 сут без последних суток"),
                    (dict(N=5), "5 монет"), (dict(N=20), "20 монет"), (dict(H=3), "срок 3 сут"),
                    (dict(H=14, d1=D1 - 7 * DAY), "срок 14 сут")):
        R = run(**kw); res[lab] = R
        show(R, lab, kw.get("H", 7))
    pickle.dump(res, open("s30/mom.pkl", "wb"))
