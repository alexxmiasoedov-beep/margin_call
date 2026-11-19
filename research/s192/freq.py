"""s192 — охват четвёртого периода (10.2019–09.2020) и грубые частоты событий находок. Доходы, сделки и плацебо
НЕ считаются: только время событий (функции событий исходных скриптов или их точные копии без сделок).

Части:
  cover — перпов с торгами, ликвидных альтов (оборот перпа ≥ 5 млн $ в сутки за 7 сут, возраст ≥ 30 сут), из них со спотом
          Binance и с рынком к воне — медиана по срезам-понедельникам (признаки s183) по месяцам; для сравнения — три
          прежних периода;
  s185  — корейская часть 👀: вход в пятёрку оборота за 24 ч одной корейской биржи вне 🔝 (функции s185/oos.py:
          volumes, events; отбор — как s185 run без сделок), доля Кореи у монеты за 7 сут ≥ 20% (s184 Г3);
  s190  — Г2 «пробой цели ботов Upbit» у монет с долей Кореи за сутки ≥ 20% (копия событийной части s190/g2.run);
  s180  — круглый доллар (s180/round_test.usd_events): B «отказ» на сетке {1…9} и контрольной, A «пробой»;
  s152  — часовое падение к BTC у 30 самых торгуемых альтов (s152/drop_events: hourly_all, universe, events);
  pumps — пампы +15% за ≤ 2 ч из покоя (s15/kr_panel, рабочая папка s192/work): 🇰🇷-тип (доля Кореи ≥ 20%, как
          s118/kr_oos) и 🛒-тип (доля спота ≥ 25,9%, как s118/spot_oos), без сделок;
  atr   — часовые сигналы трейлинга ATR s187 (SuperTrend, Chandelier, PP SuperTrend, ML Adaptive SuperTrend, UT Bot)
          в неделях ликвидности s183 после прогрева (как s187/check._coin); бары — s187/bars.build → s192/bars_2019–2020.pkl.

Запуск из /home/user/mc_data (после load_2019.py, spot_2019.py, kr_2019.py и period.py s183):
  MC_K=/home/user/mc_data/s192/k_2019.pkl MC_F=/home/user/mc_data/s192/fund_2019.pkl MC_CUT=2020-04-01 \\
      python3 <repo>/research/s192/freq.py [части …]      → stdout (freq.txt), события — s192/freq_events.pkl"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import period as PD  # noqa: E402

D = "/home/user/mc_data"
PER, DAY, WEEK = PD.NEW, 86400, 7 * 86400
T0, T1 = int(pd.Timestamp(PD.T0, tz="UTC").timestamp()), int(pd.Timestamp(PD.T1, tz="UTC").timestamp())
MONTHS = (T1 - T0) / (30.4 * DAY)
EV = {}


def month(t):
    return pd.to_datetime(np.asarray(t, np.int64), unit="s").strftime("%Y-%m")


def by_month(name, t):
    """Число событий по месяцам периода (все 12 месяцев, нули — тоже)."""
    m = pd.Series(1, index=month(t)).groupby(level=0).sum() if len(t) else pd.Series(dtype=int)
    allm = pd.period_range(PD.T0, periods=12, freq="M").strftime("%Y-%m")
    return m.reindex(allm, fill_value=0).rename(name)


def show(table, note=""):
    T = pd.concat(table, axis=1).fillna(0).astype(int)
    tot = T.sum()
    print(T.to_string())
    print("всего:", ", ".join(f"{c} {v}" for c, v in tot.items()))
    print("в месяц (12 мес.):", ", ".join(f"{c} {v / MONTHS:.1f}" for c, v in tot.items()))
    h2 = T.loc[T.index >= "2020-04"].sum()
    print("в месяц 04–09.2020 (вторая половина):", ", ".join(f"{c} {v / 6:.1f}" for c, v in h2.items()), note, flush=True)


def _K():
    sys.path.insert(0, os.path.join(PD.REPO, "research", "s15"))
    sys.path.insert(0, os.path.join(PD.REPO, "research", "s43"))
    from common import K, live  # noqa: E402
    return K, live


# ------------------------------------------------------------------------------------------------ охват
def cover():
    print("\n=== Охват: медиана по срезам-понедельникам месяца", flush=True)
    K, live = _K()
    X = pd.read_pickle(f"{D}/s183/feat2_{PER}.pkl")
    P = pd.read_pickle(f"{D}/s183/daily_{PER}.pkl")[["d", "s", "qv", "krv"]]
    # оборот по суткам прямо из свечей (в панели s183 нет BTC: в s12/perp_kind.pkl он попал в tradfi — так во всех периодах)
    qd = {s: pd.Series(a["qv"].astype(float)).groupby(a["t"] // DAY * DAY).sum() for s, a in K.items()}
    mons = [int(pd.Timestamp("2019-10-07", tz="UTC").timestamp()) + 7 * DAY * k for k in range(52)]
    rows = []
    for d0 in mons:
        live7 = {s for s, q in qd.items() if q[(q.index >= d0 - 7 * DAY) & (q.index < d0)].sum() > 0}
        w = P[(P.d >= d0 - 7 * DAY) & (P.d < d0)]
        kr7 = set(w[w.krv.fillna(0) > 0].s)
        x = X[X.d0 == d0]
        L = x[x.liq5.astype(bool) & ~x.s.isin(["BTC", "ETH"])]
        rows.append(dict(d0=d0, perps=len(live7), alts_kr=len(kr7 - {"BTC", "ETH"}), liq=len(L),
                         liq_spot=int(L.sshare7.notna().sum()), liq_kr=int(L.kshare7.notna().sum()),
                         liq20=int((L.qv7 >= 20e6).sum())))
    R = pd.DataFrame(rows)
    R["m"] = month(R.d0)
    R = R[(R.d0 >= T0) & (R.d0 < T1)]
    T = R.groupby("m")[["perps", "alts_kr", "liq", "liq20", "liq_spot", "liq_kr"]].median().astype(int)
    T.columns = ["перпов с торгами за 7 сут", "из них альтов с рынком к воне", "ликвидных альтов (≥ 5 млн $)",
                 "ликвидных ≥ 20 млн $", "ликв. со спотом Binance", "ликв. с рынком к воне"]
    print(T.to_string())
    h2 = R[R.d0 >= int(pd.Timestamp(PD.CUT, tz="UTC").timestamp())]
    print(f"за период: медиана ликвидных альтов на срез {R.liq.median():.0f}, с рынком к воне {R.liq_kr.median():.0f}; "
          f"во второй половине (04–09.2020) — {h2.liq.median():.0f} и {h2.liq_kr.median():.0f}", flush=True)
    print("\nдля сравнения (тот же расчёт по признакам s183):", flush=True)
    for per in ("2020–2022", "2022–2024", "2024–2026"):
        p = f"{D}/s183/feat2_{per}.pkl"
        if not os.path.exists(p):
            continue
        Y = pd.read_pickle(p)[["d0", "s", "liq5", "kshare7", "sshare7"]]
        L = Y[Y.liq5.astype(bool) & ~Y.s.isin(["BTC", "ETH"])]
        g = L.groupby("d0")
        print(f"  {per}: ликвидных альтов на срез — медиана {g.size().median():.0f}, с рынком к воне "
              f"{g.kshare7.count().median():.0f}, со спотом {g.sshare7.count().median():.0f}", flush=True)
    EV["cover"] = R


# ------------------------------------------------------------------------------------------------ s185
def s185():
    print("\n=== s185: вход в пятёрку оборота одной корейской биржи вне 🔝 (корейская часть 👀)", flush=True)
    M = PD.load_script("research/s185/oos.py", "s192_s185")
    PD.patch_loaded(verbose=False)
    K, live = _K()
    from oi_test import idx_at  # noqa: E402
    G3 = M.G3
    Vu, Vb = M.volumes(PER, "upbit"), M.volumes(PER, "bithumb")
    ev = []
    for ex, V in (("upbit", Vu), ("bithumb", Vb)):
        e, majors = M.events(V, PER, K, live, idx_at)
        print(f"{ex}: рынков с перпом {V.shape[1]}, лидеры первой половины {majors}; входов в пятёрку {len(e)}", flush=True)
        ev += [(T, s, ex) for s, T in e]
    kt_ev, kmaj = M.events(Vu.add(Vb, fill_value=0.0).fillna(0.0), PER, K, live, idx_at)
    print(f"🔝 (Upbit + Bithumb): лидеры {kmaj}; входов {len(kt_ev)}", flush=True)
    kt = {}
    for s, T in kt_ev:
        kt.setdefault(s, []).append(T)
    kt = {s: np.array(v) for s, v in kt.items()}
    Dk = G3.kshare(PER)
    ev.sort()
    rows, last = [], {}
    for T, s, ex in ev:
        if not (T0 <= T < T1) or T - last.get(s, -1e18) < 7 * DAY:
            continue
        o = kt.get(s, np.zeros(0))
        if ((o <= T) & (o >= T - 7 * DAY)).any():
            continue
        last[s] = T
        rows.append(dict(s=s, t=T, ex=ex, ks=G3.ks_at(Dk, s, T)))
    X = pd.DataFrame(rows, columns=["s", "t", "ex", "ks"])
    ktt = np.array([T for s, T in kt_ev if T0 <= T < T1], np.int64)
    show([by_month("👀-Корея всего", X.t), by_month("доля ≥ 20%", X[X.ks >= 0.2].t), by_month("< 20%", X[X.ks < 0.2].t),
          by_month("доли нет", X[X.ks.isna()].t), by_month("🔝 (сумма бирж)", ktt)],
         "| для сравнения s185: всего 14,5 / 27,7 в месяц (2020–22 / 2022–24), ≥ 20%: 2,5 / 5,8 / 12,7 (с 2024–26)")
    print("монеты событий:", X.s.value_counts().to_dict(), flush=True)
    EV["s185"] = X
    EV["s185_kt"] = ktt


# ------------------------------------------------------------------------------------------------ s190 Г2
def s190():
    print("\n=== s190 Г2: пробой цели Oₜ + 0,5·(Hₜ₋₁ − Lₜ₋₁) за сутки UTC у монет с рынком Upbit и долей Кореи ≥ 20%", flush=True)
    K, live = _K()
    P = pd.read_pickle(f"{D}/s183/daily_{PER}.pkl")[["d", "s", "qv", "sqv", "krv", "krv_upbit"]]
    P = P[P.krv_upbit.fillna(0) > 0].copy()
    P["share"] = P.krv / (P.krv + P.qv.fillna(0) + P.sqv.fillna(0))
    P = P[P.share >= 0.20]
    rows = []
    for s, g in P.groupby("s"):
        if s not in K:
            continue
        a = K[s]
        t = a["t"].astype(np.int64)
        lo, hi = live(s)
        if not np.isfinite(lo):
            continue
        o, h, l_ = (a[x].astype(float) for x in ("o", "h", "l"))
        days = g.d.values.astype(np.int64)
        i0 = np.searchsorted(t, days)
        ok = (i0 < len(t)) & (t[np.minimum(i0, len(t) - 1)] == days) & (i0 >= 96)
        for Dd, i, sh in zip(days[ok], i0[ok], g.share.values[ok]):
            if i + 96 >= len(t) or t[i + 96] != Dd + DAY or t[i - 96] != Dd - DAY:
                continue
            if Dd < lo + DAY or Dd + DAY > hi:
                continue
            target = o[i] + 0.5 * (h[i - 96:i].max() - l_[i - 96:i].min())
            rows.append((s, int(Dd), float(sh), bool(h[i:i + 95].max() > target)))
    X = pd.DataFrame(rows, columns=["s", "D", "share", "brk"])
    X = X[(X.D >= T0) & (X.D < T1)]
    show([by_month("монето-суток (доля ≥ 20%)", X.D), by_month("с пробоем", X[X.brk].D), by_month("без пробоя", X[~X.brk].D)],
         "| для сравнения s190: пробой 130 / 171 / 591 в месяц")
    print("монеты:", X.s.value_counts().head(15).to_dict(), flush=True)
    EV["s190"] = X


# ------------------------------------------------------------------------------------------------ s180
def s180():
    print("\n=== s180: круглый доллар на 15-мин свечах перпа (оборот за 24 ч ≥ 5 млн $, максимум за 30 сут — с заглушками "
          "до запуска, как в s180; перп ≥ 1 сут)", flush=True)
    K, live = _K()
    M = PD.load_script("research/s180/round_test.py", "s192_s180")
    M.GRIDS = {g: M.GRIDS[g] for g in ("r9", "c9", "r125", "c125")}       # без 99 сдвигов: нужны только частоты
    kind = pd.read_pickle(f"{D}/s12/perp_kind.pkl")
    bad = set(kind.get("tradfi", set())) | M.NONCRYPTO
    syms = [s for s in K if s not in bad and not s.endswith("USDC") and "qv" in K[s]]
    evA = {g: [] for g in M.GRIDS}
    evB = {g: [] for g in M.GRIDS}
    for s in syms:
        for g, (ta, tb) in M.usd_events(K[s], s, T0, T1).items():
            evA[g] += [(s, int(x)) for x in ta]
            evB[g] += [(s, int(x)) for x in tb]
    out = {}
    for nm, E, lag in (("B", evB, 0), ("A", evA, 4 * 3600)):
        for g in ("r9", "c9"):
            keep = []
            for s, tc in M.dedupe(E[g]):
                lo, _ = live(s)
                if tc + lag >= lo + DAY and tc + lag < T1:
                    keep.append((s, tc + lag))
            out[f"{nm}_{g}"] = pd.DataFrame(keep, columns=["s", "t"])
    show([by_month("B отказ, круглые", out["B_r9"].t), by_month("B контроль", out["B_c9"].t),
          by_month("A пробой, круглые", out["A_r9"].t), by_month("A контроль", out["A_c9"].t)],
         "| для сравнения s180: B круглые 31 / 46 / 87 в месяц, A 61 / 85 / 145")
    EV["s180"] = out


# ------------------------------------------------------------------------------------------------ s152
def s152():
    print("\n=== s152: час падения ликвидного альта к BTC (топ-30 по обороту за 30 сут, перп ≥ 30 сут, раз в 4 ч)", flush=True)
    _K()
    M = PD.load_script("research/s152/drop_events.py", "s192_s152")
    H = M.hourly_all()
    top = M.universe(H, T0, T1)
    sizes = pd.Series({d: len(v) for d, v in top.items()})
    print("монет во вселенной на сутки (медиана по месяцам):",
          sizes.groupby(month(sizes.index)).median().astype(int).to_dict(), flush=True)
    tab, out = [], {}
    for thr in (-0.01, -0.02, -0.03, -0.05):
        e = M.events(H, top, T0, T1, thr)
        x = pd.DataFrame(e, columns=["s", "t", "rel"])
        out[thr] = x
        tab.append(by_month(f"≤ {thr:+.0%}", x.t))
    show(tab, "| для сравнения s152 (≤ −2%): 638 / 370 / 603 в месяц")
    EV["s152"] = out


# ------------------------------------------------------------------------------------------------ пампы (🇰🇷, 🛒)
def pumps():
    print("\n=== Пампы +15% за ≤ 2 ч из покоя (s15/kr_panel.pumps, раз в сутки): основа 🇰🇷 и 🛒 (без BTC, ETH, DEFI)", flush=True)
    K, live = _K()
    W = f"{D}/s192/work/s15"
    PU = pickle.load(open(f"{W}/kr_pumps.pkl", "rb"))
    KP = pickle.load(open(f"{W}/kr_panel.pkl", "rb"))
    SP = pickle.load(open(f"{D}/s192/spot1h_2019.pkl", "rb"))
    allp, krp, spp = [], [], []
    for s, pj in PU.items():
        if s in ("BTC", "ETH", "DEFI") or not len(pj):
            continue
        a = K[s]
        Tps = (a["t"][pj].astype(np.int64) + 900)
        allp += [(s, int(x)) for x in Tps if T0 <= x < T1]
        kp = KP.get(s)                                         # 🇰🇷 как s118/kr_oos: доля часа панели, кулдаун 24 ч
        if kp is not None:
            Tv, sh, last = kp["T"].values, kp["share"].values, -1e18
            for Tp in Tps:
                k = int(np.searchsorted(Tv, Tp, side="right")) - 1
                if k < 0 or Tp - Tv[k] >= 3600 or Tp - last < 86400:
                    continue
                last = Tp
                if sh[k] >= 0.2 and T0 <= Tp < T1:
                    krp.append((s, int(Tp), float(sh[k])))
        sp = SP.get(s)                                         # 🛒 как s118/spot_oos: последний полный час, кулдаун 48 ч
        Tend = a["t"].astype(np.int64) + 900
        perp = pd.Series(a["qv"].astype(float)).groupby(((Tend - 1) // 3600 + 1) * 3600).sum()
        spv = pd.Series(sp[:, 1], index=sp[:, 0].astype(np.int64) + 3600) if sp is not None else None
        last = -1e18
        for Tp in Tps:
            if Tp - last < 48 * 3600:
                continue
            last = Tp
            if spv is None:
                continue
            Hh = (Tp // 3600) * 3600
            v, pv = float(spv.get(Hh, np.nan)), float(perp.get(Hh, np.nan))
            if v == v and pv == pv and v / max(v + pv, 1.0) >= 0.259 and T0 <= Tp < T1:
                spp.append((s, int(Tp)))
    show([by_month("пампы", [x[1] for x in allp]), by_month("🇰🇷: доля Кореи ≥ 20%", [x[1] for x in krp]),
          by_month("🛒: доля спота ≥ 25,9%", [x[1] for x in spp])],
         "| для сравнения s118 (событий в месяц, 2020–22 / 2022–24): 🇰🇷 16,7 / 8,8, 🛒 48,9 / 14,9; s49 (2024–26): 🛒 47")
    EV["pumps"] = dict(all=allp, kr=krp, spot=spp)


# ------------------------------------------------------------------------------------------------ s187
ATR = ["supertrend_kivanc", "chandelier_everget", "pp_supertrend", "ml_adaptive_st_algoalpha", "ut_bot"]


def atr():
    print("\n=== s187: часовые сигналы трейлинга ATR в неделях ликвидности (после прогрева)", flush=True)
    sys.path.insert(0, os.path.join(PD.REPO, "research", "s187"))
    import bars as BR  # noqa: E402
    PD.patch_module(BR, verbose=False)
    BR.OUT = f"{D}/s192"
    path = f"{D}/s192/bars_{PER}.pkl"
    if not os.path.exists(path):
        BR.build(PER)
    import indicators as I  # noqa: E402
    B = pickle.load(open(path, "rb"))
    coins = sorted(set(B["liq"].s) & set(B["1h"]))
    sig = {nm: ([], []) for nm in ATR}
    store = {nm: {} for nm in ATR}                              # формат s187/check.freq: {индикатор: {монета: (buy, sell)}}
    for s in coins:
        b = B["1h"][s]
        o, h, l_, c, v = (np.asarray(b[k], np.float64) for k in ("o", "h", "l", "c", "v"))
        t_close = np.asarray(b["t"], np.int64) + 3600
        weeks = np.sort(B["liq"].loc[B["liq"].s == s, "d0"].values.astype(np.int64))
        wk = np.searchsorted(weeks, t_close, "right") - 1
        inw = (wk >= 0) & (t_close >= B["t0"]) & (t_close < B["t1"])
        inw[inw] = t_close[inw] < weeks[wk[inw]] + WEEK
        nbefore = np.searchsorted(t_close, weeks, "left")
        for nm in ATR:
            m = I.REG[nm]
            r = m["fn"](o, h, l_, c, v)
            el = inw.copy()
            el[inw] = (nbefore >= m["warmup"])[wk[inw]]
            bu, se = t_close[r["buy"] & el], t_close[r["sell"] & el]
            sig[nm][0].append(bu)
            sig[nm][1].append(se)
            if len(bu) or len(se):
                store[nm][s] = (bu.astype(np.int64), se.astype(np.int64))
    pickle.dump(store, open(f"{D}/s192/signals_{PER}_1h.pkl", "wb"), protocol=5)
    nweeks = B["liq"].d0.nunique()
    print(f"монет {len(coins)}, недель с ликвидными альтами {nweeks}, монето-недель {len(B['liq'])}", flush=True)
    tab, out = [], {}
    for nm in ATR:
        bu = np.concatenate(sig[nm][0]) if sig[nm][0] else np.zeros(0, np.int64)
        se = np.concatenate(sig[nm][1]) if sig[nm][1] else np.zeros(0, np.int64)
        out[nm] = (bu, se)
        tab += [by_month(f"{nm} sell", se)]
    show(tab, "| для сравнения s187 (sell в месяц, 2020–22 / 2022–24 / 2024–26): SuperTrend 911 / 1539 / 2261, "
              "Chandelier 1233 / 2080 / 3044, PP 590 / 1021 / 1453, ML Adaptive 925 / 1566 / 2279, UT Bot 4693 / 7857 / 11063")
    EV["atr"] = out


PARTS = {"cover": cover, "s185": s185, "s190": s190, "s180": s180, "s152": s152, "pumps": pumps, "atr": atr}

if __name__ == "__main__":
    want = sys.argv[1:] or list(PARTS)
    for p in want:
        PARTS[p]()
    old = pickle.load(open(f"{D}/s192/freq_events.pkl", "rb")) if os.path.exists(f"{D}/s192/freq_events.pkl") else {}
    old.update(EV)
    pickle.dump(old, open(f"{D}/s192/freq_events.pkl", "wb"))
