"""s186 — частоты событий-кандидатов по трём периодам, размер потока ребаланса к обороту перпа Binance, след ребаланса
в обороте (без цены и знака), пересечения с журналами (входы журнала по монете за 48 ч ДО события).

Входы: cd_<период>.pkl (panel186.py), lt_universe.pkl и gate_daily.pkl (lt_lists.py), ftx_mult.pkl (ftx_supply.py),
daily_<период>.pkl s183 (оборот в Корее — признак рынка к воне), журналы — common183.journals.
Доходы после момента события, сделки и плацебо НЕ считаются. Лог — hyp186.log, таблицы — hyp186.pkl."""
import os
import pickle

import numpy as np
import pandas as pd

import common186 as C

L = C.Log("hyp186")
K_GATE = 2.0           # AUM токена Gate ≈ его суточный оборот / K (по пресс-релизу Gate 2021: $100 млн AUM при $100–420 млн
#                        оборота в сутки); оценка порядка величины
THR = (0.05, 0.10, 0.15)
BUCK = [(0, 0.02), (0.02, 0.05), (0.05, 0.10), (0.10, 0.20), (0.20, 9.0)]


def months(per):
    return C.C3.months(per)


def intervals(U, ex, levs=None):
    """{базовый: [(t0, t1, плечо)]} токенов биржи."""
    out = {}
    u = U[U.ex == ex]
    if levs is not None:
        u = u[u.lev.isin(levs)]
    for r in u.itertuples():
        out.setdefault(r.und, []).append((r.t0, r.t1, r.lev))
    return out


def has(cd, iv):
    """Маска строк cd, у которых в момент T есть хотя бы один токен из iv."""
    T = cd.D.values + cd.H.values.astype(np.int64) * 3600
    m = np.zeros(len(cd), bool)
    bb = cd.b.astype(str).values
    for b, lst in iv.items():
        sel = bb == b
        if not sel.any():
            continue
        tt = T[sel]
        mm = np.zeros(sel.sum(), bool)
        for t0, t1, _ in lst:
            mm |= (tt >= t0) & (tt <= t1)
        m[np.flatnonzero(sel)] = mm
    return m


def gate_mult(cd_rows, gdaily, G):
    """Множитель ребаланса Gate по оценке AUM из оборота токенов за 7 сут до T: Σ L(L−1)·оборот/K_GATE."""
    lev = dict(zip(G.pair, G.lev))
    und = dict(zip(G.pair, G.und))
    t_switch = C.ts("2025-04-01") + 16 * 3600       # до 01.04.2025 токены «3x» Gate держали целевое плечо 2,3
    by = {}
    for pair, df in gdaily.items():
        if pair not in lev:
            continue
        s = df.qv.rolling(7, min_periods=1).mean().shift(1)          # только сутки до T
        L0 = float(lev[pair])
        Le = np.where((abs(L0) == 3) & (df.index.values < t_switch), np.sign(L0) * 2.3, L0)
        by.setdefault(und[pair], []).append(pd.Series(Le * (Le - 1), index=df.index) * s / K_GATE)
    Mu = {u: pd.concat(v, axis=1).sum(axis=1) for u, v in by.items()}
    out = np.full(len(cd_rows), np.nan)
    bb = cd_rows.b.astype(str).values
    for u, s in Mu.items():
        sel = np.flatnonzero(bb == u)
        if not len(sel):
            continue
        out[sel] = s.reindex(cd_rows.D.values[sel]).values
    return out


def ftx_mult_rows(cd_rows, M):
    out = np.full(len(cd_rows), np.nan)
    if M is None:
        return out
    bb = cd_rows.b.astype(str).values
    for u in M.columns:
        sel = np.flatnonzero(bb == u)
        if not len(sel):
            continue
        out[sel] = M[u].reindex(cd_rows.D.values[sel] - C.DAY).values      # AUM на закрытие суток до 00:00
    return out


def pre_journal(ev_b, ev_t, J, win=48 * 3600):
    """Доля событий, у которых по той же монете был вход журнала за win до события; по журналам."""
    if not len(ev_b):
        return {}, 0.0
    J = J.copy()
    J["b"] = J.s.map(C.C3.base)
    by = {b: g for b, g in J.groupby("b")}
    hit_any = np.zeros(len(ev_b), bool)
    per_j = {}
    for i, (b, t) in enumerate(zip(ev_b, ev_t)):
        g = by.get(b)
        if g is None:
            continue
        x = g[(g.t >= t - win) & (g.t < t)]
        if len(x):
            hit_any[i] = True
            for j in set(x.j):
                per_j[j] = per_j.get(j, 0) + 1
    return {j: v / len(ev_b) for j, v in per_j.items()}, hit_any.mean()


def krw_flag(per, cd_rows):
    p = f"{C.D}/s183/daily_{per}.pkl"
    if not os.path.exists(p):
        return np.zeros(len(cd_rows), bool)
    d = pd.read_pickle(p)[["d", "s", "krv"]]
    d["b"] = d.s.map(C.C3.base)
    k = set(zip(d.b[d.krv > 0], d.d[d.krv > 0].astype(np.int64)))
    return np.array([(b, D - C.DAY) in k for b, D in zip(cd_rows.b.astype(str), cd_rows.D)])


def describe_flow(x, name):
    x = x[np.isfinite(x)]
    if not len(x):
        return f"{name}: нет данных"
    q = np.percentile(x, [50, 75, 90])
    return (f"{name}: медиана {q[0] * 100:.2f}%, p75 {q[1] * 100:.2f}%, p90 {q[2] * 100:.2f}%, "
            f"≥10% у {np.mean(x >= 0.10) * 100:.0f}%, ≥50% у {np.mean(x >= 0.5) * 100:.0f}%")


def main():
    UU = pickle.load(open(f"{C.OUT}/lt_universe.pkl", "rb"))
    U, G = UU["U"], UU["G"]
    gdaily = pickle.load(open(f"{C.OUT}/gate_daily.pkl", "rb"))
    M = pickle.load(open(f"{C.OUT}/ftx_mult.pkl", "rb")) if os.path.exists(f"{C.OUT}/ftx_mult.pkl") else None
    iv_ftx = intervals(U, "ftx", levs=[3.0, -3.0])
    iv_bin = intervals(U, "binance")
    iv_gate = intervals(U, "gate")
    res = {}
    for per in C.PERS:
        X = pickle.load(open(f"{C.OUT}/cd_{per}.pkl", "rb"))
        cd = X["cd"]
        mo = months(per)
        L(f"\n================ {per} ({mo:.1f} мес.; монет {cd.b.nunique()}) ================")
        cd["ftx"] = has(cd, iv_ftx)
        cd["blvt"] = has(cd, iv_bin)
        cd["gate"] = has(cd, iv_gate)
        J = C.C3.journals(per)
        # --- охват
        for g in ("ftx", "blvt", "gate"):
            x = cd[cd.H == 0]
            n = x.groupby("D")[g].sum()
            L(f"монет с токенами {g}: в среднем на сутки {n.mean():.1f} (макс {n.max()}), разных {x[x[g]].b.nunique()}")
        # --- E1: FTX, якорь 00 UTC
        e = cd[(cd.H == 0) & cd.ftx].copy()
        if len(e):
            e["M"] = ftx_mult_rows(e, M)
            e["krw"] = krw_flag(per, e)
            L("\nE1 FTX, 00:02 UTC: монето-суток с BULL/BEAR:", len(e))
            for thr in THR:
                up = e[e.r24 >= thr]
                dn = e[e.r24 <= -thr]
                L(f"  r24 ≥ {thr:.0%}: {len(up) / mo:.1f} в мес. (с рынком к воне {up.krw.mean() * 100:.0f}%); "
                  f"r24 ≤ −{thr:.0%}: {len(dn) / mo:.1f} в мес.")
            for thr in (0.05, 0.10):
                up = e[e.r24 >= thr]
                f_day = (up.M * up.r24 / up.v7).values
                f_slot = (up.M * up.r24 / up.q_base).values
                L("  " + describe_flow(f_day, f"поток/суточный оборот перпа при r24 ≥ {thr:.0%}"))
                L("  " + describe_flow(f_slot, f"поток/оборот свечи 00:00–00:15 (медиана 14 сут) при r24 ≥ {thr:.0%}"))
                for fmin in (0.25, 1.0):
                    L(f"    событий с потоком ≥ {fmin:.0%} оборота свечи: {np.nansum(f_slot >= fmin) / mo:.1f} в мес.")
            # пороги внутридневного ребаланса FTX: BEAR при +6,67%, BULL при −11,1% от цены 00:00
            L(f"  пересечение +6,67% от 00:00 (ребаланс BEAR) до следующих 00:00: {(e.up_6_67 >= 0).sum() / mo:.1f} в мес.;"
              f" −11,1% (BULL): {(e.dn_11_1 >= 0).sum() / mo:.1f} в мес.")
            ev = e[e.r24 >= 0.10]
            pj, pa = pre_journal(ev.b.astype(str).values, (ev.D + 0).values, J)
            L(f"  E1 (r24 ≥ 10%): вход любого журнала по монете за 48 ч до 00:00 — {pa * 100:.0f}%; " +
              ", ".join(f"{j} {v * 100:.0f}%" for j, v in sorted(pj.items(), key=lambda z: -z[1])))
            res[(per, "E1")] = e
        # контроль E1: монеты без токенов FTX в тот же час и те же монеты в другие часы
        c0 = cd[(cd.H == 0) & ~cd.ftx & ~cd.blvt]
        L(f"  контроль: монеты без FTX и BLVT, 00 UTC, r24 ≥ 10%: {(c0.r24 >= 0.10).sum() / mo:.1f} в мес.; "
          f"монеты FTX в 04/08/12/20 UTC, r24 ≥ 10%: " +
          ", ".join(f"{h:02d} {((cd.H == h) & cd.ftx & (cd.r24 >= 0.10)).sum() / mo:.1f}" for h in (4, 8, 12, 20)))
        # события s135 (скачок ≥ 5% за 00–01 UTC у монет без рынка к воне) и входы ⏰ по наличию токенов FTX —
        # только монета и время (доходы файла не читаются)
        p135 = f"{C.D}/s135_{per}.pkl"
        if os.path.exists(p135):
            s135 = pd.read_pickle(p135)[["s", "t", "open0"]]
            s135 = s135[s135.open0.astype(bool)]
            s135["b"] = s135.s.map(C.C3.base)
            d0 = (s135.t // C.DAY) * C.DAY
            ftx_now = np.array([any(t0 <= d <= t1 for t0, t1, _ in iv_ftx.get(b, [])) for b, d in zip(s135.b, d0)])
            bin_now = np.array([any(t0 <= d <= t1 for t0, t1, _ in iv_bin.get(b, [])) for b, d in zip(s135.b, d0)])
            L(f"  s135 (00–01 UTC, без рынка к воне): событий {len(s135)} ({len(s135) / mo:.1f} в мес.), у монет FTX "
              f"{ftx_now.sum()} ({ftx_now.mean() * 100:.0f}%), BLVT {bin_now.sum()}")
            o9 = J[J.j == "⏰"].copy()
            o9["b"] = o9.s.map(C.C3.base)
            d9 = (o9.t // C.DAY) * C.DAY
            f9 = np.array([any(t0 <= d <= t1 for t0, t1, _ in iv_ftx.get(b, [])) for b, d in zip(o9.b, d9)])
            L(f"  ⏰: входов {len(o9)}, у монет FTX {f9.sum()} ({f9.mean() * 100 if len(f9) else 0:.0f}%)")
        # --- E2: Gate (выжившие токены), якорь 16 UTC
        e2 = cd[(cd.H == 16) & cd.gate].copy()
        L(f"\nE2 Gate, 16:00 UTC: монето-суток с токенами Gate (выжившие пары): {len(e2)}")
        if len(e2):
            e2["M"] = gate_mult(e2, gdaily, G)
            for thr in THR:
                L(f"  r24 ≥ {thr:.0%}: {(e2.r24 >= thr).sum() / mo:.1f} в мес.; r24 ≤ −{thr:.0%}: "
                  f"{(e2.r24 <= -thr).sum() / mo:.1f} в мес.")
            up = e2[e2.r24 >= 0.10].copy()
            L("  " + describe_flow((up.M * up.r24 / up.v7).values, "K=2: поток/суточный оборот перпа Binance при r24 ≥ 10%"))
            L("  " + describe_flow((up.M * up.r24 / up.q_base).values, "K=2: поток/оборот свечи 16:00–16:15 Binance при r24 ≥ 10%"))
            gp = pickle.load(open(f"{C.OUT}/gate_perp_daily.pkl", "rb")) if os.path.exists(f"{C.OUT}/gate_perp_daily.pkl") else {}
            gv = np.full(len(up), np.nan)
            for i, (b, D) in enumerate(zip(up.b.astype(str), up.D)):
                df = gp.get(b)
                if df is not None and len(df):
                    w = df.qv[(df.index >= D - 7 * C.DAY) & (df.index < D)]
                    if len(w):
                        gv[i] = w.mean()
            L("  " + describe_flow(up.M.values * up.r24.values / gv, "K=2: поток/суточный оборот перпа Gate при r24 ≥ 10%"))
            L(f"  оборот перпа Gate к перпу Binance (медиана по событиям): {np.nanmedian(gv / up.v7.values) * 100:.1f}%")
            L(f"  пересечения от цены 16:00: +12% (3S) {(e2.up_12 >= 0).sum() / mo:.1f}, +20% (3L) "
              f"{(e2.up_20 >= 0).sum() / mo:.1f}, −12% (3L) {(e2.dn_12 >= 0).sum() / mo:.1f}, −20% (3S) "
              f"{(e2.dn_20 >= 0).sum() / mo:.1f}, ±15% (MEXC) {((e2.up_15 >= 0) | (e2.dn_15 >= 0)).sum() / mo:.1f} в мес.")
            for col, name in (("up_12", "+12%"), ("up_6_67", "+6,67%")):
                cx = e2[e2[col] >= 0]
                te = (cx.D - C.DAY + 16 * 3600 + 900 * (cx[col].astype(np.int64) + 1)).values
                pj, pa = pre_journal(cx.b.astype(str).values, te, J)
                L(f"  пересечение {name} от 16:00: {len(cx) / mo:.1f} в мес.; вход журнала за 48 ч до пересечения — "
                  f"{pa * 100:.0f}%; " + ", ".join(f"{j} {v * 100:.0f}%" for j, v in sorted(pj.items(), key=lambda z: -z[1])))
            ev = e2[e2.r24 >= 0.10]
            pj, pa = pre_journal(ev.b.astype(str).values, (ev.D + 16 * 3600).values, J)
            L(f"  E2 (r24 ≥ 10%): вход журнала за 48 ч до 16:00 — {pa * 100:.0f}%; " +
              ", ".join(f"{j} {v * 100:.0f}%" for j, v in sorted(pj.items(), key=lambda z: -z[1])))
            res[(per, "E2")] = e2
        a16 = cd[cd.H == 16]
        L(f"  все монеты (верхняя граница охвата эмитентами 00:00 UTC+8 в 2020–2024 гг.), 16 UTC: r24 ≥ 10% "
          f"{(a16.r24 >= 0.10).sum() / mo:.1f} в мес., пересечение +12% от 16:00 {(a16.up_12 >= 0).sum() / mo:.1f}, "
          f"±15% {((a16.up_15 >= 0) | (a16.dn_15 >= 0)).sum() / mo:.1f} в мес.")
        # --- след ребаланса в обороте: медиана q_slot/q_base по |r24|, группам и часам
        L("\nслед в обороте: медиана (оборот свечи [T, T+15 мин) / её медиана за 14 сут) по |r24| "
          "(корзины <2 / 2–5 / 5–10 / 10–20 / ≥20%):")
        cd["ar"] = cd.r24.abs()
        cd["ratio"] = cd.q_slot / cd.q_base
        cd["pratio"] = cd.q_pre / cd.q_pre_base
        none = ~cd.ftx & ~cd.blvt & ~cd.gate
        if per == "2020–2022":
            groups = [("FTX", cd.ftx), ("BLVT", cd.blvt), ("Gate", cd.gate), ("без токенов", none)]
        elif per == "2022–2024":
            groups = [("BLVT", cd.blvt), ("Gate", cd.gate), ("без токенов", none)]
        else:
            groups = [("Gate", cd.gate), ("без токенов", none)]
        fp = {}
        for gname, gm in groups:
            for h in (0, 4, 8, 12, 16, 20):
                x = cd[gm & (cd.H == h) & np.isfinite(cd.ratio)]
                med = [x.ratio[(x.ar >= lo) & (x.ar < hi)].median() for lo, hi in BUCK]
                pmed = [x.pratio[(x.ar >= lo) & (x.ar < hi)].median() for lo, hi in BUCK]
                nn = [int(((x.ar >= lo) & (x.ar < hi)).sum()) for lo, hi in BUCK]
                fp[(gname, h)] = (med, pmed, nn)
                L(f"  {gname:13s} {h:02d} UTC: " + " / ".join(f"{m:.2f}" for m in med) +
                  f"   (пред. свеча: " + " / ".join(f"{m:.2f}" for m in pmed) + f"; n {nn[0]}…{nn[-1]})")
        res[(per, "fp")] = fp
    pickle.dump({k: v for k, v in res.items() if k[1] == "fp"}, open(f"{C.OUT}/hyp186.pkl", "wb"))


if __name__ == "__main__":
    main()
