"""s294 Г7 — поток Binance до сброса суток Upbit для входов ⏰ (запись правил — ВЫВОДЫ.md).

F = (Σ(2·tb − qv) перпа за 15-мин свечи 23:00–23:45 + (2·tb − qv) спота за часовую свечу 23:00) / (Σqv перпа + qv спота),
сутки накануне входа ⏰ (вход 01:00 UTC); нет спота — только перп. Трети F внутри периода; Δ = верх − низ по шорту
10/25/48 (s88 S_10_25); для отчёта — 24 ч и 8 ч со стопом 10% (s277), F перпа, F спота, F к среднему той же монеты
в тот же час за 7 прошлых суток, ход перпа 23:00 → 00:00. Двойник — ⏰ при F < 67-го перцентиля F входов 2020–2024 гг.
Спот: 2024–2026 — s23/spot1h.pkl, раньше — месячные архивы часовых свечей Binance (кэш s23/spotcache папки периода,
как s118 и s175). Признаки — /home/user/mc_data/s294/g7_<период>.pkl, сводка — s294/g7_report.txt.
Запуск: python3 -I research/s294/g7.py <период>; сводка: python3 -I research/s294/g7.py report"""
import io
import os
import pickle
import re
import sys
import urllib.error
import urllib.request
import zipfile

import numpy as np
import pandas as pd

D = "/home/user/mc_data"
OUT = f"{D}/s294"
DAY, H, WEEK, BAR = 86400, 3600, 7 * 86400, 900
UA = {"User-Agent": "research-script/1.0"}
PER = {"2020–2022": dict(o9=f"{D}/s88/oos2020_trades.pkl", k=f"{D}/s117/k_2020.pkl", y0=2020, cache="/home/user/mc_2020/s23/spotcache", mo=24.0),
       "2022–2024": dict(o9=f"{D}/s88/oos_trades.pkl", k=f"{D}/s117/k_oos.pkl", y0=2022, cache="/home/user/mc_oos/s23/spotcache", mo=24.0),
       "2024–2026": dict(o9=f"{D}/s88/trades.pkl", k=f"{D}/s2/k2y.pkl", y0=None, cache=None, mo=24.5)}


def get(path, cache):
    fn = os.path.join(cache, path.replace("/", "_"))
    if os.path.exists(fn):
        return open(fn, "rb").read() or None
    try:
        with urllib.request.urlopen(urllib.request.Request(f"https://data.binance.vision/data/spot/{path}", headers=UA), timeout=60) as r:
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


def spot_old(s, y0, cache):
    """Часовые свечи спота XXXUSDT за период (s175 venue.spot_old): время открытия, qv, tb, сделки, закрытие."""
    months = [f"{y0}-{m:02d}" for m in (10, 11, 12)] + [f"{y0 + 1}-{m:02d}" for m in range(1, 13)] + \
             [f"{y0 + 2}-{m:02d}" for m in range(1, 10)]
    for b in dict.fromkeys((s, re.sub(r"^(1000000|100000|10000|1000)", "", s))):
        if any(get(f"monthly/klines/{b}USDT/1h/{b}USDT-1h-{m}.zip", cache) for m in (months[8], months[20], months[2])):
            out = []
            for m in months:
                out += rows(get(f"monthly/klines/{b}USDT/1h/{b}USDT-1h-{m}.zip", cache))
            return np.array(sorted(set(out))) if out else None
    return None


def entries(per):
    cfg = PER[per]
    X = pd.read_pickle(cfg["o9"])
    X = X[X.open9.astype(bool) & (X.r1 >= 0.05) & (X.share >= 0.20)].copy()
    X["s"] = [v[:-4] if v.endswith("USDT") else v for v in X.s.astype(str)]
    X["te"] = X.t.astype(float).astype(np.int64)
    X = X[["s", "te", "r1", "share", "S_10_25", "pl_S_10_25", "S_24h", "pl_S_24h"]].reset_index(drop=True)
    R = pd.read_pickle(f"{D}/s277_{per}.pkl")
    R = R[R.h == "⏰"]
    for ex, tag in (("24 ч", "h24"), ("8 ч", "h8")):
        g = R[R.ex == ex][["s", "te", "net", "hed", "pl", "stop"]].rename(columns={c: f"{tag}_{c}" for c in ("net", "hed", "pl", "stop")})
        X = X.merge(g, on=["s", "te"], how="left")
    return X


def flow(a, t, sp, Rd):
    """Поток за час [Rd − 1 ч, Rd): перп (сумма 2·tb − qv, сумма qv), спот (то же) — NaN, если свечей нет."""
    i0 = int(np.searchsorted(t, Rd - H))
    pn = pq = np.nan
    if i0 + 4 <= len(t) and t[i0] == Rd - H and t[i0 + 3] == Rd - BAR:
        qv = a["qv"][i0:i0 + 4].astype(float); tb = a["tb"][i0:i0 + 4].astype(float)
        if qv.sum() > 0:
            pn, pq = float((2 * tb - qv).sum()), float(qv.sum())
    sn = sq = np.nan
    if sp is not None and len(sp):
        j = int(np.searchsorted(sp[:, 0], Rd - H))
        if j < len(sp) and int(sp[j, 0]) == Rd - H and sp[j, 1] > 0:
            sn, sq = float(2 * sp[j, 2] - sp[j, 1]), float(sp[j, 1])
    return pn, pq, sn, sq


def comb(pn, pq, sn, sq):
    if not pq == pq:
        return np.nan
    if sq == sq:
        return (pn + sn) / (pq + sq)
    return pn / pq


def run(per):
    cfg = PER[per]
    X = entries(per)
    K = pickle.load(open(cfg["k"], "rb"))
    SP = pd.read_pickle(f"{D}/s23/spot1h.pkl") if cfg["y0"] is None else None
    spc = {}
    out = []
    for s, g in X.groupby("s"):
        a = K.get(s)
        if a is None:
            out += [dict(i=i) for i in g.index]
            continue
        t = a["t"].astype(np.int64)
        if SP is not None:
            sp = SP.get(s)
        else:
            if s not in spc:
                spc[s] = spot_old(s, cfg["y0"], cfg["cache"])
            sp = spc[s]
        c = a["c"].astype(float)
        for i, te in zip(g.index, g.te):
            R = int(te) - H                                     # 00:00 UTC — сброс суток Upbit
            pn, pq, sn, sq = flow(a, t, sp, R)
            F = comb(pn, pq, sn, sq)
            Fd = [comb(*flow(a, t, sp, R - d * DAY)) for d in range(1, 8)]
            Fd = [v for v in Fd if v == v]
            j1, j0 = int(np.searchsorted(t, R - BAR)), int(np.searchsorted(t, R - H - BAR))
            rp = c[j1] / c[j0] - 1 if j1 < len(t) and j0 < len(t) and t[j1] == R - BAR and t[j0] == R - H - BAR and c[j0] > 0 else np.nan
            out.append(dict(i=i, F=F, Fp=pn / pq if pq == pq else np.nan, Fs=sn / sq if sq == sq else np.nan,
                            Fa=F - np.mean(Fd) if len(Fd) >= 4 and F == F else np.nan, rpre=rp, spot=sq == sq))
    Fx = pd.DataFrame(out).set_index("i").sort_index()
    X = X.join(Fx)
    os.makedirs(OUT, exist_ok=True)
    X.to_pickle(f"{OUT}/g7_{per}.pkl")
    print(f"{per}: входов ⏰ {len(X)}, с F {X.F.notna().sum()}, со спотом {int(X.spot.fillna(False).sum())}; "
          f"S_10_25 {X.S_10_25.mean():+.2%}", flush=True)


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
    R = {p: pd.read_pickle(f"{OUT}/g7_{p}.pkl") for p in PER}
    L = []
    P = lambda s="": (print(s), L.append(s))  # noqa: E731
    P("s294 Г7 — поток Binance 23:00–00:00 UTC перед входом ⏰ (Δ = верхняя треть − нижняя по шорту)")
    for col, lab in (("F", "F перп + спот (основной)"), ("Fp", "F перпа"), ("Fs", "F спота"), ("Fa", "F к среднему монеты за 7 сут"),
                     ("rpre", "ход перпа 23:00 → 00:00")):
        P(); P(f"== {lab} ==")
        for ex, pl_col, lab2 in (("S_10_25", "pl_S_10_25", "10/25/48 (основной)"), ("h24_net", "h24_pl", "24 ч, стоп 10%"),
                                 ("h8_net", "h8_pl", "8 ч, стоп 10%"), ("h24_hed", None, "24 ч, с хеджем альтов")):
            ms, ses, sg, cells = [], [], [], []
            for per, X in R.items():
                Y = X[X[col].notna() & X[ex].notna()]
                q1, q2 = Y[col].quantile([1 / 3, 2 / 3])
                top, bot, mid = Y[Y[col] > q2], Y[Y[col] <= q1], Y[(Y[col] > q1) & (Y[col] <= q2)]
                m1, _, n1, s1 = ct(top[ex], top.te); m2, _, n2, s2 = ct(bot[ex], bot.te); m3 = mid[ex].mean()
                d, se = m1 - m2, np.hypot(s1, s2)
                ms.append(d); ses.append(se); sg.append(d < 0)
                cells.append(f"{per}: низ {m2:+.2%} / сер. {m3:+.2%} / верх {m1:+.2%} (n {n2}/{n1}), Δ {d:+.2%} (t {d / se:+.1f})")
            m, t = combine(ms, ses)
            P(f"  {lab2}: вместе Δ {m:+.2%} (t {t:+.1f}); Δ < 0 во всех — {'да' if all(sg) else 'нет'}")
            for c in cells:
                P(f"    {c}")
    # двойник по постоянной границе
    old = pd.concat([R["2020–2022"], R["2022–2024"]])
    thr = float(old.F.quantile(2 / 3))
    P(); P(f"== двойник «⏰ при F < {thr:+.4f}» (67-й перцентиль F входов 2020–2024 гг.; без F — вход) ==")
    for per, X in R.items():
        keep = ~(X.F >= thr)
        for ex, pl_col, lab2 in (("S_10_25", "pl_S_10_25", "10/25/48"), ("h24_net", "h24_pl", "24 ч")):
            A = X[keep & X[ex].notna()]; B = X[X[ex].notna()]
            ma, ta, na, _ = ct(A[ex], A.te); mb, tb_, nb, _ = ct(B[ex], B.te)
            med = A.te.median()
            h1, h2 = A[A.te <= med][ex].mean(), A[A.te > med][ex].mean()
            mp, tp, _, _ = ct(A[ex] - A[pl_col], A.te)
            P(f"  {per} {lab2}: двойник {ma:+.2%} (t {ta:+.1f}, {na / PER[per]['mo']:.1f} в мес., половины {h1:+.2%} / {h2:+.2%}, "
              f"сверх плацебо {mp:+.2%} t {tp:+.1f}) против ⏰ {mb:+.2%} (t {tb_:+.1f}, {nb / PER[per]['mo']:.1f} в мес.)")
    open(f"{OUT}/g7_report.txt", "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
