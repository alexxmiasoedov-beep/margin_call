"""s293 — проверка Г9, Г10, Г3, Г4 по записи ВЫВОДЫ.md (коммит 1a2ad55).

Запуск из /home/user/mc_data (свечи старых периодов — MC_K / MC_F):
  python3 -I <repo>/research/s293/run.py 2024–2026
  MC_K=s117/k_oos.pkl MC_F=s117/fund_oos.pkl python3 -I <repo>/research/s293/run.py 2022–2024
  MC_K=s117/k_2020.pkl MC_F=s117/fund_2020.pkl python3 -I <repo>/research/s293/run.py 2020–2022
  python3 -I <repo>/research/s293/run.py report
Сделки — /home/user/mc_data/s293_<период>.pkl, сводка — /home/user/mc_data/s293_report.txt.
Метрики берутся на последнем часовом срезе не позже чем за 10 мин до входа (срез публикуется с задержкой)."""
import importlib.util
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
D0 = "/home/user/mc_data"
PER = {"2020–2022": dict(win=("2020-10-01", "2022-10-01"), mwin=("2021-12-01", "2022-10-01"), met="s293/metrics_2021",
                         fmt="npy", label="П1 (12.2021–09.2022)"),
       "2022–2024": dict(win=("2022-10-01", "2024-10-01"), mwin=("2022-10-01", "2024-10-01"), met="s230/metrics",
                         fmt="npy", label="П2"),
       "2024–2026": dict(win=("2024-10-01", "2026-10-19"), mwin=("2024-10-01", "2026-10-19"), met="s228/met",
                         fmt="npz", label="П3")}
BAR, DAY, WEEK, HOUR = 900, 86400, 7 * 86400, 3600
MONTH = 30.44 * DAY


def ts(s):
    return int(pd.Timestamp(s, tz="UTC").timestamp())


def load_met(cfg, coin):
    """Почасовые метрики монеты: t, OI $, лонг/шорт топ-трейдеров по позициям, всех счетов."""
    if cfg["fmt"] == "npy":
        p = f"{D0}/{cfg['met']}/{coin}.npy"
        if not os.path.exists(p):
            return None
        a = np.load(p)
        if not len(a):
            return None
        return a[:, 0].astype(np.int64), a[:, 2].astype(float), a[:, 4].astype(float), a[:, 5].astype(float)
    p = f"{D0}/{cfg['met']}/{coin}.npz"
    if not os.path.exists(p):
        return None
    z = np.load(p)
    if not len(z["t"]):
        return None
    v = z["v"].astype(float)
    return z["t"].astype(np.int64), v[:, 1], v[:, 3], v[:, 4]


def snap(t, x, T, lag=600):
    """Значение среза на последний час не позже T − lag; NaN, если среза нет."""
    T = np.asarray(T, np.int64)
    h = (T - lag) // HOUR * HOUR
    k = np.searchsorted(t, h)
    ok = (k < len(t)) & (t[np.minimum(k, len(t) - 1)] == h)
    return np.where(ok, x[np.minimum(k, len(t) - 1)], np.nan)


def setup(per):
    sys.path.insert(0, os.path.join(HERE, "..", "s187"))
    import fastbt as FB  # noqa: E402
    spec = importlib.util.spec_from_file_location("s287run", os.path.join(HERE, "..", "s287", "run.py"))
    R7 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(R7)
    V = R7._mod("vs", os.path.join(HERE, "..", "s286", "study", "volstudy.py"))
    D = R7.load_D(V, FB.K, *PER[per]["win"])
    # агрессивные покупки на той же сетке
    TB = np.full(D["C"].shape, np.nan, np.float32)
    for j, c in enumerate(D["coins"]):
        a = FB.K[c]
        tt = np.asarray(a["t"], np.int64)
        ok = (tt >= D["t0"]) & (tt < D["t0"] + D["n"] * BAR) & (np.asarray(a["qv"]) > 0)
        TB[j, (tt[ok] - D["t0"]) // BAR] = np.asarray(a["tb"], float)[ok] if "tb" in a else np.nan
    D["TB"] = TB
    return FB, D


def daily_pct(series_by_day, q, window=30, minn=1000):
    """Порог q-го перцентиля по прошлым `window` суткам для каждого дня (series_by_day: массив (nd, k))."""
    nd = series_by_day.shape[0]
    out = np.full(nd, np.nan)
    flat = series_by_day
    for d in range(window, nd):
        w = flat[d - window:d].ravel()
        w = w[np.isfinite(w)]
        if len(w) >= minn:
            out[d] = np.percentile(w, q)
    return out


def thin(T, gap):
    keep, last = [], -10 ** 12
    for x in np.sort(np.asarray(T, np.int64)):
        if x - last >= gap:
            keep.append(int(x))
            last = x
    return keep


# ---------- Г9: временная продажа ----------
def g9(D, cfg):
    a, b = ts(cfg["mwin"][0]), ts(cfg["mwin"][1])
    C, Q, TB, t0 = D["C"], D["Q"], D["TB"], D["t0"]
    nd = D["nd"]
    cand = set(int(j) for d in range(nd) for j in D["top"][d] if j >= 0)
    ent = []
    for j in cand:
        c = D["coins"][j]
        m = load_met(cfg, c)
        if m is None:
            continue
        mt, oi, _, _ = m
        x = (2 * TB[j] - Q[j]).astype(float)
        x[Q[j] <= 0] = np.nan
        xd = x[:nd * 96].reshape(nd, 96)
        q01, q99 = daily_pct(xd, 1), daily_pct(xd, 99)
        with np.errstate(invalid="ignore", divide="ignore"):
            r = C[j, 1:] / C[j, :-1] - 1
        for kind, side_cond in (("продажа", -1), ("покупка", 1)):
            evT = []
            for d in range(30, nd):
                if j not in set(D["top"][d][:50].tolist()):
                    continue
                thr = q01[d] if side_cond < 0 else q99[d]
                sg = D["sig"][j, d]
                if not (np.isfinite(thr) and np.isfinite(sg) and sg > 0):
                    continue
                ii = np.arange(d * 96, d * 96 + 96)
                ii = ii[(ii >= 1) & (ii < len(x))]
                xx, rr = x[ii], r[ii - 1]
                ok = (xx <= thr) if side_cond < 0 else (xx >= thr)
                ok &= (rr <= -1.5 * sg) if side_cond < 0 else (rr >= 1.5 * sg)
                if not ok.any():
                    continue
                T = t0 + (ii[ok] + 1) * BAR
                T = T[(T >= a) & (T < b)]
                if not len(T):
                    continue
                o1 = snap(mt, oi, T)
                o0 = snap(mt, oi, T - HOUR)
                with np.errstate(invalid="ignore", divide="ignore"):
                    dOI = o1 / o0 - 1
                evT += list(T[np.isfinite(dOI) & (dOI >= -0.02)])
            for T in thin(evT, 4 * HOUR):
                if kind == "продажа":
                    ent += [dict(h="Г9", var="продажа → лонг 4 ч", s=c, T=T, side=1, hold=4.0, sl=0.05),
                            dict(h="Г9", var="продажа → лонг 1 ч", s=c, T=T, side=1, hold=1.0, sl=0.05)]
                else:
                    ent.append(dict(h="Г9", var="покупка → лонг 4 ч (зеркало)", s=c, T=T, side=1, hold=4.0, sl=0.05))
    return ent


# ---------- Г10: контрарный сдвиг топ-трейдеров ----------
def g10(D, cfg):
    a, b = ts(cfg["mwin"][0]), ts(cfg["mwin"][1])
    C, Q, t0, nd = D["C"], D["Q"], D["t0"], D["nd"]
    cand = set(int(j) for d in range(nd) for j in D["top"][d] if j >= 0)
    ent = []
    cq = np.nancumsum(np.nan_to_num(Q, nan=0.0), axis=1)
    for j in cand:
        c = D["coins"][j]
        m = load_met(cfg, c)
        if m is None:
            continue
        mt, oi, p, al = m
        hh = np.arange(max(a, t0 + 31 * DAY) // HOUR * HOUR, b, HOUR)
        Ltop = snap(mt, p / (1 + p), hh + 600)                    # срез на час hh (вход — на 15 мин позже)
        Lall = snap(mt, al / (1 + al), hh + 600)
        Ltop4 = snap(mt, p / (1 + p), hh - 4 * HOUR + 600)
        Lall4 = snap(mt, al / (1 + al), hh - 4 * HOUR + 600)
        OIh = snap(mt, oi, hh + 600)
        i_h = (hh - t0) // BAR                                      # индекс свечи, открытой в момент hh
        ok_i = (i_h >= 97) & (i_h < Q.shape[1])
        turn = np.full(len(hh), np.nan)
        turn[ok_i] = cq[j, i_h[ok_i] - 1] - cq[j, i_h[ok_i] - 97]
        with np.errstate(invalid="ignore", divide="ignore"):
            S = ((Ltop - Ltop4) - (Lall - Lall4)) * OIh / turn
            r4 = np.full(len(hh), np.nan)
            r4[ok_i] = C[j, i_h[ok_i] - 1] / C[j, i_h[ok_i] - 17] - 1
        # пороги по прошлым 30 суткам (720 часов)
        dd = (hh - t0) // DAY
        Sser = pd.Series(S, index=hh)
        lo = Sser.rolling(720, min_periods=400).quantile(0.05).shift(1).to_numpy()
        hi = Sser.rolling(720, min_periods=400).quantile(0.95).shift(1).to_numpy()
        top_ok = np.array([d < nd and j in set(D["top"][d][:50].tolist()) for d in dd])
        L = np.isfinite(S) & np.isfinite(hi) & (S >= hi) & (r4 <= 0) & top_ok
        Sh = np.isfinite(S) & np.isfinite(lo) & (S <= lo) & (r4 >= 0) & top_ok
        for side, mask in ((1, L), (-1, Sh)):
            T = thin(hh[mask] + BAR, 24 * HOUR)                     # вход — закрытие 15-мин свечи после среза
            for x in T:
                ent += [dict(h="Г10", var=f"{'лонг' if side > 0 else 'шорт'} за топ-трейдерами 24 ч", s=c, T=x,
                             side=side, hold=24.0, sl=0.10),
                        dict(h="Г10", var=f"{'лонг' if side > 0 else 'шорт'} за топ-трейдерами 4 ч", s=c, T=x,
                             side=side, hold=4.0, sl=0.10)]
    return ent


def trades(FB, ent):
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
        pl = FB.placebo(s, I, sl, hold, int(side), days=(7, 14, 21))
        alt = FB.alt_mv(t[I] + BAR, np.where(okt, tend, t[I] + BAR))
        recs = g.to_dict("records")
        for k in range(len(I)):
            if okt[k]:
                r = recs[k]
                r.update(te=int(t[I[k]] + BAR), net=float(net[k]), stop=bool(stp[k]), pl=float(pl[k]),
                         hed=float(net[k] - side * alt[k]))
                rows.append(r)
    return pd.DataFrame(rows)


# ---------- Г3 и Г4: признаки на входах шорт-журналов ----------
def journal_entries(per):
    out = []
    a = pd.read_pickle(f"{D0}/s277_{per}.pkl")
    out.append(a[a.h.isin(["⏰", "🇰🇷", "👀"]) & (a.ex == "8 ч")][["h", "s", "te", "net", "stop", "hed", "pl"]])
    b = pd.read_pickle(f"{D0}/s285_{per}.pkl")
    out.append(b[b.ex == "8 ч"].assign(h="🔝")[["h", "s", "te", "net", "stop", "hed", "pl"]])
    c = pd.read_pickle(f"{D0}/s270_{per}.pkl")
    c = c[(c.grp == "S") & (c.side == -1) & (c.sl == 0.10) & (c.hold == 8)]
    out.append(c.assign(h="🛒")[["h", "s", "te", "net", "stop", "hed", "pl"]])
    w = pd.read_pickle(f"{D0}/s284_{per}.pkl")
    out.append(w[w.ex == "8 ч"].rename(columns={"t": "te"}).assign(h="🐋")[["h", "s", "te", "net", "stop", "hed", "pl"]])
    J = pd.concat(out, ignore_index=True)
    J["te"] = J.te.astype(np.int64)
    return J


def journal_features(FB, D, per, cfg):
    J = journal_entries(per)
    C, Q, TB, t0 = D["C"], D["Q"], D["TB"], D["t0"]
    idx = {c: j for j, c in enumerate(D["coins"])}
    cq = np.nancumsum(np.nan_to_num(Q, nan=0.0), axis=1)
    imb = np.abs(2 * np.nan_to_num(TB, nan=0.0) - np.nan_to_num(Q, nan=0.0))
    ci = np.cumsum(imb, axis=1)
    J["vpin"] = np.nan
    J["oi2x"] = np.nan
    J["oiturn"] = np.nan
    mcache = {}
    for k in range(len(J)):
        s, te = J.s.iat[k], int(J.te.iat[k])
        j = idx.get(s)
        if j is None:
            continue
        i = (te - t0) // BAR                                        # свечи до момента te: индексы < i
        if i < 97 or i > Q.shape[1]:
            continue
        qs = cq[j, i - 1] - cq[j, i - 97]
        if qs > 0:
            J.iat[k, J.columns.get_loc("vpin")] = (ci[j, i - 1] - ci[j, i - 97]) / qs
        if s not in mcache:
            mcache[s] = load_met(cfg, s)
        m = mcache[s]
        if m is not None and ts(cfg["mwin"][0]) <= te < ts(cfg["mwin"][1]):
            o1 = snap(m[0], m[1], np.array([te]))[0]
            o0 = snap(m[0], m[1], np.array([te - DAY]))[0]
            if np.isfinite(o1) and np.isfinite(o0) and o0 > 0:
                J.iat[k, J.columns.get_loc("oi2x")] = o1 / o0
            if np.isfinite(o1) and qs > 0:
                J.iat[k, J.columns.get_loc("oiturn")] = o1 / qs
    J["per"] = per
    return J


def run(per):
    cfg = PER[per]
    FB, D = setup(per)
    print(per, "монет", len(D["coins"]), flush=True)
    J = journal_features(FB, D, per, cfg)
    J.to_pickle(f"{D0}/s293_journals_{per}.pkl")
    print(per, "входов журналов", len(J), "с VPIN", int(J.vpin.notna().sum()), "с OI", int(J.oi2x.notna().sum()), flush=True)
    ent = g9(D, cfg)
    print(per, "входов Г9", len(ent), flush=True)
    ent += g10(D, cfg)
    print(per, "входов всего", len(ent), flush=True)
    del D
    R = trades(FB, ent)
    R["per"] = per
    R.to_pickle(f"{D0}/s293_{per}.pkl")
    print(per, "сделок", R.groupby("var").size().to_dict(), flush=True)


# ---------- сводка ----------
def ct(x, t):
    x = np.asarray(x, float)
    w = np.asarray(t, np.int64) // WEEK
    ok = np.isfinite(x)
    x, w = x[ok], w[ok]
    if len(x) < 5:
        return np.nan, np.nan, len(x), np.nan
    m = x.mean()
    s = pd.Series(x - m).groupby(w).sum()
    se = np.sqrt((s ** 2).sum()) / len(x)
    return m, (m / se if se > 0 else np.nan), len(x), se


def combine(ms, ses):
    w = np.array([1 / s ** 2 for s in ses])
    m = float(np.sum(w * np.array(ms)) / w.sum())
    return m, m * np.sqrt(w.sum())


def report():
    out = []
    P = lambda s: (out.append(s), print(s))                                              # noqa: E731
    R = pd.concat([pd.read_pickle(f"{D0}/s293_{p}.pkl") for p in PER if os.path.exists(f"{D0}/s293_{p}.pkl")],
                  ignore_index=True)
    for var in sorted(R["var"].unique()):
        x = R[R["var"] == var]
        main = var in ("продажа → лонг 4 ч", "лонг за топ-трейдерами 24 ч", "шорт за топ-трейдерами 24 ч")
        P(f"\n### {var}{' (основная)' if main else ''}")
        ms, ses, signs = [], [], []
        for p, cfg in PER.items():
            g = x[x.per == p]
            a, b = ts(cfg["mwin"][0]), ts(cfg["mwin"][1])
            mo = (b - a) / MONTH
            m, t, n, se = ct(g.net, g.te)
            if n < 5:
                P(f"  {cfg['label']}: n={n}")
                signs.append(False)
                continue
            mh, th, _, _ = ct(g.hed, g.te)
            md, td, _, _ = ct(g.net - g.pl, g.te)
            mid = float(np.median(g.te))
            h1, h2 = g[g.te < mid].net.mean(), g[g.te >= mid].net.mean()
            P(f"  {cfg['label']}: n={n} ({n / mo:.1f} в мес.), {m:+.2%} (t {t:+.1f}); половины {h1:+.2%} / {h2:+.2%}; "
              f"сверх плацебо {md:+.2%} (t {td:+.1f}); с хеджем {mh:+.2%} (t {th:+.1f}); стопов {g.stop.mean():.0%}")
            if main and p == "2024–2026":
                conds = (("≥ 20 в мес.", n / mo >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
                         ("сверх плацебо > 0", md > 0))
                P("    правило владельца: " + "; ".join(f"{k} — {'да' if c else 'нет'}" for k, c in conds))
            ms.append(m); ses.append(se); signs.append(m > 0)
        if len(ms) == 3:
            m, t = combine(ms, ses)
            P(f"  вместе (взвешенно по периодам): {m:+.2%} (t {t:+.1f}); плюс во всех — {'да' if all(signs) else 'нет'}"
              + (f" → {'ПОРОГ ПРОЙДЕН' if all(signs) and t >= 3 else 'не пройден'}" if main else ""))
    # Г3 и Г4 на входах журналов
    J = pd.concat([pd.read_pickle(f"{D0}/s293_journals_{p}.pkl") for p in PER
                   if os.path.exists(f"{D0}/s293_journals_{p}.pkl")], ignore_index=True)
    P("\n### Г3a — вето: OI $ за 24 ч ≥ ×2 (шорт 8 ч, все журналы вместе; Δ = вето − остальные)")
    rows = []
    for p, cfg in PER.items():
        g = J[(J.per == p) & J.oi2x.notna()]
        rows.append((cfg["label"], g[g.oi2x >= 2], g[g.oi2x < 2]))
    delta_lines(P, rows)
    P("\n### Г3b — вето: OI $ к обороту за 24 ч в верхнем дециле входов периода")
    rows = []
    for p, cfg in PER.items():
        g = J[(J.per == p) & J.oiturn.notna()]
        if len(g):
            q = g.oiturn.quantile(0.9)
            rows.append((cfg["label"], g[g.oiturn >= q], g[g.oiturn < q]))
    delta_lines(P, rows)
    P("\n### Г4 — VPIN24 на входе: Δ = верхняя треть − нижняя треть (по журналам и периодам)")
    rows = []
    for p in PER:
        g = J[(J.per == p) & J.vpin.notna()].copy()
        g["tq"] = g.groupby("h").vpin.transform(lambda v: pd.qcut(v.rank(method="first"), 3, labels=False))
        rows.append((p, g[g.tq == 2], g[g.tq == 0]))
        P(f"  {p}: доля стопов по третям — " + ", ".join(f"{k}: {g[g.tq == k].stop.mean():.0%}" for k in (0, 1, 2)))
    delta_lines(P, rows)
    for h in ("🛒", "🇰🇷", "⏰", "🔝", "👀", "🐋"):
        rr = []
        for p in PER:
            g = J[(J.per == p) & (J.h == h) & J.vpin.notna()].copy()
            if len(g) >= 30:
                g["tq"] = pd.qcut(g.vpin.rank(method="first"), 3, labels=False)
                rr.append((p, g[g.tq == 2], g[g.tq == 0]))
        if rr:
            P(f"  {h}:")
            delta_lines(P, rr, indent="    ")
    open(f"{D0}/s293_report.txt", "w").write("\n".join(out) + "\n")


def delta_lines(P, rows, indent="  "):
    ms, ses, signs = [], [], []
    for lab, A, B in rows:
        m1, _, n1, s1 = ct(A.net, A.te)
        m2, _, n2, s2 = ct(B.net, B.te)
        if n1 < 5 or n2 < 5:
            P(f"{indent}{lab}: мало сделок ({n1} / {n2})")
            signs.append(False)
            continue
        d, se = m1 - m2, np.hypot(s1, s2)
        P(f"{indent}{lab}: вето/верх {m1:+.2%} (n={n1}, стопов {A.stop.mean():.0%}) против {m2:+.2%} (n={n2}, стопов "
          f"{B.stop.mean():.0%}); Δ {d:+.2%} (t {d / se:+.1f})")
        ms.append(d); ses.append(se); signs.append(d < 0)
    if len(ms) >= 2:
        m, t = combine(ms, ses)
        P(f"{indent}вместе Δ {m:+.2%} (t {t:+.1f}); Δ < 0 во всех — {'да' if all(signs) else 'нет'}")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
