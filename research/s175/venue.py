"""s175 — Г2 «выбор площадки» (гипотеза и порог — ВЫВОДЫ.md, записаны до расчёта): срез раз в сутки (закрытие часа 00–01 UTC),
z = ln(оборот перпа / оборот спота за 24 ч) − медиана за 2–30 сут; стоящая цена (|r24| ≤ 3%). События z ≥ ln 2, контроль
|z| ≤ ln 1,25; кулдаун 7 сут внутри группы. Шорт 7 сут, стоп +50% (основной), 48 ч / +25%. Спот 2024–2026 — s23/spot1h.pkl,
раньше — кэш архива Binance s23/spotcache в папке периода (s118). Запуск:
  2024–2026: cd /home/user/mc_data && python3 <repo>/research/s175/venue.py 2024–2026
  2022–2024: cd /home/user/mc_oos && MC_K=/home/user/mc_data/s117/k_oos.pkl MC_F=/home/user/mc_data/s117/fund_oos.pkl python3 … 2022–2024
  2020–2022: cd /home/user/mc_2020 && MC_K=/home/user/mc_data/s117/k_2020.pkl MC_F=/home/user/mc_data/s117/fund_2020.pkl python3 … 2020–2022
  сводка: python3 <repo>/research/s175/venue.py report"""
import io
import os
import re
import sys
import urllib.error
import urllib.request
import zipfile

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s141", "s174"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from trapped import NONCRYPTO, ct, diff, hourly, roll_sum  # noqa: E402

OUT, DAY, H = "/home/user/mc_data", 86400, 3600
PER = {"2020–2022": ("2020-10-01", "2022-10-01", "2021-10-01", 2020),
       "2022–2024": ("2022-10-01", "2024-10-01", "2023-10-01", 2022),
       "2024–2026": ("2024-10-01", "2026-10-17", "2025-12-01", None)}
EXITS = {"n7": (168, 0.50), "n2": (48, 0.25)}
LN2, LNC, FLAT, V24, COOL = np.log(2), np.log(1.25), 0.03, 5e6, 7 * 24


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def get(path):
    fn = os.path.join("s23/spotcache", path.replace("/", "_"))
    if os.path.exists(fn):
        return open(fn, "rb").read() or None
    try:
        with urllib.request.urlopen(f"https://data.binance.vision/data/spot/{path}", timeout=60) as r:
            data = r.read()
        open(fn, "wb").write(data)
        return data
    except urllib.error.HTTPError as e:
        if e.code == 404:
            open(fn, "wb").close()
    except Exception:
        pass
    return None


def rows(data):
    if not data:
        return []
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return []
    out = []
    for ln in z.read(z.namelist()[0]).decode().splitlines():
        p = ln.split(",")
        if p and p[0][:1].isdigit() and len(p) > 10:
            t = int(p[0]); t = t // 1_000_000 if t > 10 ** 14 else t // 1000
            out.append((t, float(p[7]), float(p[10]), float(p[8]), float(p[4])))
    return out


def spot_old(s, y0):
    months = [f"{y0}-{m:02d}" for m in (10, 11, 12)] + [f"{y0 + 1}-{m:02d}" for m in range(1, 13)] + \
             [f"{y0 + 2}-{m:02d}" for m in range(1, 10)]
    for b in (s, re.sub(r"^(1000000|100000|10000|1000)", "", s)):
        if any(get(f"monthly/klines/{b}USDT/1h/{b}USDT-1h-{m}.zip") for m in (months[8], months[20], months[2])):
            out = []
            for m in months:
                out += rows(get(f"monthly/klines/{b}USDT/1h/{b}USDT-1h-{m}.zip"))
            return np.array(sorted(set(out))) if out else None
    return None


def rate_x(coin, T, cache={}):
    """Загрузка пула (s40): ставка маржи на момент T к 10-му перцентилю ставок за 30 сут; нет файла — None."""
    if coin not in cache:
        p = f"{OUT}/s11/rates/{coin}.csv"
        cache[coin] = np.loadtxt(p, delimiter=",", ndmin=2) if os.path.exists(p) else None
    a = cache[coin]
    if a is None:
        return None
    if not len(a):
        return np.nan
    i = int(np.searchsorted(a[:, 0], T, "right")) - 1
    m = (a[:, 0] > T - 30 * DAY) & (a[:, 0] <= T)
    if i < 0 or m.sum() < 5:
        return np.nan
    q = np.quantile(a[m, 1], 0.1)
    return a[i, 1] / q if q > 0 else np.nan


def run(per):
    from common import K, funding, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    from flow_test import alt_index  # noqa: E402
    t0, t1, _, y0 = ts(PER[per][0]), ts(PER[per][1]), PER[per][2], PER[per][3]
    kind = pd.read_pickle(f"{OUT}/s12/perp_kind.pkl")
    bad = set(kind.get("tradfi", set())) | NONCRYPTO | {"BTC", "ETH"}
    SP = pd.read_pickle(f"{OUT}/s23/spot1h.pkl") if y0 is None else None
    T_, I_ = alt_index(K)

    def mv(a, b):
        i = int(np.searchsorted(T_, a - 900, "right")) - 1; j = int(np.searchsorted(T_, b - 900, "right")) - 1
        return I_[j] / I_[i] - 1 if 0 <= i <= j < len(I_) else np.nan

    def deal(s, te, extra=True):
        i = idx_at(s, te)
        if i is None or int(K[s]["t"][i]) + 900 != te:
            return None
        r = {}
        for nm, (hold, sl) in EXITS.items():
            z = trade(s, i, tp=None, sl=sl, hold_h=hold, side=-1)
            r[nm] = z["net"] if z else np.nan
            if nm == "n7":
                if z is None:
                    return None
                r["why"] = z["why"]; r["hed"] = z["net"] + mv(te, te + int(z["bars"]) * 900)
        if extra:
            pl = []
            for back in (45, 90, 135):
                j = idx_at(s, te - back * DAY)
                w = trade(s, j, tp=None, sl=0.50, hold_h=168, side=-1) if j is not None else None
                if w:
                    pl.append(w["net"])
            r["pl"] = float(np.mean(pl)) if pl else np.nan
        return r

    rows_, cross = [], []
    nsp = 0
    for s in sorted(K):
        if s in bad or s.endswith("USDC") or "tb" not in K[s]:
            continue
        sp = SP.get(s) if SP is not None else spot_old(s, y0)
        if sp is None or not len(sp):
            continue
        nsp += 1
        T, x = hourly(K[s])
        if len(T) < 24 * 40:
            continue
        sp = np.asarray(sp, float); Hs = sp[:, 0].astype(np.int64) // H
        sq = np.zeros(len(T)); m_ = (Hs >= T[0]) & (Hs <= T[-1]); sq[(Hs[m_] - T[0]).astype(int)] = sp[m_, 1]
        qv, c = x["qv"], x["c"]
        v24, s24, tb24 = roll_sum(qv, 24), roll_sum(sq, 24), roll_sum(x["tb"], 24)
        with np.errstate(divide="ignore", invalid="ignore"):
            lps = np.log(v24 / s24)
        nz = np.flatnonzero(qv > 0)
        if not len(nz):
            continue
        first = nz[0]
        fr = funding(s)
        coin = re.sub(r"^(1000000|100000|10000|1000)", "", s)
        last = {"event": -10 ** 9, "control": -10 ** 9}
        for i in np.flatnonzero(T % 24 == 0):
            if i < first + 744 or v24[i] < V24 or s24[i] <= 0 or not np.isfinite(lps[i]):
                continue
            te = (int(T[i]) + 1) * H + 900
            if not (t0 <= te < t1):
                continue
            hist = lps[i - 720:i - 24:24]; hist = hist[np.isfinite(hist)]
            if len(hist) < 20:
                continue
            z = lps[i] - np.median(hist); r24 = c[i] / c[i - 24] - 1
            if abs(r24) > FLAT:
                continue
            cross.append((s, te, z))
            g = "event" if z >= LN2 else ("control" if abs(z) <= LNC else None)
            if g is None or i - last[g] < COOL:
                continue
            r = deal(s, te)
            if r is None:
                continue
            last[g] = i
            ts_ = te - 900
            m = (fr[:, 0] > ts_ - DAY) & (fr[:, 0] <= ts_) if len(fr) else np.zeros(0, bool)
            rx = rate_x(coin, ts_) if y0 is None else np.nan
            rows_.append(dict(s=s, t=te, grp=g, z=z, r24=r24, buy=tb24[i] / v24[i], f24=float(fr[m, 1].sum()) if m.any() else np.nan,
                              x=np.nan if rx is None else rx, nomargin=(rx is None) if y0 is None else np.nan, **r))
    X = pd.DataFrame(rows_)
    X.to_pickle(f"{OUT}/s175_{per}.pkl")
    # поперечный вариант: каждый день 5 с наибольшим z и 5 с наименьшим среди стоящих монет
    C = pd.DataFrame(cross, columns=["s", "t", "z"]); cr = []
    for te, g in C.groupby("t"):
        if len(g) < 20:
            continue
        g = g.sort_values("z")
        for side, sub in (("top", g.tail(5)), ("bottom", g.head(5))):
            for r in sub.itertuples():
                d = deal(r.s, int(te), extra=False)
                if d:
                    cr.append(dict(s=r.s, t=int(te), side=side, z=r.z, **d))
    pd.DataFrame(cr).to_pickle(f"{OUT}/s175_{per}_cross.pkl")
    print(per, "монет со спотом", nsp, "| событий", int((X.grp == "event").sum()) if len(X) else 0,
          "контроль", int((X.grp == "control").sum()) if len(X) else 0, "| поперечных сделок", len(cr), flush=True)


def line(x, months, cut, col="n7"):
    if len(x) < 5:
        return f"n={len(x)}"
    m, t, n = ct(x[col], x.t); mh, th, _ = ct(x.hed, x.t)
    md, td, _ = ct(x[col] - x.pl, x.t) if "pl" in x else (np.nan, np.nan, 0)
    return (f"n={n:5d} ({n / months:5.1f}/мес) {m:+.2%} (t {t:+.1f}) | половины {x[x.t < cut][col].mean():+.2%} / "
            f"{x[x.t >= cut][col].mean():+.2%} | с хеджем {mh:+.2%} (t {th:+.1f}) | сверх плацебо {md:+.2%} (t {td:+.1f}) | "
            f"в плюсе {(x[col] > 0).mean():.0%} | стопов {(x.why == 'стоп').mean():.0%}")


def report():
    A = {}
    for per in PER:
        X = pd.read_pickle(f"{OUT}/s175_{per}.pkl"); X["per"] = per; A[per] = X
    print("Основная сделка — шорт 7 сут, стоп +50%.\n")
    comb, ses, wts = [], [], []
    for per, X in A.items():
        a, b, cut, _ = PER[per]; months = (ts(b) - ts(a)) / (30.4 * DAY); c = ts(cut)
        print(f"{per}:")
        for g, nm in (("event", "событие z ≥ ln 2"), ("control", "контроль |z| ≤ ln 1,25")):
            print(f"  {nm:22s} " + line(X[X.grp == g], months, c))
        Y = X[X.grp.isin(["event", "control"])]
        d, se = diff(Y, (Y.grp == "event").astype(float), "n7")
        d2, s2 = diff(Y, (Y.grp == "event").astype(float), "n2"); dh, sh = diff(Y, (Y.grp == "event").astype(float), "hed")
        print(f"  Δ событие − контроль: {d:+.2%} (t {d / se:+.1f}) | 48 ч {d2:+.2%} (t {d2 / s2:+.1f}) | с хеджем {dh:+.2%} (t {dh / sh:+.1f})")
        Cx = pd.read_pickle(f"{OUT}/s175_{per}_cross.pkl")
        dc_, sc_ = diff(Cx.reset_index(drop=True), (Cx.reset_index(drop=True).side == "top").astype(float), "n7")
        mt, tt, nt = ct(Cx[Cx.side == "top"].n7, Cx[Cx.side == "top"].t)
        print(f"  поперечный: верхние 5 по z {mt:+.2%} (t {tt:+.1f}, n {nt}) | разница с нижними 5 {dc_:+.2%} (t {dc_ / sc_:+.1f})")
        comb.append(d); ses.append(se); wts.append((X.grp == "event").sum())
    w = np.array(wts, float) / sum(wts); dc = float(np.dot(w, comb)); sc = float(np.sqrt(np.dot(w ** 2, np.array(ses) ** 2)))
    print(f"\nΔ вместе (вес — число событий): {dc:+.2%} (t {dc / sc:+.1f}); по периодам " + ", ".join(f"{d:+.2%}" for d in comb))
    Z = pd.concat(A.values(), ignore_index=True); E = Z[Z.grp == "event"]
    md, td, n = ct(E.n7 - E.pl, E.t)
    print(f"события сверх плацебо, три периода: {md:+.2%} (t {td:+.1f}, n {n})")
    gm = {}
    for per, X in A.items():
        Ev = X[X.grp == "event"]
        for k, v in (("контроль", X[X.grp == "control"].n7.mean()), ("z ln2–ln3", Ev[Ev.z < np.log(3)].n7.mean()),
                     ("z ≥ ln3", Ev[Ev.z >= np.log(3)].n7.mean())):
            gm.setdefault(k, []).append(v)
    print("доза — ответ (вместе): " + " | ".join(f"{k} {np.dot(w, np.nan_to_num(v)):+.2%}" for k, v in gm.items()))
    print("  по периодам: " + " | ".join(f"{k} " + "/".join(f"{x:+.2%}" for x in v) for k, v in gm.items()))
    print("\nРазрезы событий (вместе; с условием / без):")
    for nm, m in (("покупки перпа ≤ 50% (сильнее)", E.buy <= 0.5), ("фандинг за 24 ч ≥ 0 (слабее)", E.f24 >= 0),
                  ("загрузка пула ≥ 2 (сильнее)", E.x >= 2), ("нет займа на марже (сильнее)", E.nomargin == True)):  # noqa: E712
        a_, b_ = E[m.fillna(False).astype(bool)], E[~m.fillna(False).astype(bool)]
        ma, ta, na = ct(a_.n7, a_.t); mb, tb_, nb = ct(b_.n7, b_.t)
        print(f"  {nm:32s} n {na:4d} {ma:+.2%} (t {ta:+.1f}) | без n {nb:4d} {mb:+.2%} (t {tb_:+.1f})")
    X = A["2024–2026"]; a, b, cut, _ = PER["2024–2026"]; months = (ts(b) - ts(a)) / (30.4 * DAY)
    print("\nПравило владельца, 2024–2026, события: " + line(X[X.grp == "event"], months, ts(cut)))


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
