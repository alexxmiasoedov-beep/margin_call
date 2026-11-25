"""s287 — проверка Г1–Г4 s286 по записи ВЫВОДЫ.md (коммит 78689f0): открытие США, перелёт альтов после шока BTC,
фиксинг ETF, воскресное открытие.

Запуск из /home/user/mc_data (свечи старых периодов — MC_K / MC_F, как в s285):
  python3 -I <repo>/research/s287/run.py 2024–2026
  MC_K=s117/k_oos.pkl MC_F=s117/fund_oos.pkl python3 -I <repo>/research/s287/run.py 2022–2024
  MC_K=s117/k_2020.pkl MC_F=s117/fund_2020.pkl python3 -I <repo>/research/s287/run.py 2020–2022
  python3 -I <repo>/research/s287/run.py report
Сделки — /home/user/mc_data/s287_<период>.pkl, сводка — /home/user/mc_data/s287_report.txt."""
import datetime as dt
import importlib.util
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
D0 = "/home/user/mc_data"
WIN = {"2020–2022": ("2020-10-01", "2022-10-01"), "2022–2024": ("2022-10-01", "2024-10-01"),
       "2024–2026": ("2024-10-01", "2026-10-19")}
BAR, DAY, WEEK = 900, 86400, 7 * 86400
MONTH = 30.44 * DAY
NY, CT = ZoneInfo("America/New_York"), ZoneInfo("America/Chicago")
MACRO = {"CPI", "NFP", "PPI", "PCE", "RETAIL", "GDP", "JOLTS", "ISM_M", "FOMC", "FOMC_PC"}   # как в s286 hyp_freq
ETF_START = {"BTC": dt.date(2024, 1, 11), "ETH": dt.date(2024, 7, 23)}


def _mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def ts(s):
    return int(pd.Timestamp(s, tz="UTC").timestamp())


def loc(d, hh, mm, tz=NY):
    return int(dt.datetime(d.year, d.month, d.day, hh, mm, tzinfo=tz).timestamp())


# ---------- матрица цен периода (как s286 volstudy.load_period, но из уже загруженных свечей fastbt) ----------
def load_D(V, K, a, b):
    t0, t1 = ts(a) - 9 * DAY, ts(b) + 2 * DAY
    n = (t1 - t0) // BAR
    coins = [c for c in V.crypto_perps(K) if c in K]
    for c in ("BTC", "ETH"):
        if c in K and c not in coins:
            coins.append(c)
    C = np.full((len(coins), n), np.nan, np.float32)
    Q = np.zeros((len(coins), n), np.float32)
    for j, c in enumerate(coins):
        x = K[c]
        tt = np.asarray(x["t"], np.int64)
        ok = (tt >= t0) & (tt < t1) & (np.asarray(x["qv"]) > 0)
        ii = (tt[ok] - t0) // BAR
        C[j, ii] = np.asarray(x["c"])[ok]
        Q[j, ii] = np.asarray(x["qv"])[ok]
    C = pd.DataFrame(C.T).ffill(limit=16).to_numpy(np.float32).T
    D = dict(coins=coins, C=C, Q=Q, t0=t0, n=n, a=ts(a), b=ts(b))
    V.daily_aux(D)
    return D


def i_of(D, T):
    """Индекс свечи сетки, открытой в момент T."""
    return (T - D["t0"]) // BAR


def r_between(D, js, T0, T1):
    """Доход монет js от момента T0 до момента T1 (цена в момент — закрытие свечи, открытой на 15 мин раньше)."""
    i0, i1 = i_of(D, T0) - 1, i_of(D, T1) - 1
    with np.errstate(invalid="ignore", divide="ignore"):
        return D["C"][js, i1] / D["C"][js, i0] - 1


def sig_of(D, js, T, minutes):
    return D["sig"][js, i_of(D, T) // 96] * np.sqrt(minutes / 15)


def days_iter(D, pred):
    d = dt.datetime.fromtimestamp(D["a"], dt.timezone.utc).date() - dt.timedelta(days=1)
    end = dt.datetime.fromtimestamp(D["b"], dt.timezone.utc).date() + dt.timedelta(days=1)
    while d <= end:
        if pred(d):
            yield d
        d += dt.timedelta(days=1)


# ---------- Г1, Г4: ход BTC за окно → по ходу BTC и альты с тем же знаком ----------
def momentum_entries(D, var, days, w0, w1, x1, n_alts, zthr, sl, extra=None):
    """w0, w1 — начало и конец окна сигнала (функции дня → момент), x1 — выход (день → момент)."""
    ib = D["ib"]
    out = []
    for d in days:
        T0, T1, TX = w0(d), w1(d), x1(d)
        if not (D["a"] <= T1 < D["b"]):
            continue
        mins = (T1 - T0) / 60
        rb = r_between(D, ib, T0, T1)
        sb = sig_of(D, ib, T0, mins)
        if not (np.isfinite(rb) and np.isfinite(sb) and sb > 0 and rb != 0) or abs(rb) / sb < zthr:
            continue
        side = int(np.sign(rb))
        hold = (TX - T1) / 3600
        meta = dict(var=var, day=d.isoformat(), hold=hold, sl=sl, side=side, T=T1, **(extra(d) if extra else {}))
        out.append(dict(s="BTC", **meta))
        top = D["top"][i_of(D, T0) // 96][:n_alts]
        top = top[top >= 0]
        ra = r_between(D, top, T0, T1)
        sa = sig_of(D, top, T0, mins)
        ok = np.isfinite(ra) & np.isfinite(sa) & (sa > 0) & (np.sign(ra) == side) & (np.abs(ra) / np.where(sa > 0, sa, 1) >= zthr)
        for j in top[ok]:
            out.append(dict(s=D["coins"][j], **meta))
    return out


def g1(D, V, BE, E):
    nyse, early = BE.nyse_day, BE.NYSE_EARLY
    busy_t = set(E[E.fam.isin(V.BUSY)].t.astype(np.int64))
    close = lambda d: loc(d, 13, 0) if d.isoformat() in early else loc(d, 16, 0)            # noqa: E731

    def flags(d):
        return dict(clean=not ({loc(d, 8, 30), loc(d, 10, 0)} & busy_t))
    ent = []
    nd = list(days_iter(D, nyse))
    ent += momentum_entries(D, "Г1", nd, lambda d: loc(d, 9, 30), lambda d: loc(d, 10, 0), close, 20, 1.5, 0.05, flags)
    ent += momentum_entries(D, "Г1 выход 12:00", nd, lambda d: loc(d, 9, 30), lambda d: loc(d, 10, 0),
                            lambda d: min(loc(d, 12, 0), close(d)), 20, 1.5, 0.05)
    ent += momentum_entries(D, "Г1 50 альтов", nd, lambda d: loc(d, 9, 30), lambda d: loc(d, 10, 0), close, 50, 1.5,
                            0.05)
    ent += momentum_entries(D, "Г1 якорь 03:30", nd, lambda d: loc(d, 3, 30), lambda d: loc(d, 4, 0),
                            lambda d: loc(d, 10, 0), 20, 1.5, 0.05)
    # последний получас: сигнал — первый получас, вход за 30 мин до закрытия, выход на закрытии
    for x in momentum_entries(D, "Г1 последний получас", nd, lambda d: loc(d, 9, 30), lambda d: loc(d, 10, 0), close,
                              20, 1.5, 0.05):
        d = dt.date.fromisoformat(x["day"])
        x["T"], x["hold"] = close(d) - 1800, 0.5
        ent.append(x)
    off = list(days_iter(D, lambda d: d.weekday() >= 5 or not nyse(d)))
    ent += momentum_entries(D, "Г1 выходные и праздники", off, lambda d: loc(d, 9, 30), lambda d: loc(d, 10, 0),
                            lambda d: loc(d, 16, 0), 20, 1.5, 0.05)
    return ent


def g4(D):
    ent = []
    for wd, var in ((6, "Г4 воскресенье"), (5, "Г4 суббота (контроль)")):
        dd = list(days_iter(D, lambda d, wd=wd: d.weekday() == wd))
        ent += momentum_entries(D, var, dd, lambda d: loc(d, 17, 0, CT), lambda d: loc(d, 18, 0, CT),
                                lambda d: loc(d, 18, 0, CT) + 8 * 3600, 10, 1.0, 0.05)
    return ent


# ---------- Г2: фиксинг ETF — BTC и ETH против хода окна ----------
def g2(D, BE):
    nyse, early = BE.nyse_day, BE.NYSE_EARLY
    ent = []
    variants = (("Г2", (15, 0), (16, 0), (18, 0), "nyse"),
                ("Г2 выход 17:00", (15, 0), (16, 0), (17, 0), "nyse"),
                ("Г2 выход 20:00", (15, 0), (16, 0), (20, 0), "nyse"),
                ("Г2 окно 14–15", (14, 0), (15, 0), (17, 0), "nyse"),
                ("Г2 выходные и праздники", (15, 0), (16, 0), (18, 0), "off"))
    for var, w0, w1, x1, kind in variants:
        pred = (lambda d: nyse(d) and d.isoformat() not in early) if kind == "nyse" else \
            (lambda d: d.weekday() >= 5 or not nyse(d))
        for d in days_iter(D, pred):
            T0, T1, TX = loc(d, *w0), loc(d, *w1), loc(d, *x1)
            if not (D["a"] <= T1 < D["b"]):
                continue
            for cur in ("BTC", "ETH"):
                j = D["coins"].index(cur)
                r = r_between(D, j, T0, T1)
                sg = sig_of(D, j, T0, 60)
                if not (np.isfinite(r) and r != 0):
                    continue
                ent.append(dict(s=cur, var=var, day=d.isoformat(), hold=(TX - T1) / 3600, sl=0.03, side=-int(np.sign(r)),
                                T=T1, etf=d >= ETF_START[cur], z1=bool(np.isfinite(sg) and sg > 0 and abs(r) / sg >= 1)))
    return ent


# ---------- Г3: перелёт альтов после шока BTC, сделка против остатка с ногой β·BTC ----------
def g3(D, V, E):
    ib, C, t0 = D["ib"], D["C"], D["t0"]
    allT = np.sort(E[E.fam.isin(V.BUSY)].t.astype(np.int64).to_numpy())
    mac = set((E[E.fam.isin(MACRO)].t.astype(np.int64) // BAR * BAR).tolist())
    lo = max(D["a"], t0 + 8 * DAY)
    idx = np.arange(i_of(D, lo), i_of(D, D["b"]))
    with np.errstate(invalid="ignore", divide="ignore"):
        rb_all = C[ib, idx] / C[ib, idx - 1] - 1
        zb_all = np.abs(rb_all) / D["sig"][ib, idx // 96]
    tt = t0 + idx * BAR
    ent, last = [], -10 ** 12
    for k in np.flatnonzero(zb_all >= 3):
        t = int(tt[k])
        if t - last < 3 * 3600:
            continue
        last = t
        if t in mac:
            grp = "A"
        else:
            j = np.searchsorted(allT, t - 3 * 3600)
            grp = "C" if (j < len(allT) and allT[j] <= t + 3 * 3600) else "B"
        i, d = idx[k], idx[k] // 96
        rb = float(rb_all[k])
        top = D["top"][d]
        top = top[top >= 0]
        with np.errstate(invalid="ignore", divide="ignore"):
            ra = C[top, i] / C[top, i - 1] - 1
        sa, be = D["sig"][top, d], D["beta"][top, d]
        e = ra - be * rb
        ok = np.isfinite(e) & np.isfinite(sa) & (sa > 0) & np.isfinite(be) & (np.sign(e) == np.sign(rb)) & \
            (np.abs(e) >= np.maximum(0.01, 2 * sa))
        cand = top[ok]
        if not len(cand):
            continue
        sc = np.abs(e[ok]) / sa[ok]
        for j, bb in zip(cand[np.argsort(-sc)][:5], be[ok][np.argsort(-sc)][:5]):
            ent.append(dict(s=D["coins"][j], var="Г3", grp=grp, dir="вверх" if rb > 0 else "вниз", hold=2.0, sl=0.05,
                            side=-int(np.sign(rb)), T=t + BAR, beta=float(bb), day=dt.datetime.fromtimestamp(
                                t, dt.timezone.utc).date().isoformat()))
    # контроль механизма: тот же остаток без шока BTC (|r_BTC| < σ15), не чаще раза в 3 ч на альт
    lastc = {}
    calm = np.flatnonzero(np.isfinite(zb_all) & (zb_all < 1))
    for k in calm:
        i, d = idx[k], idx[k] // 96
        rb = float(rb_all[k])
        top = D["top"][d]
        top = top[top >= 0]
        with np.errstate(invalid="ignore", divide="ignore"):
            ra = C[top, i] / C[top, i - 1] - 1
        sa, be = D["sig"][top, d], D["beta"][top, d]
        e = ra - be * rb
        ok = np.isfinite(e) & np.isfinite(sa) & (sa > 0) & np.isfinite(be) & (np.abs(e) >= np.maximum(0.01, 2 * sa))
        t = int(tt[k])
        for j, ee, bb in zip(top[ok], e[ok], be[ok]):
            if t - lastc.get(j, -10 ** 12) < 3 * 3600:
                continue
            lastc[j] = t
            ent.append(dict(s=D["coins"][j], var="Г3 без шока BTC", grp="-", dir="вверх" if ee > 0 else "вниз",
                            hold=2.0, sl=0.05, side=-int(np.sign(ee)), T=t + BAR, beta=float(bb),
                            day=dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat()))
    return ent


# ---------- сделки ----------
class BtcLeg:
    def __init__(self, FB):
        k = FB.K["BTC"]
        self.t = k["t"].astype(np.int64)
        self.c = k["c"].astype(float)
        fr = FB.funding("BTC")
        self.ft = fr[:, 0].astype(np.int64)
        self.cs = np.r_[0.0, np.cumsum(fr[:, 1])]

    def px(self, T):
        T = np.asarray(T, np.int64)
        k = np.searchsorted(self.t, T - BAR)
        good = (k < len(self.t)) & (self.t[np.minimum(k, len(self.t) - 1)] == T - BAR)
        return np.where(good, self.c[np.minimum(k, len(self.t) - 1)], np.nan)

    def pnl(self, pos, T0, T1):
        """Нога BTC размера pos (знак — сторона) от T0 до T1: ход, фандинг, комиссия 0,1%·|pos|."""
        r = self.px(T1) / self.px(T0) - 1
        f = self.cs[np.searchsorted(self.ft, T1, "right")] - self.cs[np.searchsorted(self.ft, T0, "right")]
        return pos * (r - f) - 0.001 * np.abs(pos)


def run_trades(FB, leg, ent):
    X = pd.DataFrame(ent)
    rows = []
    for (s, hold, side, sl), g in X.groupby(["s", "hold", "side", "sl"]):
        if s not in FB.K:
            continue
        t = FB.K[s]["t"].astype(np.int64)
        T = g["T"].to_numpy(np.int64)
        I = np.searchsorted(t, T - BAR)
        ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == T - BAR)
        if not ok.any():
            continue
        g, I = g[ok], I[ok]
        okt, net, stp, bars, tend = FB.trades(s, I, sl, hold, int(side))
        hedged = "beta" in g and g["beta"].notna().any()
        if hedged:
            pos = -int(side) * g["beta"].to_numpy(float)
            te = t[I] + BAR
            legv = leg.pnl(pos, te, np.where(okt, tend, te))
            # плацебо с той же ногой BTC: 7, 14, 21 сут раньше
            acc, cnt = np.zeros(len(I)), np.zeros(len(I))
            for dd in (7, 14, 21):
                tp = t[I] - dd * DAY
                j = np.searchsorted(t, tp)
                good = (j < len(t)) & (t[np.minimum(j, len(t) - 1)] == tp) & (j >= 96)
                jj = np.where(good, j, 0)
                okp, netp, _, _, tendp = FB.trades(s, jj, sl, hold, int(side))
                lp = leg.pnl(pos, tp + BAR, np.where(okp, tendp, tp + BAR))
                gg = good & okp & np.isfinite(lp)
                acc[gg] += netp[gg] + lp[gg]
                cnt[gg] += 1
            pl = np.where(cnt > 0, acc / np.maximum(cnt, 1), np.nan)
        else:
            legv = np.zeros(len(I))
            pl = FB.placebo(s, I, sl, hold, int(side), days=(7, 14, 21))
        recs = g.to_dict("records")
        for k in range(len(I)):
            if not okt[k] or not np.isfinite(legv[k]):
                continue
            r = recs[k]
            r.update(te=int(t[I[k]] + BAR), net_alt=float(net[k]), net=float(net[k] + legv[k]), stop=bool(stp[k]),
                     pl=float(pl[k]))
            rows.append(r)
    return pd.DataFrame(rows)


def run(per):
    sys.path.insert(0, os.path.join(HERE, "..", "s187"))
    import fastbt as FB  # noqa: E402
    V = _mod("vs", os.path.join(HERE, "..", "s286", "study", "volstudy.py"))
    BE = _mod("be", os.path.join(HERE, "..", "s286", "study", "build_events.py"))
    E = pd.read_csv(f"{D0}/s286/events.csv")
    D = load_D(V, FB.K, *WIN[per])
    print(per, "монет", len(D["coins"]), flush=True)
    ent = g1(D, V, BE, E) + g2(D, BE) + g4(D)
    print(per, "входов Г1/Г2/Г4", len(ent), flush=True)
    e3 = g3(D, V, E)
    print(per, "входов Г3", sum(x["var"] == "Г3" for x in e3), "контроль", sum(x["var"] != "Г3" for x in e3), flush=True)
    del D
    leg = BtcLeg(FB)
    R = pd.concat([run_trades(FB, leg, ent), run_trades(FB, leg, e3)], ignore_index=True)
    R["per"] = per
    R.to_pickle(f"{D0}/s287_{per}.pkl")
    print(per, "сделок", R.groupby("var").size().to_dict(), flush=True)


# ---------- сводка ----------
def ct(x, t):
    x = np.asarray(x, float)
    w = (np.asarray(t, np.int64) // WEEK) * WEEK
    ok = np.isfinite(x)
    x, w = x[ok], w[ok]
    if len(x) < 5:
        return np.nan, np.nan, len(x), np.nan
    m = x.mean()
    s = pd.Series(x - m).groupby(w).sum()
    se = np.sqrt((s ** 2).sum()) / len(x)
    return m, (m / se if se > 0 else np.nan), len(x), se


def line(x, mo):
    m, t, n, _ = ct(x.net, x.te)
    if n < 5:
        return f"n={n}", (n, m, t, np.nan, np.nan, np.nan)
    md, td, _, _ = ct(x.net - x.pl, x.te)
    mid = float(np.median(x.te))
    h1, h2 = x[x.te < mid].net.mean(), x[x.te >= mid].net.mean()
    return (f"n={n} ({n / mo:.1f} в мес.), {m:+.2%} (t {t:+.1f}); половины {h1:+.2%} / {h2:+.2%}; "
            f"сверх плацебо {md:+.2%} (t {td:+.1f}); стопов {x.stop.mean():.0%}"), (n / mo, m, t, h1, h2, md)


def delta(x, y):
    m1, _, n1, s1 = ct(x.net, x.te)
    m2, _, n2, s2 = ct(y.net, y.te)
    if not (n1 >= 5 and n2 >= 5):
        return "—"
    return f"Δ {m1 - m2:+.2%} (t {(m1 - m2) / np.sqrt(s1 ** 2 + s2 ** 2):+.1f})"


def block(out, R, title, sel, main=False):
    out.append(f"\n### {title}")
    allx, signs = [], []
    for p in WIN:
        x = sel(R[R.per == p])
        mo = (ts(WIN[p][1]) - ts(WIN[p][0])) / MONTH
        s, (pm, m, t, h1, h2, md) = line(x, mo)
        out.append(f"  {p}: {s}")
        if main and p == "2024–2026" and np.isfinite(t):
            conds = (("≥ 20 в мес.", pm >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
                     ("сверх плацебо > 0", md > 0))
            out.append("    правило владельца: " + "; ".join(f"{k} — {'да' if c else 'нет'}" for k, c in conds))
        allx.append(x)
        signs.append(np.isfinite(m) and m > 0)
    A = pd.concat(allx)
    m, t, n, _ = ct(A.net, A.te)
    md, td, _, _ = ct(A.net - A.pl, A.te)
    tail = ""
    if main:
        tail = f"; плюс во всех — {'да' if all(signs) else 'нет'} → " + \
            ("ПОРОГ ТРЁХ ПЕРИОДОВ ПРОЙДЕН" if all(signs) and t >= 3 else "не пройден")
    out.append(f"  вместе: {m:+.2%} (t {t:+.1f}, n={n}); сверх плацебо {md:+.2%} (t {td:+.1f}){tail}")


def report():
    R = pd.concat([pd.read_pickle(f"{D0}/s287_{p}.pkl") for p in WIN if os.path.exists(f"{D0}/s287_{p}.pkl")],
                  ignore_index=True)
    out = []
    v = lambda name: (lambda x: x[x["var"] == name])                                         # noqa: E731
    block(out, R, "Г1 — первый получас США (основная)", v("Г1"), main=True)
    for name in ("Г1 якорь 03:30", "Г1 выходные и праздники", "Г1 выход 12:00", "Г1 последний получас",
                 "Г1 50 альтов"):
        block(out, R, f"{name} (для отчёта)", v(name))
    block(out, R, "Г1 только BTC (для отчёта)", lambda x: x[(x["var"] == "Г1") & (x.s == "BTC")])
    block(out, R, "Г1 только альты (для отчёта)", lambda x: x[(x["var"] == "Г1") & (x.s != "BTC")])
    block(out, R, "Г1 «чистые» дни (для отчёта)", lambda x: x[(x["var"] == "Г1") & (x.clean == True)])  # noqa: E712
    x = R[(R["var"] == "Г1") & (R.per == "2024–2026")]
    cut = ts("2024-11-19")
    mo1, mo2 = (cut - ts(WIN["2024–2026"][0])) / MONTH, (ts(WIN["2024–2026"][1]) - cut) / MONTH
    out.append(f"  Г1 на 2024–2026 гг. до 19.11.2024: {line(x[x.te < cut], mo1)[0]}")
    out.append(f"  Г1 на 2024–2026 гг. после 19.11.2024: {line(x[x.te >= cut], mo2)[0]}")
    out.append("  Г1 − якорь 03:30 по периодам: " + "; ".join(
        f"{p} {delta(R[(R['var'] == 'Г1') & (R.per == p)], R[(R['var'] == 'Г1 якорь 03:30') & (R.per == p)])}"
        for p in WIN))
    out.append("  Г1 − выходные и праздники по периодам: " + "; ".join(
        f"{p} {delta(R[(R['var'] == 'Г1') & (R.per == p)], R[(R['var'] == 'Г1 выходные и праздники') & (R.per == p)])}"
        for p in WIN))

    block(out, R, "Г3 B — перелёт альтов после шока BTC вне расписания (основная)",
          lambda x: x[(x["var"] == "Г3") & (x.grp == "B")], main=True)
    for g, nm in (("A", "в момент релиза"), ("C", "рядом с событием")):
        block(out, R, f"Г3 {g} — {nm} (для отчёта)", lambda x, g=g: x[(x["var"] == "Г3") & (x.grp == g)])
    for dd in ("вверх", "вниз"):
        block(out, R, f"Г3 B, шок {dd} (для отчёта)",
              lambda x, dd=dd: x[(x["var"] == "Г3") & (x.grp == "B") & (x.dir == dd)])
    block(out, R, "Г3 без шока BTC — контроль механизма (для отчёта)", v("Г3 без шока BTC"))
    out.append("  Г3 B − без шока BTC по периодам: " + "; ".join(
        f"{p} {delta(R[(R['var'] == 'Г3') & (R.grp == 'B') & (R.per == p)], R[(R['var'] == 'Г3 без шока BTC') & (R.per == p)])}"
        for p in WIN))
    b = R[(R["var"] == "Г3") & (R.grp == "B")]
    m, t, n, _ = ct(b.net_alt, b.te)
    out.append(f"  Г3 B без ноги BTC (только альт): {m:+.2%} (t {t:+.1f}, n={n})")

    out.append("\n### Г2 — фиксинг ETF (основная проверка — 2024–2026 гг. и дни до ETF)")
    x = R[(R["var"] == "Г2") & (R.per == "2024–2026")]
    mo = (ts(WIN["2024–2026"][1]) - ts(WIN["2024–2026"][0])) / MONTH
    s, (pm, m, t, h1, h2, md) = line(x, mo)
    out.append(f"  2024–2026: {s}")
    pre = R[(R["var"] == "Г2") & (R.per != "2024–2026") & (R.etf == False)]                  # noqa: E712
    mo_pre = (ts("2024-10-01") - ts("2020-10-01")) / MONTH
    out.append(f"  дни до ETF 2020–2024 (плацебо механизма): {line(pre, mo_pre)[0]}")
    dl = delta(x, pre)
    out.append(f"  2024–2026 − до ETF: {dl}")
    if np.isfinite(t):
        m1, _, _, s1 = ct(x.net, x.te)
        m2, _, _, s2 = ct(pre.net, pre.te)
        tdl = (m1 - m2) / np.sqrt(s1 ** 2 + s2 ** 2)
        conds = (("≥ 20 в мес.", pm >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
                 ("сверх плацебо > 0", md > 0), ("лучше дней до ETF, t ≥ 2", tdl >= 2))
        out.append("    порог: " + "; ".join(f"{k} — {'да' if c else 'нет'}" for k, c in conds))
    e22 = R[(R["var"] == "Г2") & (R.per == "2022–2024") & (R.etf == True)]                   # noqa: E712
    out.append(f"  дни ETF внутри 2022–2024 гг.: {line(e22, 8.5)[0]}")
    for name in ("Г2 выход 17:00", "Г2 выход 20:00", "Г2 окно 14–15", "Г2 выходные и праздники"):
        block(out, R, f"{name} (для отчёта)", v(name))
    block(out, R, "Г2 только z ≥ 1 (для отчёта)", lambda x: x[(x["var"] == "Г2") & (x.z1 == True)])  # noqa: E712
    cut = ts("2025-07-29")
    out.append(f"  Г2 на 2024–2026 гг. до 29.07.2025: {line(x[x.te < cut], (cut - ts('2024-10-01')) / MONTH)[0]}")
    out.append(f"  Г2 на 2024–2026 гг. после 29.07.2025: {line(x[x.te >= cut], (ts('2026-10-19') - cut) / MONTH)[0]}")

    block(out, R, "Г4 — воскресное открытие (для отчёта)", v("Г4 воскресенье"))
    block(out, R, "Г4 — суббота, контроль (для отчёта)", v("Г4 суббота (контроль)"))
    out.append("  Г4 воскресенье − суббота: " + "; ".join(
        f"{p} {delta(R[(R['var'] == 'Г4 воскресенье') & (R.per == p)], R[(R['var'] == 'Г4 суббота (контроль)') & (R.per == p)])}"
        for p in WIN))
    txt = "\n".join(out)
    open(f"{D0}/s287_report.txt", "w").write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
