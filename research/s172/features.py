"""s172 — признаки на моментах T событий «займ ускорился» (s171_events.pkl; метод — ВЫВОДЫ.md, записан до расчёта).
Только данные до T. Итог — s172_feat.pkl в папке данных. Метрики позиций докачиваются в кэш s22/metrics_full (загрузчик
s22/h12_fetch.full_day). Запуск из /home/user/mc_data: python3 <repo>/research/s172/features.py"""
import datetime
import json
import os
import pickle
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s22"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, funding, live  # noqa: E402
from h12_fetch import full_day  # noqa: E402

H, DAY = 3600, 86400
UTC = datetime.timezone.utc


def coin_of(fs):
    m = re.match(r"^(1000000|1000)(.+)$", fs)
    return m.group(2) if m else fs


def at(t, x, T):
    """Значение ряда x (по времени t) на последнюю отметку не позже T."""
    i = int(np.searchsorted(t, T, "right")) - 1
    return x[i] if i >= 0 else np.nan


def main():
    E = pd.read_pickle("s171_events.pkl").sort_values("T").reset_index(drop=True)
    F = E[["s", "T", "n7", "n7h", "n2", "n2h"]].copy()
    # займ
    F["bor"] = E.bor; F["rep"] = E.rep
    F["b_acc"] = E.bor / E.bor4.replace(0, np.nan); F["r_acc"] = (E.rep + 1) / (E.rep4 + 1)
    F["br"] = E.bor / (E.rep + 1e3)
    F["bmc"] = E.get("bmc"); F["mcap"] = E.get("mcap")
    G = pickle.load(open("s7/margin.pkl", "rb"))["G"]
    pres = []
    for r in E.itertuples():
        g = G.get(coin_of(r.s)) if coin_of(r.s) in G else G.get(r.s)
        if g is None:
            pres.append(np.nan); continue
        tt = g[:, 0]; m = (tt > r.T - 7 * DAY) & (tt <= r.T)
        pres.append(len(np.unique((tt[m] // H).astype(np.int64))))
    F["pres7"] = pres
    R = pd.read_pickle("s41/rows.pkl")
    CH = {c: (g.t.values, g.chng.values) for c, g in R.groupby("c")}
    F["chng"] = [np.nanmax(CH[c][1][(CH[c][0] > T - 6 * H) & (CH[c][0] <= T)]) if c in CH and np.any((CH[c][0] > T - 6 * H) & (CH[c][0] <= T)) else np.nan
                 for c, T in zip(E.s.map(coin_of), E["T"])]
    # цена и оборот фьючерса
    cols = {k: [] for k in ("r24", "r72", "r168", "vol24", "dhi7", "dlo7", "qv24", "qvx", "tb4", "tb24", "nx", "age", "btc24")}
    bt, bc = K["BTC"]["t"].astype(np.int64) + 900, K["BTC"]["c"].astype(float)
    for r in E.itertuples():
        a = K.get(r.s)
        if a is None:
            for k in cols:
                cols[k].append(np.nan)
            continue
        t = a["t"].astype(np.int64) + 900; c = a["c"].astype(float); qv = a["qv"].astype(float)
        i = int(np.searchsorted(t, r.T, "right")) - 1
        ok = i >= 7 * 96 and t[i] == r.T
        if not ok:
            for k in cols:
                cols[k].append(np.nan)
            continue
        cols["r24"].append(c[i] / c[i - 96] - 1); cols["r72"].append(c[i] / c[i - 288] - 1); cols["r168"].append(c[i] / c[i - 672] - 1)
        lr = np.diff(np.log(c[i - 96:i + 1])); cols["vol24"].append(float(np.std(lr)))
        cols["dhi7"].append(c[i] / a["h"][i - 671:i + 1].astype(float).max() - 1); cols["dlo7"].append(c[i] / a["l"][i - 671:i + 1].astype(float).min() - 1)
        q24 = qv[i - 95:i + 1].sum(); q7 = qv[i - 671:i + 1].sum() / 7
        cols["qv24"].append(q24); cols["qvx"].append(q24 / q7 if q7 > 0 else np.nan)
        tb = a["tb"].astype(float)
        cols["tb4"].append(tb[i - 15:i + 1].sum() / max(qv[i - 15:i + 1].sum(), 1e-9))
        cols["tb24"].append(tb[i - 95:i + 1].sum() / max(q24, 1e-9))
        n = a["n"].astype(float); n24 = n[i - 95:i + 1].sum(); n7 = n[i - 671:i + 1].sum() / 7
        cols["nx"].append(n24 / n7 if n7 > 0 else np.nan)
        lo, _ = live(r.s); cols["age"].append((r.T - lo) / DAY if np.isfinite(lo) else np.nan)
        cols["btc24"].append(at(bt, bc, r.T) / at(bt, bc, r.T - DAY) - 1)
    for k, v in cols.items():
        F[k] = v
    # спот
    S = pickle.load(open("s23/spot1h.pkl", "rb"))
    F["sbuy4"] = E.buy4
    sh = []
    for r, q24 in zip(E.itertuples(), F.qv24):
        k = r.s if r.s in S else coin_of(r.s)
        if k not in S or not np.isfinite(q24):
            sh.append(np.nan); continue
        a = S[k]; m = (a[:, 0] >= r.T - DAY) & (a[:, 0] < r.T)
        sq = a[m, 1].sum(); sh.append(sq / (sq + q24) if sq + q24 > 0 else np.nan)
    F["spot24"] = sh
    # фандинг и премия
    F["f24"] = E.f24
    f7 = []
    for r in E.itertuples():
        fr = funding(r.s)
        m = (fr[:, 0] > r.T - 7 * DAY) & (fr[:, 0] <= r.T) if len(fr) else np.array([], bool)
        f7.append(float(fr[m, 1].sum()) if m.any() else np.nan)
    F["f7"] = f7
    P = pickle.load(open("s12/prem.pkl", "rb"))
    p1, p24 = [], []
    for r in E.itertuples():
        if r.s not in P:
            p1.append(np.nan); p24.append(np.nan); continue
        t, v = P[r.s]; t = np.asarray(t, np.int64); v = np.asarray(v, float)
        j = int(np.searchsorted(t, r.T, "right"))
        p1.append(float(np.nanmean(v[max(0, j - 4):j])) if j > 0 else np.nan)
        p24.append(float(np.nanmean(v[max(0, j - 96):j])) if j > 0 else np.nan)
    F["prem1"] = p1; F["prem24"] = p24
    del P
    # ставка маржи к своему полу за 30 сут (s40)
    rx = []; cache = {}
    for r in E.itertuples():
        c = coin_of(r.s)
        if c not in cache:
            p = f"s11/rates/{c}.csv"
            cache[c] = np.loadtxt(p, delimiter=",", ndmin=2) if os.path.exists(p) else None
        a = cache[c]
        if a is None or not len(a):
            rx.append(np.nan); continue
        m = (a[:, 0] > r.T - 30 * DAY) & (a[:, 0] <= r.T)
        cur = at(a[:, 0], a[:, 1], r.T)
        rx.append(cur / np.quantile(a[m, 1], 0.1) if m.sum() >= 5 and np.isfinite(cur) else np.nan)
    F["ratex"] = rx
    # позиции (метрики, почасовые отметки)
    days = sorted({(s, datetime.datetime.fromtimestamp(x, UTC).strftime("%Y-%m-%d")) for s, T in zip(E.s, E["T"])
                   for x in (T - 1, T - DAY - 1)})
    print("дней метрик к загрузке/из кэша:", len(days), flush=True)
    with ThreadPoolExecutor(8) as ex:
        got = dict(zip(days, ex.map(lambda sd: full_day(*sd), days)))
    mcol = {k: [] for k in ("oi4", "oi24", "lsr_ta", "lsr_tp", "lsr_all", "dlsr24", "tkr4")}
    for r in E.itertuples():
        arr = [got.get((r.s, datetime.datetime.fromtimestamp(x, UTC).strftime("%Y-%m-%d"))) for x in (r.T - DAY - 1, r.T - 1)]
        arr = [a for a in arr if a is not None and len(a)]
        if not arr:
            for k in mcol:
                mcol[k].append(np.nan)
            continue
        a = np.vstack(arr); a = a[np.argsort(a[:, 0])]

        def v(T, j):
            i = int(np.searchsorted(a[:, 0], T, "right")) - 1
            return a[i, j] if i >= 0 and T - a[i, 0] <= H else np.nan
        o, o4, o24 = v(r.T, 1), v(r.T - 4 * H, 1), v(r.T - DAY, 1)
        mcol["oi4"].append(o / o4 - 1 if o4 and np.isfinite(o4) else np.nan)
        mcol["oi24"].append(o / o24 - 1 if o24 and np.isfinite(o24) else np.nan)
        mcol["lsr_ta"].append(v(r.T, 3)); mcol["lsr_tp"].append(v(r.T, 4)); mcol["lsr_all"].append(v(r.T, 5))
        mcol["dlsr24"].append(v(r.T, 5) - v(r.T - DAY, 5))
        m4 = (a[:, 0] > r.T - 4 * H) & (a[:, 0] <= r.T)
        mcol["tkr4"].append(float(np.nanmean(a[m4, 6])) if m4.any() else np.nan)
    for k, v_ in mcol.items():
        F[k] = v_
    # ликвидации за 24 ч
    L = {"Long": {}, "Short": {}}
    for ln in open("s72/liq.jsonl"):
        x = json.loads(ln)
        m = re.search(r"#(\S+) Liquidated (Long|Short): \$([\d.]+)([KMB]?)", x[2])
        if m:
            L[m.group(2)].setdefault(m.group(1), []).append((pd.Timestamp(x[1]).timestamp(),
                                                             float(m.group(3)) * {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}[m.group(4)]))
    for side, nm in (("Long", "liqL24"), ("Short", "liqS24")):
        D = {s: np.array(sorted(v)) for s, v in L[side].items()}
        F[nm] = [float(D[s][(D[s][:, 0] > T - DAY) & (D[s][:, 0] <= T), 1].sum()) if s in D else 0.0 for s, T in zip(E.s, E["T"])]
    # события: дней до разлока, завод на Binance
    U = pd.concat([pd.read_pickle(f"s142_{p}.pkl") for p in ("2022–2024", "2024–2026")])
    UT = {s: np.sort(g["T"].values.astype(np.int64)) for s, g in U.groupby("s")}
    dd = []
    for s, T in zip(E.s, E["T"]):
        u = UT.get(s, np.array([], np.int64)); u = u[(u > T) & (u <= T + 60 * DAY)]
        dd.append((u[0] - T) / DAY if len(u) else np.nan)
    F["d_unl"] = dd
    F["dep24"] = np.where(E.erc, E.dep24.astype(float), np.nan)
    # рынок: волна займов — событий З↑ по всем монетам за 24 ч (до прореживания)
    D = pd.read_pickle("s21/panel.pkl")
    allT = np.sort(D[D.in4 & (D.bor >= 1.5 * D.bor4) & (D.bor >= 50e3)]["T"].values.astype(np.int64))
    F["wave"] = [int(np.searchsorted(allT, T, "right") - np.searchsorted(allT, T - DAY, "right")) for T in E["T"]]
    F["hour"] = (E["T"] // H) % 24; F["wday"] = pd.to_datetime(E["T"], unit="s").dt.weekday
    F.to_pickle("s172_feat.pkl")
    print("признаков:", F.shape[1] - 6, "событий:", len(F), "| заполнено:",
          ", ".join(f"{c} {F[c].notna().mean():.0%}" for c in F.columns[6:]), flush=True)


if __name__ == "__main__":
    main()
