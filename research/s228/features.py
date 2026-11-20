"""s228 — 25 признаков без займа и канала и исход «шорт 4 ч с хеджем индексом альтов» на сетке 4 ч (метод — ВЫВОДЫ.md,
записан до расчёта). Определения — как research/s216/features.py (рынок, метрики позиций, btc24) и research/s225/features.py
(«необычно для монеты» за 30 сут); здесь они посчитаны сразу для всех отметок монеты (накопленные суммы вместо циклов).

Режимы:
- check — наблюдения канала из s225_feat.pkl, метрики из s22/metrics_full (все сохранённые сутки, как в s225); сравнение
  25 признаков с s225_feat.pkl: совпадение — |разница| ≤ 1e-6·max(1, |x|) или оба пустые;
- full — все отметки 4 ч монет вселенной (s228/met/*.npz) с 01.10.2024 по 19.11.2026, фьючерс старше суток; признак
  «в канале» по панели s224/work/s21/panel.pkl; исход y (шорт 4 ч, стоп 10%, + ход индекса альтов) и время выхода u_e →
  s228/feat.pkl.
Запуск из /home/user/mc_data: MC_K=s224/k_d.pkl MC_F=s224/fund_d.pkl python3 <repo>/research/s228/features.py check|full"""
import datetime
import glob
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s187"))
import fastbt as FB  # noqa: E402

K, funding, live = FB.K, FB.funding, FB.live
H, DAY, W, G4 = 3600, 86400, 30 * 86400, 4 * 3600
MINP = 48
T0 = int(datetime.datetime(2024, 10, 1, tzinfo=datetime.timezone.utc).timestamp())
T1 = int(datetime.datetime(2026, 11, 19, 20, tzinfo=datetime.timezone.utc).timestamp())
FEATS = ("r4", "r24", "r72", "vol24", "qv24", "qvx", "tb4", "f8", "f24", "doi4", "doi24", "lsr_top", "lsr_acc", "dlsr24",
         "tkr", "oiq", "btc24", "zr4", "zr24", "zqv", "zoi4", "zoi24", "zlsr", "zlsrt", "zf")


def wstats(x, a, b):
    """Для окон x[a:b] (a, b — массивы границ): число конечных значений, их среднее и ст. откл. (ddof 0). Считается
    накопленными суммами; окна почти без разброса (ст. откл. ≤ 1e-6 общего масштаба ряда — постоянный фандинг, застывший
    OI) пересчитываются как в s225 (np.mean, np.std по окну), чтобы повторить его и в вырожденных случаях."""
    f = np.isfinite(x)
    m0 = float(x[f].mean()) if f.any() else 0.0
    scale = float(x[f].std()) if f.any() else 0.0
    xc = np.where(f, x - m0, 0.0)
    n = np.r_[0, np.cumsum(f)]; s1 = np.r_[0.0, np.cumsum(xc)]; s2 = np.r_[0.0, np.cumsum(xc * xc)]
    cnt = n[b] - n[a]
    with np.errstate(invalid="ignore", divide="ignore"):
        mu = (s1[b] - s1[a]) / cnt + m0
        sd = np.sqrt(np.maximum((s2[b] - s2[a]) / cnt - ((s1[b] - s1[a]) / cnt) ** 2, 0.0))
    for i in np.flatnonzero((cnt > 0) & (sd <= 1e-6 * (np.abs(mu) + scale))):
        w = x[a[i]:b[i]]; w = w[np.isfinite(w)]
        mu[i], sd[i] = w.mean(), w.std()
    return cnt, mu, sd


def market(s, TT, out):
    """r4 … tb4, f8, f24 — как s216.market_features; zr4, zr24, zqv — как s225."""
    a = K[s]; t = a["t"].astype(np.int64) + 900
    c, qv, tb = (a[x].astype(float) for x in ("c", "qv", "tb"))
    I = np.searchsorted(t, TT, "right") - 1
    ok = (I >= 672) & (t[np.maximum(I, 0)] == TT)
    j = np.flatnonzero(ok); Io = I[ok]
    if len(j):
        out["r4"][j] = c[Io] / c[Io - 16] - 1; out["r24"][j] = c[Io] / c[Io - 96] - 1; out["r72"][j] = c[Io] / c[Io - 288] - 1
        lr = np.diff(np.log(c))
        Wv = np.lib.stride_tricks.sliding_window_view(lr, 96)
        out["vol24"][j] = Wv[Io - 96].std(axis=1)
        cs = np.r_[0.0, np.cumsum(qv)]; ct = np.r_[0.0, np.cumsum(tb)]
        q24 = cs[Io + 1] - cs[Io - 95]; q7 = (cs[Io + 1] - cs[Io - 671]) / 7
        out["qv24"][j] = q24
        with np.errstate(invalid="ignore", divide="ignore"):
            out["qvx"][j] = np.where(q7 > 0, q24 / q7, np.nan)
            q4 = cs[Io + 1] - cs[Io - 15]
            out["tb4"][j] = np.where(q4 > 0, (ct[Io + 1] - ct[Io - 15]) / q4, np.nan)
        fr = funding(s)
        if len(fr):
            ft = fr[:, 0].astype(np.int64); fv = fr[:, 1]
            k = np.searchsorted(ft, TT[j], "right") - 1
            okf = k >= 1; jf = j[okf]; kf = k[okf]
            gap = (ft[kf] - ft[kf - 1]) / H
            with np.errstate(invalid="ignore", divide="ignore"):
                out["f8"][jf] = np.where(gap > 0, fv[kf] * 8 / gap, np.nan)
            cf = np.r_[0.0, np.cumsum(fv)]
            out["f24"][jf] = cf[kf + 1] - cf[np.searchsorted(ft, TT[jf] - DAY, "right")]
    # zr4, zr24: ln-ход к ст. откл. таких ходов по часовым закрытиям за [T − 30 сут, T)
    m = t % H == 0
    th, ch = t[m], c[m]
    l4 = np.full(len(th), np.nan); l4[4:] = np.log(ch[4:] / ch[:-4])
    l24 = np.full(len(th), np.nan); l24[24:] = np.log(ch[24:] / ch[:-24])
    a_, b_ = np.searchsorted(th, TT - W, "left"), np.searchsorted(th, TT, "left")
    for name, ser, cur in (("zr4", l4, "r4"), ("zr24", l24, "r24")):
        n, _, sd = wstats(ser, a_, b_)
        sd = np.where(n >= MINP, sd, np.nan)
        r = out[cur]
        with np.errstate(invalid="ignore", divide="ignore"):
            out[name] = np.where((sd > 0) & np.isfinite(r), np.log1p(r) / sd, np.nan)
    # zqv: ln(оборот за 24 ч / медиана оборотов за 24 ч в T − k сут, k = 1 … 30), нужно ≥ 20 значений
    n15 = len(t); ar = np.arange(n15)
    cs = np.r_[0.0, np.cumsum(qv)]
    q24s = np.where(ar >= 95, cs[ar + 1] - cs[np.maximum(ar - 95, 0)], np.nan)
    d = TT[:, None] - DAY * np.arange(1, 31)[None, :]
    ii = np.searchsorted(t, d, "right") - 1
    okd = (ii >= 0) & (t[np.maximum(ii, 0)] == d)
    qs = np.where(okd, q24s[np.maximum(ii, 0)], np.nan)
    qs = np.where(np.isfinite(qs) & (qs > 0), qs, np.nan)
    cnt = np.isfinite(qs).sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        med = np.nanmedian(np.where(cnt[:, None] > 0, qs, 0.0), axis=1)
        qn = out["qv24"]
        out["zqv"] = np.where((cnt >= 20) & (qn > 0), np.log(qn / med), np.nan)


def metric(TT, tm, V, out):
    """doi4 … tkr, oiq — как s216.metric_features (строка не позже T − 1 ч, не старше часа); zoi4, zoi24, zlsr, zlsrt — как
    s225 (окно строк [T − 1 ч − 30 сут, T − 1 ч), не меньше 48 строк). V — столбцы OI, OI $, топ-счета, топ-позиции,
    все счета, агрессивные объёмы."""
    if not len(tm):
        return

    def val(x, col):
        i = np.searchsorted(tm, x, "right") - 1
        ok = (i >= 0) & (x - tm[np.maximum(i, 0)] < H)
        return np.where(ok, V[np.maximum(i, 0), col], np.nan)
    Tp = TT - H
    o, o4, o24 = val(Tp, 0), val(Tp - 4 * H, 0), val(Tp - DAY, 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        out["doi4"] = np.where(np.isfinite(o4) & (o4 > 0), o / o4 - 1, np.nan)
        out["doi24"] = np.where(np.isfinite(o24) & (o24 > 0), o / o24 - 1, np.nan)
    oiv = val(Tp, 1)
    out["lsr_top"] = val(Tp, 3); out["lsr_acc"] = val(Tp, 4); out["dlsr24"] = val(Tp, 4) - val(Tp - DAY, 4)
    out["tkr"] = val(Tp, 5)
    with np.errstate(invalid="ignore", divide="ignore"):
        out["oiq"] = np.where(out["qv24"] > 0, oiv / out["qv24"], np.nan)
    oi = V[:, 0]
    o4s = np.full(len(tm), np.nan); o24s = np.full(len(tm), np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        okp = (tm[4:] - tm[:-4] == 4 * H) & (oi[:-4] > 0) & (oi[4:] > 0)
        o4s[4:][okp] = np.log(oi[4:][okp] / oi[:-4][okp])
        okq = (tm[24:] - tm[:-24] == DAY) & (oi[:-24] > 0) & (oi[24:] > 0)
        o24s[24:][okq] = np.log(oi[24:][okq] / oi[:-24][okq])
    a_, b_ = np.searchsorted(tm, Tp - W, "left"), np.searchsorted(tm, Tp, "left")
    rows = (b_ - a_) >= MINP
    for name, ser, cur in (("zoi4", o4s, "doi4"), ("zoi24", o24s, "doi24")):
        n, _, sd = wstats(ser, a_, b_)
        sd = np.where(rows & (n >= MINP), sd, np.nan)
        dd = out[cur]
        with np.errstate(invalid="ignore", divide="ignore"):
            out[name] = np.where((sd > 0) & np.isfinite(dd) & (dd > -1), np.log1p(dd) / sd, np.nan)
    for name, col, cur in (("zlsr", 4, "lsr_acc"), ("zlsrt", 3, "lsr_top")):
        n, mu, sd = wstats(V[:, col].astype(float), a_, b_)
        c = out[cur]
        with np.errstate(invalid="ignore", divide="ignore"):
            out[name] = np.where(rows & (n >= MINP) & (sd > 0) & np.isfinite(c), (c - mu) / sd, np.nan)


def zfund(s, TT, out):
    """zf — как s225: (f8 − среднее) / ст. откл. начислений на 8 ч за (T − 30 сут, T], не меньше 48."""
    fr = funding(s)
    if len(fr) <= 1:
        return
    ft = fr[:, 0].astype(np.int64); gap = np.r_[np.nan, np.diff(ft) / H]
    with np.errstate(invalid="ignore", divide="ignore"):
        f8s = np.where(gap > 0, fr[:, 1] * 8 / gap, np.nan)
    a_, b_ = np.searchsorted(ft, TT - W, "right"), np.searchsorted(ft, TT, "right")
    n, mu, sd = wstats(f8s, a_, b_)
    c = out["f8"]
    with np.errstate(invalid="ignore", divide="ignore"):
        out["zf"] = np.where((n >= MINP) & (sd > 0) & np.isfinite(c), (c - mu) / sd, np.nan)


_btc = {}


def btc24(TT):
    if not _btc:
        _btc["t"] = K["BTC"]["t"].astype(np.int64) + 900; _btc["c"] = K["BTC"]["c"].astype(float)
    bt, bc = _btc["t"], _btc["c"]
    i = np.searchsorted(bt, TT, "right") - 1; j = np.searchsorted(bt, TT - DAY, "right") - 1
    return np.where((i >= 0) & (j >= 0), bc[np.maximum(i, 0)] / bc[np.maximum(j, 0)] - 1, np.nan)


def build(s, TT, tm, V):
    out = {k: np.full(len(TT), np.nan) for k in FEATS}
    if s in K:
        market(s, TT, out)
    metric(TT, tm, V, out)
    if s in K:
        zfund(s, TT, out)
    out["btc24"] = btc24(TT)
    return out


def met_full(s):
    """Метрики s22/metrics_full монеты — все сохранённые сутки, как в s225 (без удаления повторов)."""
    fl = sorted(glob.glob(f"s22/metrics_full/{s}/*.npy"))
    arr = [x for x in (np.load(f) for f in fl) if len(x)]
    if not arr:
        return np.zeros(0, np.int64), np.zeros((0, 6))
    M = np.vstack(arr); M = M[np.argsort(M[:, 0])]
    return M[:, 0].astype(np.int64), M[:, 1:]


def check():
    F = pd.read_pickle("s225_feat.pkl")
    res = {k: [] for k in FEATS}
    for s, g in F.groupby("s"):
        TT = g["T"].to_numpy(np.int64)
        tm, V = met_full(s)
        out = build(s, TT, tm, V)
        for k in FEATS:
            a, b = out[k], g[k].to_numpy(float)
            res[k].append((np.isnan(a) & np.isnan(b)) | (np.abs(a - b) <= 1e-6 * np.maximum(1.0, np.abs(b))))
    print(f"сверка с s225_feat.pkl: наблюдений {len(F)}, монет {F.s.nunique()}")
    for k in FEATS:
        x = np.concatenate(res[k])
        print(f"  {k:8s} совпало {x.mean():7.2%}  заполнено в s225 {np.isfinite(F[k]).mean():6.1%}")


def full():
    P = pd.read_pickle("s224/work/s21/panel.pkl")
    P = P[P["T"] % G4 == 0]
    inch = set(zip(P.s, P["T"].astype(np.int64)))
    parts = []
    files = sorted(glob.glob("s228/met/*.npz"))
    for n, p in enumerate(files):
        s = os.path.basename(p)[:-4]
        if s not in K:
            continue
        lo, hi = live(s)
        if not np.isfinite(lo):
            continue
        t0 = max(T0, int(np.ceil((lo + DAY + 900) / G4)) * G4)
        TT = np.arange(t0, min(T1, int(hi)) + 1, G4, dtype=np.int64)
        if not len(TT):
            continue
        z = np.load(p); tm, V = z["t"], z["v"].astype(float)
        out = build(s, TT, tm, V)
        # исход: шорт 4 ч, стоп 10%, + ход индекса альтов (как y_hs4 в s223)
        t = K[s]["t"].astype(np.int64)
        st = TT - 900; I = np.searchsorted(t, st)
        ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == st)
        ok &= t[np.minimum(I, len(t) - 1)] >= lo + DAY
        y = np.full(len(TT), np.nan); ue = np.full(len(TT), np.nan)
        if ok.any():
            okt, net, _, _, tend = FB.trades(s, I[ok], 0.10, 4, -1)
            mv = FB.alt_mv(t[I[ok]] + 900, tend)
            y[ok] = np.where(okt, net + mv, np.nan); ue[ok] = np.where(okt, tend, np.nan)
        df = pd.DataFrame({k: out[k].astype(np.float32) for k in FEATS})
        df.insert(0, "T", TT); df.insert(0, "s", s)
        df["inch"] = [(s, int(x)) in inch for x in TT]
        df["y"] = y; df["u_e"] = ue
        parts.append(df[np.isfinite(df.y)])
        if n % 50 == 0:
            print(f"{n + 1}/{len(files)} {s}: отметок {len(TT)}, с исходом {int(np.isfinite(y).sum())}", flush=True)
    D = pd.concat(parts, ignore_index=True)
    D["s"] = D.s.astype("category")
    D = D.sort_values(["T", "s"]).reset_index(drop=True)
    D.to_pickle("s228/feat.pkl")
    print("готово:", D.shape, "в канале", int(D.inch.sum()), "\nзаполнено:",
          {k: round(float(np.isfinite(D[k]).mean()), 2) for k in FEATS}, flush=True)


if __name__ == "__main__":
    {"check": check, "full": full}[sys.argv[1]]()
