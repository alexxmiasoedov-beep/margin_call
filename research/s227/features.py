"""s227 — часовая панель CYBER: признаки по всем собранным данным (только данные до T) и 8 исходов (лонг и шорт на 1 / 4 /
24 / 72 ч со стопами 5 / 10 / 15 / 25%, комиссия и фандинг — логика s187/fastbt; с хеджем индексом альтов — для отчёта).
Метод — ВЫВОДЫ.md (записан до расчёта доходов). Шаги:
  python3 <repo>/research/s227/features.py prep    — свечи и фандинг CYBER и BTC за 08.2023–11.2026, индекс альтов (s227/k.pkl,
                                                     s227/f.pkl, s227/alt.npy);
  MC_K=s227/k.pkl MC_F=s227/f.pkl python3 <repo>/research/s227/features.py — панель: s227_feat.pkl (до 18.10.2026),
                                                     s227c_feat.pkl (эпоха канала, с 22.02.2025), s227D_feat.pkl (22.10–19.11.2026).
Запуск из /home/user/mc_data."""
import datetime
import glob
import gzip
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
UTC = datetime.timezone.utc
H, D, B = 3600, 86400, 900
S = "CYBER"
T_START = int(datetime.datetime(2023, 8, 22, tzinfo=UTC).timestamp())
C_END = int(datetime.datetime(2026, 10, 18, 23, tzinfo=UTC).timestamp())
D0, D1 = int(datetime.datetime(2026, 10, 22, tzinfo=UTC).timestamp()), int(datetime.datetime(2026, 11, 19, 20, tzinfo=UTC).timestamp())
CH0 = int(datetime.datetime(2025, 2, 22, tzinfo=UTC).timestamp())
OUTS = {"l1": (1, 0.05, 1), "s1": (-1, 0.05, 1), "l4": (1, 0.10, 4), "s4": (-1, 0.10, 4),
        "l24": (1, 0.15, 24), "s24": (-1, 0.15, 24), "l72": (1, 0.25, 72), "s72": (-1, 0.25, 72)}


def prep():
    sys.path.insert(0, os.path.join(HERE, "..", "s141"))
    from flow_test import alt_index  # noqa: E402
    parts, alts = {"CYBER": [], "BTC": []}, []
    for f, cut in (("s117/k_oos.pkl", (None, int(datetime.datetime(2024, 10, 1, tzinfo=UTC).timestamp()))),
                   ("s224/k_d.pkl", (int(datetime.datetime(2024, 10, 1, tzinfo=UTC).timestamp()), None))):
        K = pickle.load(open(f, "rb"))
        Ti, Ii = alt_index(K)
        m = np.ones(len(Ti), bool)
        if cut[0]:
            m &= Ti >= cut[0]
        if cut[1]:
            m &= Ti < cut[1]
        alts.append((Ti[m], Ii[m]))
        for s in parts:
            a = K[s]; mm = np.ones(len(a["t"]), bool)
            if cut[0]:
                mm &= a["t"] >= cut[0]
            if cut[1]:
                mm &= a["t"] < cut[1]
            parts[s].append({k: np.asarray(v)[mm] for k, v in a.items()})
        del K
    K = {s: {k: np.concatenate([p[k] for p in ps]) for k in ps[0]} for s, ps in parts.items()}
    pickle.dump(K, open("s227/k.pkl", "wb"))
    (t1, i1), (t2, i2) = alts
    lvl = np.r_[i1, i2 * (i1[-1] / i2[0])]                    # склейка: первый шаг второго архива считаем нулевым
    np.save("s227/alt.npy", np.c_[np.r_[t1, t2], lvl])
    F = {}
    for f in ("s117/fund_oos.pkl", "s224/fund_d.pkl"):
        x = pickle.load(open(f, "rb"))
        for s in ("CYBER", "BTC"):
            F.setdefault(s, []).extend([list(r) for r in x.get(s, [])])
    F = {s: np.array(sorted({int(r[0]): r for r in v}.values())) for s, v in F.items()}
    pickle.dump(F, open("s227/f.pkl", "wb"))
    print("свечи:", {s: (len(K[s]["t"]), int(K[s]["t"][0]), int(K[s]["t"][-1])) for s in K}, "фандинг:", {s: len(v) for s, v in F.items()},
          "индекс альтов:", len(lvl), flush=True)


def roll(x, w):
    cs = np.r_[0.0, np.cumsum(np.nan_to_num(x, nan=0.0))]; out = np.full(len(x), np.nan)
    out[w - 1:] = cs[w:] - cs[:-w]
    return out


def hourly_from(t, v, T):
    """Значение ряда (t — начало часа) за час, закончившийся в T."""
    idx = {int(a): i for i, a in enumerate(t)}
    return np.array([v[idx[T_ - H]] if (T_ - H) in idx else np.nan for T_ in T])


def main():
    sys.path.insert(0, os.path.join(HERE, "..", "s187"))
    import fastbt as FB  # noqa: E402
    K = FB.K; a = K[S]
    t15 = a["t"].astype(np.int64); c = a["c"].astype(float); hi = a["h"].astype(float); lo = a["l"].astype(float)
    qv = a["qv"].astype(float); tb = a["tb"].astype(float)
    close_at = {int(x) + B: i for i, x in enumerate(t15)}
    lo_live, _ = FB.live(S)
    T = np.arange(T_START, D1 + H, H)
    T = T[[(x in close_at) and (x - B >= lo_live + D) for x in T]]
    I = np.array([close_at[x] for x in T])
    F = pd.DataFrame({"T": T})
    ok = I >= 672
    def back(n):
        out = np.full(len(I), np.nan); m = I >= n; out[m] = c[I[m]] / c[I[m] - n] - 1
        return out
    F["r1"], F["r4"], F["r24"], F["r72"], F["r168"] = back(4), back(16), back(96), back(288), back(672)
    lr = np.r_[np.nan, np.diff(np.log(c))]
    sd = pd.Series(lr).rolling(96).std(ddof=0).to_numpy()
    F["vol24"] = sd[I]
    hmax = pd.Series(hi).rolling(96).max().to_numpy(); lmin = pd.Series(lo).rolling(96).min().to_numpy()
    F["rng24"] = hmax[I] / lmin[I] - 1
    h7 = pd.Series(hi).rolling(672).max().to_numpy(); l7 = pd.Series(lo).rolling(672).min().to_numpy()
    F["hi7"] = c[I] / h7[I] - 1; F["lo7"] = c[I] / l7[I] - 1
    q4, q96, q672 = roll(qv, 4), roll(qv, 96), roll(qv, 672)
    F["qv1x"] = q4[I] / (q672[I] / 168); F["qvx"] = q96[I] / (q672[I] / 7)
    t4, t16 = roll(tb, 4), roll(tb, 16); q16 = roll(qv, 16)
    F["tb1"] = t4[I] / q4[I]; F["tb4"] = t16[I] / q16[I]
    qv24 = q96[I]; perp1 = q4[I]
    F.loc[~ok, ["r168", "hi7", "lo7", "qv1x", "qvx"]] = np.nan
    # спот Binance (часовые свечи: начало часа, …, оборот $ в колонке 7)
    sp = np.load("s227/spot.npy")
    spq = hourly_from(sp[:, 0], sp[:, 7], T); spc = hourly_from(sp[:, 0], sp[:, 4], T)
    spq24 = pd.Series(spq).rolling(24, min_periods=24).sum().to_numpy()       # сетка T часовая и сплошная по возможности
    gap = np.r_[False, np.diff(T) != H]
    F["sp1"] = spq / (spq + perp1)
    F["sp24"] = spq24 / (spq24 + qv24)
    F["basis"] = c[I] / spc - 1
    # Корея: Bithumb и Upbit (оборот в вонах → $ по KRW-USDT той же биржи), премия
    up = pickle.load(open("s15/kr_candles_upbit.pkl", "rb")); bt = pickle.load(open("s15/kr_candles_bithumb.pkl", "rb"))
    def kr_series(main, sym, extra):
        d = {}
        x = main.get(sym)
        if x is not None:
            for tt, cc, vv in zip(x["t"], x["c"], x["v"]):
                d[int(tt)] = (float(cc), float(vv))
        for f in extra:
            if os.path.exists(f):
                for r in np.load(f):
                    d.setdefault(int(r[0]), (float(r[1]), float(r[2])))
        return d
    kd = {"bithumb": (kr_series(bt, "CYBER", ["s227/kr_bithumb_CYBER_2023.npy", "s227/kr_bithumb_CYBER_2026.npy"]),
                      kr_series(bt, "USDT", ["s227/kr_bithumb_USDT_2023.npy", "s227/kr_bithumb_USDT_2026.npy"])),
          "upbit": (kr_series(up, "CYBER", ["s227/kr_upbit_CYBER_2026.npy"]), kr_series(up, "USDT", ["s227/kr_upbit_USDT_2026.npy"]))}
    kr1 = np.zeros(len(T)); prem_kr = np.full(len(T), np.nan); krv = {}
    for ex, (cy, us) in kd.items():
        ut = np.array(sorted(us)); uv = np.array([us[x][0] for x in ut])
        def usd(tt):
            j = np.searchsorted(ut, tt, "right") - 1
            return uv[j] if j >= 0 else np.nan
        v = np.array([cy[x - H][1] / usd(x - H) if (x - H) in cy else 0.0 for x in T])
        p = np.array([cy[x - H][0] / usd(x - H) / c[i] - 1 if (x - H) in cy else np.nan for x, i in zip(T, I)])
        krv[ex] = v
        prem_kr = np.where(np.isnan(prem_kr), p, np.where(np.isnan(p), prem_kr, (prem_kr + p) / 2))
    kv = krv["bithumb"] + krv["upbit"]
    kv24 = pd.Series(kv).rolling(24, min_periods=24).sum().to_numpy()
    F["kr24"] = kv24 / (kv24 + qv24); F["kr_prem"] = prem_kr
    pu = json.load(gzip.open("s209/upbit_premium/DAYS_1/KRW-CYBER.json.gz"))
    pt = np.array(sorted(pd.Timestamp(x["recordTime"], tz="UTC").timestamp() for x in pu))
    pv = {pd.Timestamp(x["recordTime"], tz="UTC").timestamp(): x.get("disparityRate") for x in pu}
    F["up_prem"] = [pv[pt[j]] if (j := np.searchsorted(pt, x - D, "right") - 1) >= 0 else np.nan for x in T]
    # пара к лире: 15-мин CYBERTRY и USDTTRY (s15/try), ноябрь 2026 — часовые свечи, курс — последний известный
    def try_series(pair):
        a_ = [np.load(f) for f in sorted(glob.glob(f"s15/try/{pair}-*.npy"))]
        a_ = np.concatenate([x for x in a_ if len(x)]); a_ = a_[np.argsort(a_[:, 0])]
        return a_
    cy, fx = try_series("CYBERTRY"), try_series("USDTTRY")
    fxv = np.interp(cy[:, 0], fx[:, 0], fx[:, 1])
    usd15 = cy[:, 2] / fxv
    tail = np.load("s227/try_tail.npy")
    tt_all = np.r_[cy[:, 0], tail[:, 0] if len(tail) else []]
    vv_all = np.r_[usd15, tail[:, 7] / fx[-1, 1] if len(tail) else []]
    o = np.argsort(tt_all); tt_all, vv_all = tt_all[o], vv_all[o]
    csum = np.r_[0.0, np.cumsum(vv_all)]
    a0 = np.searchsorted(tt_all, T - D, "left"); a1 = np.searchsorted(tt_all, T, "left")      # начала свечей в [T − 24 ч, T)
    tr24 = csum[a1] - csum[a0]
    F["try24"] = tr24 / (tr24 + qv24)
    # фандинг
    fr = FB.funding(S); ft = fr[:, 0].astype(np.int64); fv = fr[:, 1]
    k = np.searchsorted(ft, T, "right") - 1
    gp = np.where(k >= 1, (ft[k] - ft[np.maximum(k - 1, 0)]) / H, np.nan)
    F["f8"] = np.where(k >= 1, fv[k] * 8 / np.where(gp > 0, gp, np.nan), np.nan); F["fint"] = gp
    cs = np.r_[0.0, np.cumsum(fv)]
    for w, nm in ((D, "f24"), (3 * D, "f72")):
        a0 = np.searchsorted(ft, T - w, "right"); a1 = np.searchsorted(ft, T, "right"); F[nm] = cs[a1] - cs[a0]
    # премия к индексу (часовые свечи premiumIndexKlines)
    pr = np.load("s227/prem.npy")
    pc = hourly_from(pr[:, 0], pr[:, 4], T)
    F["prem1"] = pc; F["prem24"] = pd.Series(pc).rolling(24, min_periods=20).mean().to_numpy()
    # метрики позиций: строки в начале часа, T − 1 ч
    M = {}
    for f in sorted(glob.glob("s227/metrics/*.npy")):
        for r in np.load(f):
            M[int(r[0])] = r
    def mv(x, col):
        r = M.get(int(x)); return r[col] if r is not None else np.nan
    T1 = T - H
    oi = np.array([mv(x, 1) for x in T1])
    F["doi1"] = oi / np.array([mv(x - H, 1) for x in T1]) - 1
    F["doi4"] = oi / np.array([mv(x - 4 * H, 1) for x in T1]) - 1
    F["doi24"] = oi / np.array([mv(x - D, 1) for x in T1]) - 1
    oiv = np.array([mv(x, 2) for x in T1])
    F["lsr_tacc"] = [mv(x, 3) for x in T1]; F["lsr_tpos"] = [mv(x, 4) for x in T1]; F["lsr_acc"] = [mv(x, 5) for x in T1]
    F["dlsr24"] = F["lsr_acc"].to_numpy() - np.array([mv(x - D, 5) for x in T1])
    F["tkr"] = [mv(x, 6) for x in T1]
    F["oiq"] = oiv / qv24
    # CMC: капитализация и монеты в обращении на сутки до T
    cm = {}
    for r in json.load(open("s227/cmc_old.json")):
        if r[3] and r[4]:
            cm[r[0]] = (float(r[3]), float(r[4]))
    for r in json.load(open("s28/hist/24781.json")):
        if r[3] and r[4]:
            cm[r[0]] = (float(r[3]), float(r[4]))
    for r in json.load(open("s171/cmc/24781.json")):
        if r[3] and r[1]:
            cm.setdefault(r[0], (float(r[3]), float(r[1])))
    days = np.array(sorted(cm));
    def cmc_at(x, back_d=1):
        d = pd.Timestamp(x - back_d * D, unit="s").strftime("%Y-%m-%d"); j = np.searchsorted(days, d, "right") - 1
        return cm[days[j]] if j >= 0 else (np.nan, np.nan)
    mc = np.array([cmc_at(x) for x in T]); mc30 = np.array([cmc_at(x, 31) for x in T])
    F["oimc"] = oiv / mc[:, 0]; F["circ30"] = mc[:, 1] / mc30[:, 1] - 1
    # канал MarginData (с 22.02.2025): монета в канале (пост не старше 30 мин), займ, отдача, место, рост займа за 4 ч
    G = pickle.load(open("s224/work/s7/margin.pkl", "rb"))["G"].get(S)
    tp, bo, rp, rk = G[:, 0], G[:, 1], G[:, 2], G[:, 4]
    def chan(x):
        j = np.searchsorted(tp, x, "right") - 1
        if x < CH0:
            return np.nan, np.nan, np.nan, np.nan
        if j >= 0 and x - tp[j] <= 1800:
            return 1.0, bo[j], rp[j], rk[j]
        return 0.0, 0.0, 0.0, np.nan
    ch = np.array([chan(x) for x in T]); ch4 = np.array([chan(x - 4 * H) for x in T])
    F["inch"], F["bor"], F["rep"], F["place"] = ch[:, 0], ch[:, 1], ch[:, 2], ch[:, 3]
    F["rb"] = np.where(ch[:, 1] > 0, ch[:, 2] / np.where(ch[:, 1] > 0, ch[:, 1], 1), np.nan)
    F["b4"] = np.where((ch[:, 0] == 1) & (ch4[:, 0] == 1) & (ch4[:, 1] > 0), ch[:, 1] / np.where(ch4[:, 1] > 0, ch4[:, 1], 1), np.nan)
    hs = set((tp // H).astype(np.int64).tolist())
    F["pres7"] = [sum(1 for kk in range(168) if (x // H - 1 - kk) in hs) if x >= CH0 + 7 * D else np.nan for x in T]
    F["bqv"] = F["bor"].to_numpy() / qv24
    # ставка займа маржи: почасовой ряд, час T − 1 ч; загрузка к 10-му перцентилю за 30 сут, изменение за сутки
    rr = {}
    for f in ("s190/rates/CYBER.csv", "s11/rates/CYBER.csv", "s224/work/s11/rates/CYBER.csv"):
        if os.path.exists(f):
            for r in np.loadtxt(f, delimiter=",", ndmin=2):
                rr[int(r[0])] = float(r[1])
    rt = np.array(sorted(rr)); rv = np.array([rr[x] for x in rt])
    hrs = np.arange(rt[0] // H * H, rt[-1] // H * H + H, H)
    vh = rv[np.maximum(np.searchsorted(rt, hrs, "right") - 1, 0)]
    q10 = pd.Series(vh).rolling(720, min_periods=120).quantile(0.1).to_numpy()
    kk = np.searchsorted(hrs, T - H, "right") - 1; okk = kk >= 24
    kk2 = np.where(okk, kk, 0)
    F["rate"] = np.where(okk, vh[kk2], np.nan); F["ux"] = np.where(okk, vh[kk2] / q10[kk2], np.nan)
    F["dr24"] = np.where(okk, vh[kk2] / vh[np.maximum(kk2 - 24, 0)], np.nan)
    # разлоки DefiLlama (cliff, кроме казны): дней до ближайшего, его доля к обращению, разлок за прошлые 7 сут
    ev = json.load(open("s139/ll/e_cyberconnect.json"))["metadata"]["events"]
    cl = {}
    for x in ev:
        if x.get("unlockType") == "cliff" and x.get("category") not in ("noncirculating", "burned"):
            cl[int(x["timestamp"])] = cl.get(int(x["timestamp"]), 0.0) + float(sum(x.get("noOfTokens") or [0]))
    ut = np.array(sorted(cl)); uv = np.array([cl[x] for x in ut])
    j = np.searchsorted(ut, T, "right")
    nxt = np.where(j < len(ut), ut[np.minimum(j, len(ut) - 1)], np.nan)
    F["unl_d"] = (nxt - T) / D
    F["unl_f"] = np.where(j < len(ut), uv[np.minimum(j, len(ut) - 1)], np.nan) / mc[:, 1]
    cu = np.r_[0.0, np.cumsum(uv)]
    F["unl7"] = (cu[np.searchsorted(ut, T, "right")] - cu[np.searchsorted(ut, T - 7 * D, "right")]) / mc[:, 1]
    # ончейн (Ethereum): заводы держателей на биржи (s160), выводы с Binance на кошельки (s207) — доля обращения
    e160 = pd.read_pickle("s160_events.pkl"); e160 = e160[(e160.perp == S) & (e160.from_exch != True)]
    w207 = pd.read_pickle("s207_withdrawals.pkl"); w207 = w207[(w207.perp == S) & (w207.kind == "wallet")]
    def wsum(tt, vv, w):
        o_ = np.argsort(tt); tt, vv = np.asarray(tt)[o_], np.asarray(vv)[o_]; cs_ = np.r_[0.0, np.cumsum(vv)]
        return cs_[np.searchsorted(tt, T, "right")] - cs_[np.searchsorted(tt, T - w, "right")]
    F["dep24"] = wsum(e160.t.to_numpy(float), e160.frac.to_numpy(float), D)
    F["dep72"] = wsum(e160.t.to_numpy(float), e160.frac.to_numpy(float), 3 * D)
    bn = e160[e160.exch == "Binance"]
    F["depb72"] = wsum(bn.t.to_numpy(float), bn.frac.to_numpy(float), 3 * D)
    F["wd24"] = wsum(w207.t.to_numpy(float), w207.frac.to_numpy(float), D)
    # рынок и время
    b = K["BTC"]; bt_ = b["t"].astype(np.int64) + B; bc = b["c"].astype(float)
    ib = np.searchsorted(bt_, T, "right") - 1
    F["btc4"] = bc[ib] / bc[np.searchsorted(bt_, T - 4 * H, "right") - 1] - 1
    F["btc24"] = bc[ib] / bc[np.searchsorted(bt_, T - D, "right") - 1] - 1
    al = np.load("s227/alt.npy"); at, alv = al[:, 0] + B, al[:, 1]
    ia = np.searchsorted(at, T, "right") - 1
    F["alt4"] = alv[ia] / alv[np.searchsorted(at, T - 4 * H, "right") - 1] - 1
    F["alt24"] = alv[ia] / alv[np.searchsorted(at, T - D, "right") - 1] - 1
    hh = (T // H) % 24; wd = pd.to_datetime(T, unit="s").dayofweek.to_numpy()
    F["h00"] = (hh < 6).astype(float); F["h06"] = ((hh >= 6) & (hh < 12)).astype(float)
    F["h12"] = ((hh >= 12) & (hh < 18)).astype(float); F["h18"] = (hh >= 18).astype(float)
    F["wkend"] = (wd >= 5).astype(float)
    # исходы: вход на закрытии T (свеча I), комиссия и фандинг; хедж — ход индекса альтов на фактический срок
    for kname, (side, sl, hold) in OUTS.items():
        okt, net, _, _, tend = FB.trades(S, I, sl, hold, side)
        y = np.where(okt, net, np.nan)
        a0 = np.searchsorted(at, T, "right") - 1; a1 = np.searchsorted(at, np.where(okt, tend, T), "right") - 1
        mvv = np.where(okt & (a0 >= 0), alv[np.maximum(a1, 0)] / alv[np.maximum(a0, 0)] - 1, np.nan)
        F[f"y_{kname}"] = y
        F[f"u_h_{kname}"] = y - side * mvv
        F[f"u_e_{kname}"] = np.where(okt, tend, np.nan)
    F["s"] = S
    F = F.replace([np.inf, -np.inf], np.nan)
    A = F[F["T"] <= C_END].reset_index(drop=True)
    A.to_pickle("s227_feat.pkl")
    A[A["T"] >= CH0].reset_index(drop=True).to_pickle("s227c_feat.pkl")
    F[(F["T"] >= D0) & (F["T"] <= D1)].reset_index(drop=True).to_pickle("s227D_feat.pkl")
    fe = [x for x in F.columns if x not in ("T", "s") and not x.startswith(("y_", "u_"))]
    print("наблюдений: всего", len(F), "до C", len(A), "эпоха канала", int((A["T"] >= CH0).sum()), "D", int(((F["T"] >= D0) & (F["T"] <= D1)).sum()))
    print("признаков", len(fe), "заполненность:", {x: round(float(A[x].notna().mean()), 2) for x in fe})


if __name__ == "__main__":
    if sys.argv[1:] == ["prep"]:
        prep()
    else:
        main()
