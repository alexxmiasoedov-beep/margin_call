"""s174 — Г1 «застрявшие покупатели» (гипотеза и порог — ВЫВОДЫ.md, записаны до расчёта). Часовые свечи — из 15-мин свечей
перпа; профиль агрессивных покупок по корзинам 1% логарифма типичной цены за часы (T − 30 сут, T − 72 ч]; полоса Z —
корзина закрытия и две выше; группы по плотности D полосы: плотная ≥ 15%, средняя 5–15%, пустая < 5%; кулдаун 72 ч внутри
группы. Сделки — s15/common.trade, вход — закрытие 15-мин свечи после закрытия часа. Запуск из /home/user/mc_data:
MC_K=… MC_F=… python3 <repo>/research/s174/trapped.py <период>  (2024–2026 — без MC_K/MC_F);
сводка: python3 <repo>/research/s174/trapped.py report"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s141"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
OUT, DAY, H = "/home/user/mc_data", 86400, 3600
PER = {"2020–2022": ("2020-10-01", "2022-10-01", "2021-10-01", "/home/user/mc_2020/s15/kr_panel.pkl"),
       "2022–2024": ("2022-10-01", "2024-10-01", "2023-10-01", "/home/user/mc_oos/s15/kr_panel.pkl"),
       "2024–2026": ("2024-10-01", "2026-10-17", "2025-12-01", "/home/user/mc_data/s15/kr_panel.pkl")}
NONCRYPTO = {"XAU", "XAG", "XPT", "XPD", "COPPER", "NATGAS", "CL", "BZ", "AAPL", "MSFT", "AMD", "QQQ", "SPY", "TSM",
             "BABA", "AMC", "CVX", "DIA", "AVGO", "QCOM", "ANET", "PAXG", "USDC", "FDUSD", "TUSD", "USDP", "BTCDOM",
             "DEFI", "BLUEBIRD", "HUT", "APLD", "GPRO", "SKHY", "OPENAI", "ANTHROPIC", "SPCX", "POPMART", "UNITREE",
             "MARSCOIN", "USAR", "SLX", "ESP"}
EXITS = {"n24": (24, 0.25), "n24s10": (24, 0.10), "n48": (48, 0.25), "n48s10": (48, 0.10)}
DENSE, EMPTY, RISE, V24, COOL = 0.15, 0.05, 0.05, 5e6, 72
LB = np.log(1.01)


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def hourly(k):
    """Сплошная сетка часов: максимум, минимум, закрытие, оборот и агрессивные покупки ($)."""
    t = np.asarray(k["t"], np.int64); h = t // H
    st = np.r_[0, np.flatnonzero(np.diff(h)) + 1]; Hh = h[st]
    hi = np.maximum.reduceat(np.asarray(k["h"], np.float64), st)
    lo = np.minimum.reduceat(np.asarray(k["l"], np.float64), st)
    en = np.r_[st[1:], len(t)] - 1
    c = np.asarray(k["c"], np.float64)[en]
    qv = np.add.reduceat(np.asarray(k["qv"], np.float64), st)
    tb = np.add.reduceat(np.asarray(k["tb"], np.float64), st)
    T = np.arange(Hh[0], Hh[-1] + 1); idx = Hh - Hh[0]
    out = {}
    for nm, a, fill in (("hi", hi, np.nan), ("lo", lo, np.nan), ("c", c, np.nan), ("qv", qv, 0.0), ("tb", tb, 0.0)):
        z = np.full(len(T), fill); z[idx] = a; out[nm] = z
    out["c"] = pd.Series(out["c"]).ffill().values
    out["hi"] = np.where(np.isnan(out["hi"]), out["c"], out["hi"])
    out["lo"] = np.where(np.isnan(out["lo"]), out["c"], out["lo"])
    return T, out


def roll_sum(a, w):
    cs = np.cumsum(np.r_[0.0, a]); r = np.full(len(a), np.nan); r[w - 1:] = cs[w:] - cs[:-w]
    return r


def fund_hourly(T, F):
    """Фандинг на час: ставка начисления, разделённая на длину его интервала в часах."""
    out = np.full(len(T), np.nan)
    if not len(F):
        return out
    tf = F[:, 0].astype(np.int64); r = F[:, 1].astype(float)
    dt = np.diff(tf, prepend=tf[0] - 8 * H) / H; dt = np.where((dt <= 0) | (dt > 24), 8.0, dt)
    k = np.searchsorted(tf, (T + 1) * H, "left"); ok = k < len(tf)
    out[ok] = r[k[ok]] / dt[k[ok]]
    out[(T + 1) * H < tf[0] - 8 * H] = np.nan
    return out


def events(T, x, fh):
    c, qv, tb = x["c"], x["qv"], x["tb"]
    ok = qv > 0
    if ok.sum() < 24 * 40:
        return []
    p = (x["hi"] + x["lo"] + c) / 3
    with np.errstate(divide="ignore", invalid="ignore"):
        b = np.floor(np.log(np.where(p > 0, p, np.nan)) / LB)
        bc = np.floor(np.log(np.where(c > 0, c, np.nan)) / LB)
    good = np.isfinite(b) & np.isfinite(bc)
    if good.sum() < 24 * 40:
        return []
    bmin = int(np.nanmin(b[good])) - 3; nb = int(np.nanmax(b[good])) + 4 - bmin + 1
    if nb > 2000:
        return []
    ii = np.flatnonzero(good); col = (b[ii] - bmin).astype(int)
    Mt = np.zeros((len(T), nb)); Mt[ii, col] = tb[ii]; Ct = np.cumsum(Mt, axis=0); del Mt
    Mq = np.zeros((len(T), nb)); Mq[ii, col] = qv[ii]; Cq = np.cumsum(Mq, axis=0); del Mq
    v24 = roll_sum(qv, 24); first = np.flatnonzero(ok)[0]
    cs = pd.Series(c)
    rise = (cs / cs.shift(24) - 1).values
    prevmax = cs.shift(1).rolling(72, min_periods=72).max().values
    with np.errstate(invalid="ignore"):
        cand = np.flatnonzero(good & (v24 >= V24) & (rise >= RISE) & (prevmax < 1.01 ** bc))
    cand = cand[cand >= max(720, first + 720)]
    ev, last = [], {"dense": -10 ** 9, "mid": -10 ** 9, "empty": -10 ** 9}
    for i in cand:
        k0 = int(bc[i] - bmin)
        W = Ct[i - 72] - Ct[i - 720]; tot = W.sum()
        if tot <= 0:
            continue
        zb = W[k0:k0 + 3].sum(); D = zb / tot
        g = "dense" if D >= DENSE else ("empty" if D < EMPTY else "mid")
        if i - last[g] < COOL:
            continue
        last[g] = i
        zq = (Cq[i - 72] - Cq[i - 720])[k0:k0 + 3].sum()
        young = (Ct[i - 72] - Ct[i - 240])[k0:k0 + 3].sum() / zb if zb > 0 else np.nan
        hh = np.arange(i - 719, i - 71); inz = (b[hh] >= bc[i]) & (b[hh] <= bc[i] + 2) & np.isfinite(fh[hh])
        w = tb[hh][inz]
        fz = float((fh[hh][inz] * w).sum() / w.sum() * 8) if w.sum() > 0 else np.nan
        pump = c[i] / np.nanmin(x["lo"][i - 1:i + 1]) - 1 >= 0.15
        ev.append(dict(Th=int(T[i]), grp=g, D=D, buy=zb / zq if zq > 0 else np.nan, young=young, fz=fz, pump=bool(pump),
                       r24=rise[i], v24=v24[i]))
    return ev


def kr_table(path):
    P = pickle.load(open(path, "rb"))
    return {s: (d["T"].to_numpy(np.int64), d["kr"].to_numpy(float), d["bin"].to_numpy(float)) for s, d in P.items()}


def run(per):
    from common import K, funding, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    from flow_test import alt_index  # noqa: E402
    t0, t1 = ts(PER[per][0]), ts(PER[per][1])
    kind = pd.read_pickle(f"{OUT}/s12/perp_kind.pkl")
    bad = set(kind.get("tradfi", set())) | NONCRYPTO
    T_, I_ = alt_index(K)

    def mv(a, b):
        i = int(np.searchsorted(T_, a - 900, "right")) - 1; j = int(np.searchsorted(T_, b - 900, "right")) - 1
        return I_[j] / I_[i] - 1 if 0 <= i <= j < len(I_) else np.nan

    KR = kr_table(PER[per][3])
    rows = []
    for s in sorted(K):
        if s in bad or s.endswith("USDC") or "tb" not in K[s]:
            continue
        T, x = hourly(K[s])
        if len(T) < 24 * 40:
            continue
        fh = fund_hourly(T, funding(s))
        for e in events(T, x, fh):
            te = (e["Th"] + 1) * H + 900
            if not (t0 <= te < t1):
                continue
            i = idx_at(s, te)
            if i is None or int(K[s]["t"][i]) + 900 != te:
                continue
            r = dict(s=s, t=te, **e)
            main = None
            for nm, (hold, sl) in EXITS.items():
                z = trade(s, i, tp=None, sl=sl, hold_h=hold, side=-1)
                r[nm] = z["net"] if z else np.nan
                if nm == "n24":
                    main = z
            if main is None:
                continue
            r["why"] = main["why"]; r["fund"] = main["fund"]
            r["hed"] = main["net"] + mv(te, te + int(main["bars"]) * 900)
            pl = []
            for back in (45, 90, 135):
                j = idx_at(s, te - back * DAY)
                w = trade(s, j, tp=None, sl=0.25, hold_h=24, side=-1) if j is not None else None
                if w:
                    pl.append(w["net"])
            r["pl"] = float(np.mean(pl)) if pl else np.nan
            kr = KR.get(s)
            if kr is None:
                r["kr"] = np.nan
            else:
                m = (kr[0] >= te - 900 - DAY) & (kr[0] < te - 900)
                a, bn = kr[1][m].sum(), kr[2][m].sum()
                r["kr"] = a / (a + bn) if a + bn > 0 else 0.0
            rows.append(r)
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/s174_{per}.pkl")
    g = X.groupby("grp").size().to_dict() if len(X) else {}
    print(per, "событий", len(X), g, flush=True)


def ct(x, t):
    y = np.asarray(x, float); g = (np.asarray(t, float) // DAY).astype(np.int64); m = ~np.isnan(y); y, g = y[m], g[m]
    if len(y) < 5:
        return np.nan, np.nan, len(y)
    u = pd.Series(y - y.mean()).groupby(g).sum().values; G = len(u)
    se = np.sqrt((u ** 2).sum() * G / (G - 1)) / len(y) if G > 1 else np.nan
    return y.mean(), y.mean() / se if se and se > 0 else np.nan, len(y)


def diff(X, a, col="n24"):
    """Разница средних «a − остальные» в X (МНК на признак a) с ошибкой, кластеризованной по дню: (Δ, ошибка)."""
    X = X[X[col].notna()]
    y = X[col].to_numpy(float); d = a.loc[X.index].to_numpy(float)
    if d.sum() < 5 or (1 - d).sum() < 5:
        return np.nan, np.nan
    Z = np.c_[np.ones(len(y)), d]; A = np.linalg.inv(Z.T @ Z); beta = A @ Z.T @ y; u = y - Z @ beta
    g = (X["t"].to_numpy() // DAY).astype(np.int64)
    S = pd.DataFrame(Z * u[:, None]).groupby(g).sum().to_numpy(); G = len(S)
    V = A @ (S.T @ S) @ A * G / (G - 1)
    return float(beta[1]), float(np.sqrt(V[1, 1]))


def line(x, months, cut):
    if len(x) < 5:
        return f"n={len(x)}"
    m, t, n = ct(x.n24, x.t); mh, th, _ = ct(x.hed, x.t); md, td, _ = ct(x.n24 - x.pl, x.t)
    return (f"n={n:5d} ({n / months:5.1f}/мес) {m:+.2%} (t {t:+.1f}) | половины {x[x.t < cut].n24.mean():+.2%} / "
            f"{x[x.t >= cut].n24.mean():+.2%} | с хеджем {mh:+.2%} (t {th:+.1f}) | сверх плацебо {md:+.2%} (t {td:+.1f}) | "
            f"в плюсе {(x.n24 > 0).mean():.0%} | стопов {(x.why == 'стоп').mean():.0%}")


def report():
    A = {}
    for per, (a, b, cut, _) in PER.items():
        X = pd.read_pickle(f"{OUT}/s174_{per}.pkl"); X["per"] = per; A[per] = X
    print("Основная сделка — шорт 24 ч, стоп +25%.\n")
    comb, wts, ses = [], [], []
    for per, X in A.items():
        a, b, cut, _ = PER[per]; months = (ts(b) - ts(a)) / (30.4 * DAY); c = ts(cut)
        print(f"{per}:")
        for g, nm in (("dense", "плотная D ≥ 15%"), ("mid", "средняя 5–15%"), ("empty", "пустая D < 5%")):
            print(f"  {nm:16s} " + line(X[X.grp == g], months, c))
        Y = X[X.grp.isin(["dense", "empty"])]
        d, se = diff(Y, (Y.grp == "dense").astype(float))
        print(f"  Δ плотная − пустая: {d:+.2%} (t {d / se:+.1f})", end="")
        for col in ("n24s10", "n48", "n48s10", "hed"):
            dd, ss = diff(Y, (Y.grp == "dense").astype(float), col)
            print(f" | {col} {dd:+.2%} (t {dd / ss:+.1f})", end="")
        print()
        comb.append(d); ses.append(se); wts.append((X.grp == "dense").sum())
    w = np.array(wts, float) / sum(wts); dc = float(np.dot(w, comb)); sc = float(np.sqrt(np.dot(w ** 2, np.array(ses) ** 2)))
    print(f"\nΔ вместе (вес — число плотных событий): {dc:+.2%} (t {dc / sc:+.1f}); по периодам "
          + ", ".join(f"{d:+.2%}" for d in comb))
    Z = pd.concat(A.values(), ignore_index=True); Dn = Z[Z.grp == "dense"]
    md, td, n = ct(Dn.n24 - Dn.pl, Dn.t)
    print(f"плотная сверх плацебо, три периода: {md:+.2%} (t {td:+.1f}, n {n})")
    # доза — ответ: средние групп внутри периода, вместе с весами по числу плотных
    gm = {}
    for per, X in A.items():
        Dp = X[X.grp == "dense"].copy(); q = Dp.D.quantile([1 / 3, 2 / 3]).values
        Dp["tq"] = np.where(Dp.D < q[0], "T1", np.where(Dp.D < q[1], "T2", "T3"))
        vals = {"пустая": X[X.grp == "empty"].n24.mean(), "средняя": X[X.grp == "mid"].n24.mean(),
                "плотная": Dp.n24.mean(), **{f"плотная {k}": Dp[Dp.tq == k].n24.mean() for k in ("T1", "T2", "T3")}}
        for k, v in vals.items():
            gm.setdefault(k, []).append(v)
    print("доза — ответ (вместе): " + " | ".join(f"{k} {np.dot(w, v):+.2%}" for k, v in gm.items()))
    print("  по периодам: " + " | ".join(f"{k} " + "/".join(f"{x:+.2%}" for x in v) for k, v in gm.items()))
    # разрезы
    print("\nРазрезы плотной группы (вместе, основная сделка; с условием / без):")
    for nm, m in (("фандинг в зоне ≥ 0,01%/8 ч", Dn.fz >= 1e-4), ("доля покупок в зоне ≥ 55%", Dn.buy >= 0.55),
                  ("доля Кореи ≥ 20%", Dn.kr >= 0.20), ("молодая зона (3–10 сут)", Dn.young >= 0.5),
                  ("D ≥ 20%", Dn.D >= 0.20), ("памп +15% за 2 ч", Dn.pump)):
        a_, b_ = Dn[m.fillna(False).astype(bool)], Dn[~m.fillna(False).astype(bool)]
        ma, ta, na = ct(a_.n24, a_.t); mb, tb_, nb = ct(b_.n24, b_.t)
        print(f"  {nm:28s} n {na:5d} {ma:+.2%} (t {ta:+.1f}) | без n {nb:5d} {mb:+.2%} (t {tb_:+.1f}) | по периодам "
              + ", ".join(f"{a_[a_.per == p].n24.mean():+.2%}/{b_[b_.per == p].n24.mean():+.2%}" for p in A))
    # правило владельца на 2024–2026
    X = A["2024–2026"]; a, b, cut, _ = PER["2024–2026"]; months = (ts(b) - ts(a)) / (30.4 * DAY)
    print("\nПравило владельца, 2024–2026, плотная группа: " + line(X[X.grp == "dense"], months, ts(cut)))


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
