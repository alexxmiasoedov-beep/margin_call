"""s37 — корейские часы против западных (гипотезы — ВЫВОДЫ.md, записаны до проверки). Панель s15/kr_panel.pkl: по часам
T (закрытие часа, UTC) доход фьючерса r1 и обычная доля Кореи norm (медиана за 7 сут до часа). Рынок — медиана часового
дохода всех фьючерсов (s22/grid.pkl). Сессии по суткам UTC: К = часы, начинающиеся 00–14, З = 15–23 (вариант — 12–23).
Г1: доход сессии к рынку по корзинам norm на начало сессии. Г2: шорт сессии З у монет с norm ≥ порога, комиссия 0,1%,
фактический фандинг (s2/fund2y.pkl), к рынку и с хеджем BTC; t по дням; половины до и после 01.12.2025.
Итог — s37/sess.pkl. Запуск из папки с данными."""
import pickle
import numpy as np, pandas as pd

CUT = 1764547200
FEE = 0.001
KP = pickle.load(open("s15/kr_panel.pkl", "rb"))
GR = pickle.load(open("s22/grid.pkl", "rb"))
g, C = GR["grid"], GR["C"].astype(np.float64)
with np.errstate(all="ignore"):
    MK1 = np.r_[np.nan, np.nanmedian(C[:, 1:] / C[:, :-1] - 1, axis=0)]        # доход рынка за час, кончающийся в g[k]
BTC1 = np.r_[np.nan, C[GR["row"]["BTC"], 1:] / C[GR["row"]["BTC"], :-1] - 1]
FU = pickle.load(open("s2/fund2y.pkl", "rb"))
FUND = {}


def fund_sum(s, a, b):
    if s not in FUND:
        f = FU.get(s)
        x = np.array([(int(r[0]), float(r[2])) for r in f]) if f is not None and len(f) else np.zeros((0, 2))
        x = x[np.argsort(x[:, 0])] if len(x) else x
        FUND[s] = (x[:, 0], np.r_[0.0, np.cumsum(x[:, 1])]) if len(x) else (np.zeros(0), np.zeros(1))
    tt, cs = FUND[s]
    return cs[np.searchsorted(tt, b, "right")] - cs[np.searchsorted(tt, a, "right")]


def sessions(w_start=15):
    """Строки: монета, день, сессия, norm на начало, доход (произведение), к рынку (сумма), рынок и BTC за сессию."""
    rows = []
    for s, d in KP.items():
        d = d[np.isfinite(d.r1)]
        if d.empty:
            continue
        T = d["T"].values.astype(np.int64); H = T - 3600
        k = np.searchsorted(g, T); ok = (k < len(g)) & (g[np.minimum(k, len(g) - 1)] == T)
        d = d[ok]; T, H, k = T[ok], H[ok], k[ok]
        hod = (H % 86400) // 3600; day = H // 86400
        ses = np.where(hod < w_start, "К", "З")
        df = pd.DataFrame(dict(day=day, ses=ses, hod=hod, r1=d.r1.values, mk=MK1[k], bt=BTC1[k], norm=d.norm.values, H=H))
        for (dy, se), x in df.groupby(["day", "ses"], sort=False):
            need = w_start if se == "К" else 24 - w_start
            if len(x) != need or not np.isfinite(x.mk).all():
                continue
            x = x.sort_values("hod")
            rows.append((s, int(dy), se, float(x.norm.iloc[0]), float(np.prod(1 + x.r1) - 1), float((x.r1 - x.mk).sum()),
                         float(np.prod(1 + x.mk) - 1), float(np.prod(1 + x.bt) - 1), int(x.H.iloc[0]), int(x.H.iloc[-1]) + 3600))
    return pd.DataFrame(rows, columns=["s", "day", "ses", "norm", "ret", "exc", "mkt", "btc", "t0", "t1"])


def by_day(x, col):
    q = x.groupby("day")[col].mean()
    return q.mean(), (q.mean() / q.std() * np.sqrt(len(q)) if len(q) > 2 and q.std() > 0 else np.nan), len(q)


def g1(S, label):
    print(f"Г1 ({label}): доход сессии к рынку по корзинам обычной доли Кореи (среднее по дням, t по дням)")
    for lo, hi, nm in ((0, 0.05, "< 5%"), (0.05, 0.20, "5–20%"), (0.20, 1.01, "≥ 20%")):
        line = f"  norm {nm:6s}:"
        for se in ("К", "З"):
            x = S[(S.ses == se) & (S.norm >= lo) & (S.norm < hi)]
            m, t, n = by_day(x, "exc")
            h1 = by_day(x[x.t0 < CUT], "exc")[0]; h2 = by_day(x[x.t0 >= CUT], "exc")[0]
            line += f" | {se}: {m:+.3%} (t {t:+.1f}; {h1:+.3%} / {h2:+.3%}; монето-сессий {len(x)})"
        print(line, flush=True)


def g2(S, thr, label):
    x = S[(S.ses == "З") & (S.norm >= thr)].copy()
    x["f"] = [fund_sum(s, a, b) for s, a, b in zip(x.s, x.t0, x.t1)]
    x["net"] = -x.ret + x.f - FEE
    x["rel"] = x.net + x.mkt
    x["hb"] = x.net + x.btc
    out = f"  {label}: монето-сессий {len(x)}, дней {x.day.nunique()}, монет в день {len(x) / max(x.day.nunique(), 1):.1f}"
    for col, nm in (("net", "шорт"), ("rel", "к рынку"), ("hb", "с хеджем BTC")):
        m, t, n = by_day(x, col)
        h1 = by_day(x[x.t0 < CUT], col)[0]; h2 = by_day(x[x.t0 >= CUT], col)[0]
        out += f"\n      {nm:12s} {m:+.3%} в день (t {t:+.1f}) | половины {h1:+.3%} / {h2:+.3%}"
    print(out, flush=True)
    return x


if __name__ == "__main__":
    res = {}
    S = sessions(15); res["S15"] = S
    g1(S, "З = 15–24 UTC")
    print("\nГ2: шорт западной сессии у монет с большой долей Кореи (после комиссии 0,1% и фандинга)")
    for thr in (0.20, 0.10, 0.30):
        res[f"g2_{thr}"] = g2(S, thr, f"norm ≥ {thr:.0%}, З = 15–24 UTC" + (" (основное)" if thr == 0.20 else ""))
    S12 = sessions(12); res["S12"] = S12
    res["g2_12"] = g2(S12, 0.20, "norm ≥ 20%, З = 12–24 UTC")
    pickle.dump(res, open("s37/sess.pkl", "wb"))
