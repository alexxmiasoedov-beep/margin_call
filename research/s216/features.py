"""s216 — признаки на сетке 4 ч (монета в канале MarginData) и восемь исходов. Метод — ВЫВОДЫ.md (записан до расчёта,
коммит c94a850). Только данные до T. Итог — s216_feat.pkl в папке данных.
Запуск из /home/user/mc_data (сначала fetch_metrics.py): python3 <repo>/research/s216/features.py
Окружение (s224): GRID — шаг сетки в часах (по умолчанию 4), T0 — начало сетки ГГГГ-ММ-ДД (по умолчанию вся панель),
OUT — файл итога (по умолчанию s216_feat.pkl)."""
import datetime
import json
import os
import pickle
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s187", "s171", "s22"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
import fastbt as FB  # noqa: E402

K, funding, live = FB.K, FB.funding, FB.live
H, DAY, G4 = 3600, 86400, 4 * 3600
UTC = datetime.timezone.utc
OUTS = {"s4": (-1, 0.10, 4), "s24": (-1, 0.25, 24), "s48": (-1, 0.25, 48), "s168": (-1, 0.50, 168),
        "l4": (1, 0.10, 4), "l24": (1, 0.25, 24), "l48": (1, 0.25, 48), "l168": (1, 0.50, 168)}


def coin_of(fs):
    m = re.match(r"^(1000000|1000|1M)(.+)$", fs)
    return m.group(2) if m and not m.group(2)[0].isdigit() else fs


def mult_of(fs):
    m = re.match(r"^(1000000|100000|10000|1000|1M)(.+)$", fs)
    if m and not m.group(2)[0].isdigit():
        return 1e6 if m.group(1) in ("1M", "1000000") else float(m.group(1))
    return 1.0


def loan_features(D, G):
    """Признаки займа по часовой панели s21 (строка = монета в канале в час T) и постам канала."""
    key = {(s, int(T)): (b, r) for s, T, b, r in zip(D.s, D["T"], D.bor, D.rep)}
    out = {k: np.full(len(G), np.nan) for k in ("b24", "r24x", "net7", "place", "pres7", "run")}
    M = pickle.load(open("s7/margin.pkl", "rb"))["G"]
    hours = {}
    for j, (s, T) in enumerate(zip(G.s, G["T"])):
        T = int(T)
        b0 = key.get((s, T - DAY))
        out["b24"][j] = G.bor.iat[j] / b0[0] if b0 and b0[0] > 0 else np.nan
        out["r24x"][j] = G.rep.iat[j] / b0[1] if b0 and b0[1] > 0 else np.nan
        out["net7"][j] = sum((lambda x: x[0] - x[1] if x else 0.0)(key.get((s, T - k * DAY))) for k in range(7))
        c = s if s in M else coin_of(s)
        g = M.get(c)
        if g is None:
            continue
        if c not in hours:
            hours[c] = (g[:, 0], set((g[:, 0] // H).astype(np.int64).tolist()))
        tt, hs = hours[c]
        i = int(np.searchsorted(tt, T, "right")) - 1
        if i >= 0 and T - tt[i] <= 1800:
            out["place"][j] = g[i, 4]
        h0 = T // H - 1                                       # час, закончившийся в T
        out["pres7"][j] = sum((h0 - k) in hs for k in range(168))
        run = 0
        while (h0 - run) in hs and run < 24 * 60:
            run += 1
        out["run"][j] = run
    return out


def mcap_table(G):
    """Капитализация CMC (s171/k3: монета CMC с тем же тикером и медианой цены к фьючерсу 0,8–1,25) на последний день не
    позже суток до T."""
    import k3  # noqa: E402  (s171: hist(), кэш s171/cmc)
    cmc = json.load(open("s167/cmc_map_all.json"))
    by = {}
    for c in cmc:
        by.setdefault(str(c.get("symbol") or "").upper(), []).append(c)
    pick = {}
    for fs in sorted(G.s.unique()):
        if fs not in K:
            continue
        coin, mult = coin_of(fs), mult_of(fs)
        a = K[fs]; m = (a["qv"] > 0) & (a["t"] % DAY == DAY - 900)
        px = pd.Series(a["c"][m].astype(float) / mult,
                       index=pd.to_datetime(a["t"][m].astype(np.int64) // DAY * DAY, unit="s").strftime("%Y-%m-%d"))
        best = None
        for c in by.get(coin, []):
            h = k3.hist(c["id"])
            q = pd.Series({d: cl for d, _, cl, _ in h if cl}, dtype=float)
            j = q.index.intersection(px.index)
            if len(j) < 20:
                continue
            r = float(np.median(q[j].values / px[j].values))
            if 0.8 <= r <= 1.25 and (best is None or abs(np.log(r)) < abs(np.log(best[1]))):
                best = (c["id"], r)
        if best:
            pick[fs] = best[0]
    print("монет с капитализацией CMC:", len(pick), "из", G.s.nunique(), flush=True)
    ser = {}
    for fs, cid in pick.items():
        h = [x for x in json.load(open(f"s171/cmc/{cid}.json")) if x[1] and x[2]]
        ser[fs] = (np.array([x[0] for x in h]), np.array([x[1] * x[2] for x in h], float))
    mc = np.full(len(G), np.nan)
    for j, (s, T) in enumerate(zip(G.s, G["T"])):
        if s in ser:
            d, v = ser[s]
            i = int(np.searchsorted(d, pd.Timestamp(int(T) - DAY, unit="s").strftime("%Y-%m-%d"), "right")) - 1
            mc[j] = v[i] if i >= 0 else np.nan
    return mc


def rate_features(G):
    """Ставка займа (s11/rates: моменты смены ставки) → почасовой ряд; загрузка к 10-му перцентилю за 30 сут, ставка 24 ч
    назад, «пул выбран» (≥ 0,9 максимума за 30 сут и загрузка ≥ 3)."""
    out = {k: np.full(len(G), np.nan) for k in ("rate", "ux", "dr24", "lim")}
    for c, idx in G.groupby(G.s.map(coin_of)).groups.items():
        p = f"s11/rates/{c}.csv"
        if not os.path.exists(p):
            continue
        a = np.loadtxt(p, delimiter=",", ndmin=2)
        if not len(a):
            continue
        hrs = np.arange(int(a[0, 0]) // H * H, int(a[-1, 0]) // H * H + H, H)
        v = a[np.maximum(np.searchsorted(a[:, 0], hrs, "right") - 1, 0), 1]
        s = pd.Series(v, index=hrs)
        q10 = s.rolling(720, min_periods=120).quantile(0.1).to_numpy()
        mx = s.rolling(720, min_periods=120).max().to_numpy()
        ii = G.loc[idx]
        k = np.searchsorted(hrs, ii["T"].to_numpy() - H, "right") - 1     # последний полный час до T
        ok = k >= 24
        kk = np.where(ok, k, 0)
        pos = G.index.get_indexer(idx)
        out["rate"][pos] = np.where(ok, v[kk], np.nan)
        out["ux"][pos] = np.where(ok, v[kk] / q10[kk], np.nan)
        out["dr24"][pos] = np.where(ok, v[kk] / v[np.maximum(kk - 24, 0)], np.nan)
        out["lim"][pos] = np.where(ok & np.isfinite(mx[kk]), ((v[kk] >= 0.9 * mx[kk]) & (v[kk] / q10[kk] >= 3)).astype(float),
                                   np.nan)
    return out


def market_features(G):
    names = ("r4", "r24", "r72", "vol24", "qv24", "qvx", "tb4", "f8", "f24")
    out = {k: np.full(len(G), np.nan) for k in names}
    for s, idx in G.groupby("s").groups.items():
        if s not in K:
            continue
        a = K[s]; t = a["t"].astype(np.int64) + 900
        c, qv, tb = (a[x].astype(float) for x in ("c", "qv", "tb"))
        pos = G.index.get_indexer(idx)
        TT = G.loc[idx, "T"].to_numpy(np.int64)
        I = np.searchsorted(t, TT, "right") - 1
        fr = funding(s)
        ft = fr[:, 0].astype(np.int64) if len(fr) else np.zeros(0, np.int64)
        for p_, T, i in zip(pos, TT, I):
            if i < 672 or t[i] != T:
                continue
            out["r4"][p_] = c[i] / c[i - 16] - 1; out["r24"][p_] = c[i] / c[i - 96] - 1; out["r72"][p_] = c[i] / c[i - 288] - 1
            out["vol24"][p_] = float(np.std(np.diff(np.log(c[i - 96:i + 1]))))
            q24 = qv[i - 95:i + 1].sum(); q7 = qv[i - 671:i + 1].sum() / 7
            out["qv24"][p_] = q24; out["qvx"][p_] = q24 / q7 if q7 > 0 else np.nan
            q4 = qv[i - 15:i + 1].sum(); out["tb4"][p_] = tb[i - 15:i + 1].sum() / q4 if q4 > 0 else np.nan
            if len(ft):
                k = int(np.searchsorted(ft, T, "right")) - 1
                if k >= 1:
                    gap = (ft[k] - ft[k - 1]) / H
                    out["f8"][p_] = fr[k, 1] * 8 / gap if gap > 0 else np.nan
                    m = (ft > T - DAY) & (ft <= T)
                    out["f24"][p_] = float(fr[m, 1].sum())
    return out


def metric_features(G):
    """Метрики позиций (почасовые строки s22/metrics_full: время, OI, OI $, лонг/шорт топ-счетов, топ-позиций, всех счетов,
    отношение агрессивных объёмов). Берём строку не позже T − 1 ч (публикация 5-мин метрик с задержкой)."""
    names = ("doi4", "doi24", "oiv", "lsr_top", "lsr_acc", "dlsr24", "tkr")
    out = {k: np.full(len(G), np.nan) for k in names}
    cache = {}

    def day(s, x):
        d = datetime.datetime.fromtimestamp(x, UTC).strftime("%Y-%m-%d")
        if (s, d) not in cache:
            p = f"s22/metrics_full/{s}/{d}.npy"
            cache[(s, d)] = np.load(p) if os.path.exists(p) else np.zeros((0, 7))
        return cache[(s, d)]
    for j, (s, T) in enumerate(zip(G.s, G["T"])):
        T = int(T) - H
        arr = [a for a in (day(s, T - DAY - 4 * H), day(s, T - DAY), day(s, T)) if len(a)]
        if not arr:
            continue
        a = np.vstack(arr); a = a[np.argsort(a[:, 0])]

        def v(x, col):
            i = int(np.searchsorted(a[:, 0], x, "right")) - 1
            return a[i, col] if i >= 0 and x - a[i, 0] < H else np.nan
        o, o4, o24 = v(T, 1), v(T - 4 * H, 1), v(T - DAY, 1)
        out["doi4"][j] = o / o4 - 1 if o4 and np.isfinite(o4) and o4 > 0 else np.nan
        out["doi24"][j] = o / o24 - 1 if o24 and np.isfinite(o24) and o24 > 0 else np.nan
        out["oiv"][j] = v(T, 2)
        out["lsr_top"][j] = v(T, 4); out["lsr_acc"][j] = v(T, 5); out["dlsr24"][j] = v(T, 5) - v(T - DAY, 5)
        out["tkr"][j] = v(T, 6)
        if j % 20000 == 0:
            cache.clear()
    return out


def outcomes(G):
    out = {k: np.full(len(G), np.nan) for k in OUTS}
    for s, idx in G.groupby("s").groups.items():
        if s not in K:
            continue
        t = K[s]["t"].astype(np.int64)
        pos = G.index.get_indexer(idx)
        st = G.loc[idx, "T"].to_numpy(np.int64) - 900
        I = np.searchsorted(t, st)
        ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == st)
        lo, _ = live(s)
        ok &= t[np.minimum(I, len(t) - 1)] >= lo + DAY
        if not ok.any():
            continue
        for k, (side, sl, hold) in OUTS.items():
            okt, net, *_ = FB.trades(s, I[ok], sl, hold, side)
            out[k][pos[ok]] = np.where(okt, net, np.nan)
    return out


def main():
    D = pd.read_pickle("s21/panel.pkl")
    # s224: сетка и начало — из окружения (GRID — часов, по умолчанию 4; T0 — дата ГГГГ-ММ-ДД, по умолчанию вся панель)
    grid = int(float(os.environ.get("GRID", "4")) * H)
    G = D[D["T"] % grid == 0]
    if os.environ.get("T0"):
        G = G[G["T"] >= pd.Timestamp(os.environ["T0"], tz="UTC").timestamp()]
    G = G.sort_values(["T", "s"]).reset_index(drop=True)
    F = G[["s", "T", "bor", "rep"]].copy()
    F["net"] = G.bor - G.rep
    F["rb"] = np.where(G.bor > 0, G.rep / G.bor, np.nan)
    F["b4"] = np.where(G.in4 & (G.bor4 > 0), G.bor / G.bor4.where(G.bor4 > 0), np.nan)
    F["r4x"] = np.where(G.in4 & (G.rep4 > 0), G.rep / G.rep4.where(G.rep4 > 0), np.nan)
    print("наблюдений", len(F), flush=True)
    for k, v in loan_features(D, G).items():
        F[k] = v
    F["hold"] = np.clip(F.net7 / np.maximum(G.rep, 1e3), -1000, 1000)
    print("займ готов", flush=True)
    for k, v in market_features(G).items():
        F[k] = v
    F["bqv"] = F.bor / F.qv24.where(F.qv24 > 0)
    print("рынок готов", flush=True)
    for k, v in rate_features(G).items():
        F[k] = v
    print("ставки готовы", flush=True)
    F["mcap"] = mcap_table(G)
    F["bmc"] = F.bor / F.mcap
    for k, v in metric_features(G).items():
        F[k] = v
    F["oiq"] = F.oiv / F.qv24.where(F.qv24 > 0)
    print("метрики готовы", flush=True)
    bt = K["BTC"]["t"].astype(np.int64) + 900; bc = K["BTC"]["c"].astype(float)
    F["btc24"] = [bc[i] / bc[j] - 1 if i >= 0 and j >= 0 else np.nan
                  for i, j in zip(np.searchsorted(bt, F["T"], "right") - 1, np.searchsorted(bt, F["T"] - DAY, "right") - 1)]
    acc = D[D.in4 & (D.bor >= 1.5 * D.bor4) & (D.bor >= 50e3)][["s", "T"]]
    at = np.sort(acc["T"].to_numpy(np.int64)); sa = acc.sort_values("T").s.to_numpy()
    F["wave"] = [len(set(sa[np.searchsorted(at, T - DAY, "right"):np.searchsorted(at, T, "right")])) for T in F["T"]]
    for k, v in outcomes(G).items():
        F[k] = v
    F = F.drop(columns=["oiv", "mcap"])
    F.to_pickle(os.environ.get("OUT", "s216_feat.pkl"))                # s224: OUT — другой файл итога
    print("готово:", F.shape, "\nзаполнено:", F.notna().mean().round(2).to_dict(), flush=True)


if __name__ == "__main__":
    main()
