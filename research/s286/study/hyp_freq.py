"""s286 — частоты гипотез Г1–Г5 (только счёт событий и кандидатов в сделки; доходы НЕ считаются).

Г1 — перелёт альтов после макрошока США: событие ≥ 3σ у BTC за 15 мин, альт ушёл дальше β·BTC в ту же сторону
     на ≥ max(1%, 2σ альта) — до 5 альтов на событие; для сравнения — такие же шоки BTC вне расписания.
Г2 — первый получас США: |z| хода BTC 09:30–10:00 ET ≥ 1,5; альты из 20 крупнейших с тем же знаком и |z| ≥ 1,5.
Г3 — воскресное открытие (вс 17:00 CT, фьючерсы на индексы и FX; CME-крипта до 29.05.2026): |z| хода BTC за первый
     час ≥ 2; альты из 20 крупнейших с тем же знаком и |z| ≥ 1,5. Ещё — выходные с |ходом BTC| ≥ 3% (пт 16:00 → вс 17:00 CT).
Г4 — вето макро-окна у внутридневных журналов (🛒 → 🛒⁸, ⏰, 🐋 → 🐋⁸): доля входов, у которых в 8 ч после входа
     CPI, NFP, PPI, PCE, решение или пресс-конференция FOMC.
Г5 — притяжение к max pain недельных экспираций Deribit: в T − 8 ч (00:00 UTC пятницы) цена перпа в 1–4% от max pain
     (по OI на экспирации; поправка на заглядывание — deribit_late.py).
Запуск — из /home/user/mc_data: python3 -I <repo>/research/s286/study/hyp_freq.py → /home/user/mc_data/s286/hyp_freq.txt"""
import datetime as dt
import importlib.util
import json
import os
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("vs", os.path.join(HERE, "volstudy.py"))
V = importlib.util.module_from_spec(spec); spec.loader.exec_module(V)
OUT = "/home/user/mc_data/s286"
NY, CT = ZoneInfo("America/New_York"), ZoneInfo("America/Chicago")
MACRO = {"CPI", "NFP", "PPI", "PCE", "RETAIL", "GDP", "JOLTS", "ISM_M", "FOMC", "FOMC_PC"}
TIER1 = {"CPI", "NFP", "PPI", "PCE", "FOMC", "FOMC_PC"}
BAR, DAY = 900, 86400


def ret(D, j, i0, i1):
    """Доход монет j от закрытия свечи i0 − 1 до закрытия свечи i1 − 1 (цены в моменты t(i0) и t(i1))."""
    return D["C"][j, i1 - 1] / D["C"][j, i0 - 1] - 1


def shock_alts(D, i, k_bars, top_n, need_sign=True):
    """BTC-шок и альты-«перелёты» за k_bars свечей от момента i (индекс свечи, открытой в T)."""
    d = i // 96
    ib = D["ib"]
    rb = ret(D, ib, i, i + k_bars)
    sb = D["sig"][ib, d] * np.sqrt(k_bars)
    top = D["top"][d][:top_n]
    top = top[top >= 0]
    ra = ret(D, top, i, i + k_bars)
    sa = D["sig"][top, d] * np.sqrt(k_bars)
    be = D["beta"][top, d]
    return rb, sb, top, ra, sa, be


def g1(D, E, per_rows, per):
    ev = E[E.fam.isin(MACRO)]
    T = np.unique(ev.t.to_numpy())
    T = T[(T >= D["a"]) & (T < D["b"])]
    allT = np.sort(E[E.fam.isin(V.BUSY)].t.to_numpy())
    n_ev, n_shock, n_tr, n_shock_t1 = 0, 0, 0, 0
    for t in T:
        i = (t // BAR * BAR - D["t0"]) // BAR
        rb, sb, top, ra, sa, be = shock_alts(D, i, 1, V.NALT)
        if not np.isfinite(rb) or not np.isfinite(sb) or sb <= 0:
            continue
        n_ev += 1
        if abs(rb) / sb < 3:
            continue
        n_shock += 1
        fams = set(ev[ev.t == t].fam)
        n_shock_t1 += bool(fams & TIER1)
        e = ra - be * rb
        ok = np.isfinite(e) & (np.sign(e) == np.sign(rb)) & (np.abs(e) >= np.maximum(0.01, 2 * sa))
        n_tr += min(5, int(ok.sum()))
    # такие же шоки BTC вне расписания (нет событий ±3 ч), на сетке 15 мин
    ib = D["ib"]
    C = D["C"][ib]
    lo = max(D["a"], D["t0"] + 8 * DAY)
    idx = np.arange((lo - D["t0"]) // BAR, (D["b"] - D["t0"]) // BAR)
    r = C[idx] / C[idx - 1] - 1
    s = D["sig"][ib, idx // 96]
    z = np.abs(r) / s
    tt = D["t0"] + idx * BAR
    j = np.searchsorted(allT, tt - 3 * 3600)
    busy = (j < len(allT)) & (allT[np.minimum(j, len(allT) - 1)] <= tt + 3 * 3600)
    un = (z >= 3) & ~busy
    # одно на 3 ч
    last, cnt = -10 ** 12, 0
    for t in tt[un]:
        if t - last >= 3 * 3600:
            cnt += 1; last = t
    mo = (D["b"] - D["a"]) / (30.44 * DAY)
    per_rows.append(dict(hyp="Г1", period=per, events=round(n_ev / mo, 2), shocks=round(n_shock / mo, 2),
                         shocks_tier1=round(n_shock_t1 / mo, 2), trades=round(n_tr / mo, 2),
                         unscheduled_shocks=round(cnt / mo, 2)))


def g2(D, per_rows, per, kind):
    K = V.kinds(pd.DataFrame({"fam": [], "t": []}))
    days_ok = K["nyse"] if kind == "nyse" else (K["nyse_hol"] if kind == "nyse_hol" else K["weekend"])
    n_day, n_btc, n_tr = 0, 0, 0
    d = dt.date(2020, 9, 1)
    while d < dt.date(2026, 10, 20):
        if days_ok(d):
            t = int(dt.datetime(d.year, d.month, d.day, 9, 30, tzinfo=NY).timestamp())
            if D["a"] <= t < D["b"]:
                i = (t - D["t0"]) // BAR
                rb, sb, top, ra, sa, be = shock_alts(D, i, 2, 20)
                if np.isfinite(rb) and np.isfinite(sb) and sb > 0:
                    n_day += 1
                    if abs(rb) / sb >= 1.5:
                        n_btc += 1
                        ok = np.isfinite(ra) & (np.sign(ra) == np.sign(rb)) & (np.abs(ra) / sa >= 1.5)
                        n_tr += 1 + int(ok.sum())
        d += dt.timedelta(days=1)
    mo = (D["b"] - D["a"]) / (30.44 * DAY)
    per_rows.append(dict(hyp="Г2", period=per, days=kind, events=round(n_day / mo, 2), shocks=round(n_btc / mo, 2),
                         trades=round(n_tr / mo, 2)))


def g3(D, per_rows, per):
    n_sun, n_btc, n_tr, n_wk = 0, 0, 0, 0
    d = dt.date(2020, 9, 6)
    while d < dt.date(2026, 10, 20):
        if d.weekday() == 6:
            t = int(dt.datetime(d.year, d.month, d.day, 17, 0, tzinfo=CT).timestamp())
            f = d - dt.timedelta(days=2)
            tf = int(dt.datetime(f.year, f.month, f.day, 16, 0, tzinfo=CT).timestamp())
            if D["a"] <= tf and t < D["b"]:
                i = (t - D["t0"]) // BAR
                rb, sb, top, ra, sa, be = shock_alts(D, i, 4, 20)
                if np.isfinite(rb) and np.isfinite(sb) and sb > 0:
                    n_sun += 1
                    if abs(rb) / sb >= 2:
                        n_btc += 1
                        ok = np.isfinite(ra) & (np.sign(ra) == np.sign(rb)) & (np.abs(ra) / sa >= 1.5)
                        n_tr += int(ok.sum())
                    iw = (tf - D["t0"]) // BAR
                    rw = D["C"][D["ib"], i - 1] / D["C"][D["ib"], iw - 1] - 1
                    n_wk += abs(rw) >= 0.03
        d += dt.timedelta(days=1)
    mo = (D["b"] - D["a"]) / (30.44 * DAY)
    per_rows.append(dict(hyp="Г3", period=per, events=round(n_sun / mo, 2), shocks=round(n_btc / mo, 2),
                         trades=round(n_tr / mo, 2), weekend_ge3pct=round(n_wk / mo, 2)))


def g4(E, per_rows):
    ev = np.sort(E[E.fam.isin(TIER1)].t.to_numpy())
    src = {"🛒 (s270, доля спота ≥ 26%)": ("s270", lambda x: x[(x.grp == "S") & (x.hold == 8)], "te"),
           "⏰ (s277)": ("s277", lambda x: x[(x.h == "⏰") & (x.ex == "8 ч")], "te"),
           "🐋 (s284)": ("s284", lambda x: x[x.ex == "8 ч"], "t")}
    for name, (pre, sel, col) in src.items():
        for per, (_, a, b) in V.PER.items():
            fn = f"/home/user/mc_data/{pre}_{per}.pkl"
            if not os.path.exists(fn):
                continue
            x = sel(pd.read_pickle(fn))
            t = x[col].astype(np.int64).to_numpy()            # только моменты входа; доходы не читаются
            j = np.searchsorted(ev, t)
            hit = (j < len(ev)) & (ev[np.minimum(j, len(ev) - 1)] <= t + 8 * 3600)
            mo = (V.ts(b) - V.ts(a)) / (30.44 * DAY)
            per_rows.append(dict(hyp="Г4", period=per, journal=name, entries=round(len(t) / mo, 2),
                                 with_macro=round(hit.sum() / mo, 2), share=round(hit.mean(), 3)))


def g5(D, per_rows, per):
    ex = json.load(open("/home/user/mc_data/s157/expiries.json"))
    for cur in ("BTC", "ETH"):
        j = D["coins"].index(cur)
        n_all, n_in, n_mq = 0, 0, 0
        for x in ex:
            if x["cur"] != cur or x["type"] not in ("W", "M", "Q"):
                continue
            t = int(pd.Timestamp(x["t"]).floor("15min").timestamp())
            if not (D["a"] <= t < D["b"]):
                continue
            i = (t - 8 * 3600 - D["t0"]) // BAR
            s = D["C"][j, i - 1]
            if not np.isfinite(s) or not x["maxpain"]:
                continue
            n_all += 1
            dist = abs(x["maxpain"] / s - 1)
            if 0.01 <= dist <= 0.04:
                n_in += 1
                n_mq += x["type"] in ("M", "Q")
        mo = (D["b"] - D["a"]) / (30.44 * DAY)
        per_rows.append(dict(hyp="Г5", period=per, cur=cur, events=round(n_all / mo, 2), in_band=round(n_in / mo, 2),
                             in_band_MQ=round(n_mq / mo, 2)))


def g6(D, per_rows, per):
    """Фиксинг ETF (BRRNY 15:00–16:00 ET): дни NYSE без короткого дня; |z| хода окна ≥ 1 — BTC и ETH."""
    K = V.kinds(pd.DataFrame({"fam": [], "t": []}))
    for kind in ("nyse", "nyse_hol", "weekend"):
        ok_d = K[kind]
        for cur, start in (("BTC", dt.date(2024, 1, 11)), ("ETH", dt.date(2024, 7, 23))):
            j = D["coins"].index(cur)
            n_all, n_z = 0, 0
            d = dt.date(2020, 9, 1)
            while d < dt.date(2026, 10, 20):
                if ok_d(d) and d.isoformat() not in V.NYSE_EARLY:
                    t = int(dt.datetime(d.year, d.month, d.day, 15, 0, tzinfo=NY).timestamp())
                    if D["a"] <= t < D["b"]:
                        i = (t - D["t0"]) // BAR
                        r = ret(D, j, i, i + 4)
                        sg = D["sig"][j, i // 96] * 2
                        if np.isfinite(r) and sg > 0:
                            n_all += 1
                            n_z += abs(r) / sg >= 1
                d += dt.timedelta(days=1)
            mo = (D["b"] - D["a"]) / (30.44 * DAY)
            era = "ETF" if D["b"] > V.ts(start.isoformat()) else "до ETF"
            per_rows.append(dict(hyp="Г2-фиксинг", period=per, days=kind, cur=cur, events=round(n_all / mo, 2),
                                 shocks=round(n_z / mo, 2), note=f"ETF с {start}" if kind == "nyse" else ""))


def g7(D, E, per_rows, per):
    """Макрорелиз США: шок BTC за 30 мин |z| ≥ 2; альты из 50 с остатком в сторону шока ≥ max(1%, 2σ) — до 5."""
    for fams, nm in ((TIER1, "tier1"), (MACRO | {"CLAIMS", "ISM_S", "DURABLE", "GDP23"}, "все 08:30/10:00 + FOMC")):
        ev = E[E.fam.isin(fams)]
        T = np.unique(ev.t.to_numpy())
        T = T[(T >= D["a"]) & (T < D["b"])]
        n_ev, n_sh, n_tr = 0, 0, 0
        for t in T:
            i = (t // BAR * BAR - D["t0"]) // BAR
            rb, sb, top, ra, sa, be = shock_alts(D, i, 2, V.NALT)
            if not np.isfinite(rb) or not np.isfinite(sb) or sb <= 0:
                continue
            n_ev += 1
            if abs(rb) / sb < 2:
                continue
            n_sh += 1
            e = ra - be * rb
            ok = np.isfinite(e) & (np.sign(e) == np.sign(rb)) & (np.abs(e) >= np.maximum(0.01, 2 * sa))
            n_tr += min(5, int(ok.sum()))
        mo = (D["b"] - D["a"]) / (30.44 * DAY)
        per_rows.append(dict(hyp="Г3-перелёт30", period=per, days=nm, events=round(n_ev / mo, 2),
                             shocks=round(n_sh / mo, 2), trades=round(n_tr / mo, 2)))


def g8(D, per_rows, per):
    """Воскресенье 17:00 CT, мягкий порог: |z| хода BTC за первый час ≥ 1; альты из 10 с тем же знаком и |z| ≥ 1."""
    for wd, nm in ((6, "вс"), (5, "сб (контроль)")):
        n_d, n_sh, n_tr = 0, 0, 0
        d = dt.date(2020, 9, 5)
        while d < dt.date(2026, 10, 20):
            if d.weekday() == wd:
                t = int(dt.datetime(d.year, d.month, d.day, 17, 0, tzinfo=CT).timestamp())
                if D["a"] <= t < D["b"]:
                    i = (t - D["t0"]) // BAR
                    rb, sb, top, ra, sa, be = shock_alts(D, i, 4, 10)
                    if np.isfinite(rb) and sb > 0:
                        n_d += 1
                        if abs(rb) / sb >= 1:
                            n_sh += 1
                            ok = np.isfinite(ra) & (np.sign(ra) == np.sign(rb)) & (np.abs(ra) / sa >= 1)
                            n_tr += 1 + int(ok.sum())
            d += dt.timedelta(days=1)
        mo = (D["b"] - D["a"]) / (30.44 * DAY)
        per_rows.append(dict(hyp="Г4-воскресенье", period=per, days=nm, events=round(n_d / mo, 2),
                             shocks=round(n_sh / mo, 2), trades=round(n_tr / mo, 2)))


def g9(D, E, per_rows, per):
    """Все шоки BTC за 15 мин |z| ≥ 3 (одно на 3 ч): по расписанию (макро ±0) и вне расписания (нет событий ±3 ч);
    альты из 50 с остатком в сторону шока ≥ max(1%, 2σ) — до 5 на шок."""
    allT = np.sort(E[E.fam.isin(V.BUSY)].t.to_numpy())
    mac = set(E[E.fam.isin(MACRO)].t // BAR * BAR)
    ib = D["ib"]
    lo = max(D["a"], D["t0"] + 8 * DAY)
    idx = np.arange((lo - D["t0"]) // BAR, (D["b"] - D["t0"]) // BAR - 12)
    C = D["C"][ib]
    z = np.abs(C[idx] / C[idx - 1] - 1) / D["sig"][ib, idx // 96]
    tt = D["t0"] + idx * BAR
    cnt = {"по расписанию": [0, 0], "вне расписания": [0, 0], "рядом с событием": [0, 0]}
    last = -10 ** 12
    for k in np.flatnonzero(z >= 3):
        t = tt[k]
        if t - last < 3 * 3600:
            continue
        last = t
        if t in mac:
            g = "по расписанию"
        else:
            j = np.searchsorted(allT, t - 3 * 3600)
            g = "рядом с событием" if (j < len(allT) and allT[j] <= t + 3 * 3600) else "вне расписания"
        rb, sb, top, ra, sa, be = shock_alts(D, idx[k], 1, V.NALT)
        e = ra - be * rb
        ok = np.isfinite(e) & (np.sign(e) == np.sign(rb)) & (np.abs(e) >= np.maximum(0.01, 2 * sa))
        cnt[g][0] += 1
        cnt[g][1] += min(5, int(ok.sum()))
    mo = (D["b"] - D["a"]) / (30.44 * DAY)
    for g, (n, tr) in cnt.items():
        per_rows.append(dict(hyp="Г3-все-шоки", period=per, days=g, shocks=round(n / mo, 2), trades=round(tr / mo, 2)))


def main():
    E = pd.read_csv(f"{OUT}/events.csv")
    rows = []
    for per in V.PER:
        D = V.load_period(per)
        V.daily_aux(D)
        g1(D, E, rows, per)
        for kind in ("nyse", "nyse_hol", "weekend"):
            g2(D, rows, per, kind)
        g3(D, rows, per)
        g5(D, rows, per)
        g6(D, rows, per)
        g7(D, E, rows, per)
        g8(D, rows, per)
        g9(D, E, rows, per)
        print(per, "готово", flush=True)
        del D
    g4(E, rows)
    R = pd.DataFrame(rows)
    with open(f"{OUT}/hyp_freq.txt", "w") as f:
        for h, g in R.groupby("hyp"):
            g = g.dropna(axis=1, how="all")
            f.write(f"\n{h}\n{g.to_string(index=False)}\n")
            print(h); print(g.to_string(index=False))


if __name__ == "__main__":
    main()
