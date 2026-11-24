"""s275 — описательные статистики связей между монетами на отрезке замысла 01.10.2022–01.10.2023 (k_oos).
Доходы сделок и правил не считаются; это статистика рядов: доля общей дисперсии, автокорреляции и отношения дисперсий
остатков, наклоны «прошлое → будущее» остатков (линейная автокорреляция по горизонтам), опережение-запаздывание,
коинтеграция и полураспад спредов, устойчивость корреляций месяц к месяцу.

Устройство:
- месяц оценки m = 11.2022 … 09.2023; модель оценивается на прошлом календарном месяце (вне выборки);
- вселенная месяца — 100 перпов с наибольшим оборотом за 30 сут до начала месяца (`liquid_rank` на первый день);
  в расчёт — перпы с часовыми ценами ≥ 90% часов и в месяце оценки, и в месяце модели;
- факторы: BTC и индекс альтов (равный вес вселенной суток без BTC, часовые лог-доходы, обрезка ±50%);
  сектор — равный вес других членов вселенной того же сектора (нужно ≥ 3 других);
- остаток e1 = r − a − b·BTC − c·альты; e2 — плюс сектор (−i); коэффициенты — с прошлого месяца;
- 15-мин часть (опережение-запаздывание) — та же схема на 15-мин лог-доходах.
Запуск: из /home/user/mc_data — python3 -I <repo>/research/s275/study/stats_design.py → OUT/stats_design.txt"""
import os
import pickle
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common275 import BAR, DAY, DESIGN, H, OUT, TMP, adf_t, half_life, load_k, panel, perps, sectors, ts, universe  # noqa

PER = "2022–2024"
LINES = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LINES.append(s)


def month_starts():
    out = []
    y, m = 2022, 11
    while (y, m) <= (2023, 10):
        out.append(ts(f"{y}-{m:02d}-01"))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out          # 01.11.2022 … 01.10.2023 (последняя — конец)


def factor_panel(R, QV, iB):
    """Индекс альтов как s103: равный вес перпов (без BTC) с оборотом за прошлые 24 шага-часа ≥ 5 млн $,
    лог-доходы обрезаны ±50%."""
    cs = np.cumsum(QV, axis=1)
    v24 = np.zeros_like(cs); v24[:, 24:] = cs[:, 24:] - cs[:, :-24]
    ok = np.zeros(R.shape, bool); ok[:, 1:] = v24[:, :-1] >= 5e6
    ok[iB] = False
    X = np.where(ok & np.isfinite(R), np.clip(R, -0.5, 0.5), np.nan)
    with np.errstate(all="ignore"):
        return np.nanmean(X, axis=0)


def fit_apply(y_fit, X_fit, y_ev, X_ev):
    ok = np.isfinite(y_fit) & np.isfinite(X_fit).all(1)
    if ok.sum() < 200:
        return None
    b, *_ = np.linalg.lstsq(X_fit[ok], y_fit[ok], rcond=None)
    return y_ev - X_ev @ b, b


def blocks(x, h):
    """Суммы по непересекающимся блокам длины h (nan, если в блоке есть пропуск)."""
    n = len(x) // h
    return x[: n * h].reshape(n, h).sum(1)


def acf_parts(x, lags):
    """Суммы для пулированной автокорреляции: Σ x_t x_{t+k} и Σ x_t² по парам без пропусков (среднее ≈ 0)."""
    out = {}
    for k in lags:
        a, b = x[:-k], x[k:]
        ok = np.isfinite(a) & np.isfinite(b)
        out[k] = (np.sum(a[ok] * b[ok]), np.sum(a[ok] ** 2), np.sum(b[ok] ** 2), ok.sum())
    return out


def pastfut(x, k, h, hours=False):
    """Пары (сумма за прошлые k шагов, сумма за следующие h шагов) с началом на каждом шаге (будущие окна
    перекрываются — для наклона это не смещение, но наблюдения зависимы). hours=True — ещё час суток UTC начала
    последнего прошлого шага (ряд начинается с часа 00:00–01:00 UTC)."""
    c = np.concatenate([[0.0], np.nancumsum(np.where(np.isfinite(x), x, 0.0))])
    bad = np.concatenate([[0], np.cumsum(~np.isfinite(x))])
    idx = np.arange(k, len(x) - h + 1)
    past = c[idx] - c[idx - k]; fut = c[idx + h] - c[idx]
    okp = (bad[idx] - bad[idx - k]) == 0; okf = (bad[idx + h] - bad[idx]) == 0
    ok = okp & okf
    if hours:
        return past[ok], fut[ok], ((idx - 1) % 24)[ok]
    return past[ok], fut[ok]


def main():
    t_start = time.time()
    K = load_k(PER)
    P = perps(K)
    SEC = sectors()
    LR = universe(K, P, PER)
    t0, t1 = DESIGN
    MS = month_starts()
    pidx = {p: k for k, p in enumerate(P)}
    iB = pidx["BTC"]
    say(f"s275 — описательные статистики на отрезке замысла {time.strftime('%d.%m.%Y', time.gmtime(t0))}–"
        f"{time.strftime('%d.%m.%Y', time.gmtime(t1))}; перпов {len(P)}; месяцев оценки {len(MS) - 1}")

    # ---------- часовая панель ----------
    T, LC, QV = panel(K, P, t0, t1, H)
    R = np.full(LC.shape, np.nan); R[:, 1:] = LC[:, 1:] - LC[:, :-1]
    alt = factor_panel(R, QV, iB)
    btc = R[iB]

    # накопители
    acc = {}

    def add(key, val):
        acc.setdefault(key, []).append(val)

    acf_sum = {}
    pf_sum = {}
    lag_list = (1, 2, 3, 4, 6, 8, 12, 24)
    KH = [(1, 1), (1, 4), (1, 8), (4, 4), (4, 8), (8, 8), (12, 12), (24, 24)]
    pair_rows = []
    corr_prev = None
    sector_counts = []
    for mi in range(len(MS) - 1):
        a0, a1 = MS[mi], MS[mi + 1]
        f0 = MS[mi - 1] if mi > 0 else ts("2022-10-01")
        ev = (T > a0) & (T <= a1); fit = (T > f0) & (T <= a0)
        U = sorted(LR.get(int(a0 // DAY * DAY), ()))
        U = [p for p in U if p in pidx]
        cover = lambda p, m: np.isfinite(R[pidx[p], m]).mean() >= 0.9  # noqa: E731
        U = [p for p in U if cover(p, ev) and cover(p, fit)]
        liq = {p: QV[pidx[p], fit].sum() for p in U}
        rank = {p: r for r, p in enumerate(sorted(U, key=lambda p: -liq[p]))}
        secU = {}
        for p in U:
            s = SEC.get(p, {}).get("sector", "")
            if s:
                secU.setdefault(s, []).append(p)
        sector_counts.append({s: len(v) for s, v in secU.items()})
        E1 = {}; E2 = {}; RR = {}
        for p in U:
            i = pidx[p]
            if i == iB:
                continue
            y = R[i]
            X = np.column_stack([np.ones(len(y)), btc, alt])
            r1 = fit_apply(y[fit], X[fit], y[ev], X[ev])
            if r1 is None:
                continue
            E1[p] = r1[0]; RR[p] = y[ev]
            s = SEC.get(p, {}).get("sector", "")
            others = [q for q in secU.get(s, []) if q != p and q != "BTC"]
            if len(others) >= 3:
                sx = np.nanmean(np.clip(R[[pidx[q] for q in others]], -0.5, 0.5), axis=0)
                X2 = np.column_stack([X, sx])
                r2 = fit_apply(y[fit], X2[fit], y[ev], X2[ev])
                if r2 is not None:
                    E2[p] = r2[0]
        # доля дисперсии (вне выборки) по горизонтам
        for p in E1:
            bucket = "топ-30" if rank[p] < 30 else "31–100"
            for h in (1, 4, 8, 24):
                rb = blocks(RR[p], h); e1b = blocks(E1[p], h)
                ok = np.isfinite(rb) & np.isfinite(e1b)
                if ok.sum() < 10:
                    continue
                v_r = np.var(rb[ok]); v_1 = np.var(e1b[ok])
                add(("R2_mkt", h, bucket), 1 - v_1 / v_r)
                if p in E2:
                    e2b = blocks(E2[p], h)
                    ok2 = ok & np.isfinite(e2b)
                    if ok2.sum() >= 10:
                        add(("R2_sec_vs_mkt", h, bucket), 1 - np.var(e2b[ok2]) / np.var(e1b[ok2]))
            # автокорреляции и наклоны
            for name, E in (("e1", E1), ("e2", E2), ("r", RR)):
                if p not in E:
                    continue
                for k, v in acf_parts(E[p], lag_list).items():
                    key = (name, bucket, k)
                    s0 = acf_sum.get(key, np.zeros(4)); acf_sum[key] = s0 + np.array(v, float)
                    add(("acf_coin", name, bucket, k), v[0] / np.sqrt(v[1] * v[2]) if v[1] > 0 and v[2] > 0 else np.nan)
                for k, h in KH:
                    x, y = pastfut(E[p], k, h)
                    key = (name, bucket, k, h)
                    s0 = pf_sum.get(key, np.zeros(4))
                    pf_sum[key] = s0 + np.array([np.sum(x * y), np.sum(x * x), np.sum(y * y), len(x)])
                if name == "e1":
                    for k, h in ((1, 1), (1, 4)):
                        x, y, hr = pastfut(E[p], k, h, hours=True)
                        for hh in range(24):
                            m_ = hr == hh
                            key = ("hod", bucket, k, h, hh)
                            s0 = pf_sum.get(key, np.zeros(4))
                            pf_sum[key] = s0 + np.array([np.sum(x[m_] * y[m_]), np.sum(x[m_] ** 2), np.sum(y[m_] ** 2),
                                                         m_.sum()])
            for name, E in (("e1", E1), ("e2", E2)):
                if p not in E:
                    continue
                e = E[p]
                v1 = np.nanvar(e)
                for h in (2, 4, 8, 24):
                    b = blocks(e, h)
                    b = b[np.isfinite(b)]
                    if len(b) > 10 and v1 > 0:
                        add(("VR", name, bucket, h), np.var(b) / (h * v1))
        # корреляции остатков: внутри сектора и между секторами; устойчивость к следующему месяцу
        names = sorted(E1)
        M = np.array([E1[p] for p in names])
        ok = np.isfinite(M).all(0)
        C = np.corrcoef(M[:, ok])
        Mr = np.array([RR[p] for p in names])
        Cr = np.corrcoef(Mr[:, ok])
        iu = np.triu_indices(len(names), 1)
        same = np.array([SEC.get(names[a], {}).get("sector", "") == SEC.get(names[b], {}).get("sector", "") and
                         SEC.get(names[a], {}).get("sector", "") != "" for a, b in zip(*iu)])
        eco_same = np.array([SEC.get(names[a], {}).get("eco", "") == SEC.get(names[b], {}).get("eco", "") and
                             SEC.get(names[a], {}).get("eco", "") not in ("", "Ethereum") for a, b in zip(*iu)])
        add(("corr_e1_same",), np.nanmean(C[iu][same])); add(("corr_e1_diff",), np.nanmean(C[iu][~same]))
        add(("corr_r_same",), np.nanmean(Cr[iu][same])); add(("corr_r_diff",), np.nanmean(Cr[iu][~same]))
        add(("corr_e1_eco",), np.nanmean(C[iu][eco_same]))
        cur = {(names[a], names[b]): C[a, b] for a, b in zip(*iu)}
        if corr_prev is not None:
            common = [k for k in cur if k in corr_prev]
            x = np.array([corr_prev[k] for k in common]); y = np.array([cur[k] for k in common])
            add(("stab_pearson",), np.corrcoef(x, y)[0, 1])
            q90 = np.quantile(x, 0.9); top = x >= q90
            add(("stab_top10_stay",), np.mean(y[top] >= np.quantile(y, 0.9)))
            add(("stab_top10_next_mean",), np.mean(y[top]))
            sm = np.array([SEC.get(a, {}).get("sector", "") == SEC.get(b, {}).get("sector", "") and
                           SEC.get(a, {}).get("sector", "") != "" for a, b in common])
            add(("stab_same_next_mean",), np.mean(y[sm]))
            add(("stab_top10_same_next_mean",), np.mean(y[top & sm]) if (top & sm).any() else np.nan)
            add(("stab_all_next_mean",), np.mean(y))
        corr_prev = cur

        # ---------- пары: коинтеграция (часовые лог-цены) ----------
        cand = []
        for s, mem in secU.items():
            mem = [p for p in mem if p != "BTC"]
            for a_ in range(len(mem)):
                for b_ in range(a_ + 1, len(mem)):
                    cand.append((mem[a_], mem[b_], "сектор"))
        rng = np.random.default_rng(275 + mi)
        allp = [p for p in U if p != "BTC" and SEC.get(p, {}).get("sector", "")]
        nctl = 0
        while nctl < len([c for c in cand if c[2] == "сектор"]):
            a_, b_ = rng.choice(len(allp), 2, replace=False)
            pa, pb = allp[a_], allp[b_]
            if SEC[pa]["sector"] != SEC[pb]["sector"]:
                cand.append((pa, pb, "контроль")); nctl += 1
        # пары с наибольшей корреляцией остатков в месяце модели (топ-1% всех пар вселенной)
        Ef = {}
        for p in names:
            i = pidx[p]
            y = R[i]
            X = np.column_stack([np.ones(len(y)), btc, alt])
            okf = fit & np.isfinite(y) & np.isfinite(alt) & np.isfinite(btc)
            b, *_ = np.linalg.lstsq(X[okf], y[okf], rcond=None)
            Ef[p] = (y - X @ b)[fit]
        Mf = np.array([Ef[p] for p in names]); okc = np.isfinite(Mf).all(0)
        Cf = np.corrcoef(Mf[:, okc])
        vals = Cf[iu]; thr = np.quantile(vals, 0.99)
        for a, b in zip(*iu):
            if Cf[a, b] >= thr:
                cand.append((names[a], names[b], "топ-1% корр."))
        for pa, pb, grp in cand:
            la, lb = LC[pidx[pa]], LC[pidx[pb]]
            okf = fit & np.isfinite(la) & np.isfinite(lb)
            oke = ev & np.isfinite(la) & np.isfinite(lb)
            if okf.sum() < 500 or oke.sum() < 500:
                continue
            best = None
            for y_, x_, tag in ((la, lb, "ab"), (lb, la, "ba")):
                X = np.column_stack([np.ones(okf.sum()), x_[okf]])
                bb, *_ = np.linalg.lstsq(X, y_[okf], rcond=None)
                u = y_[okf] - X @ bb
                tt = adf_t(u)
                if best is None or tt < best[0]:
                    best = (tt, bb, u, y_, x_)
            tt, bb, u, y_, x_ = best
            mu, sd = u.mean(), u.std()
            ue = y_[oke] - bb[0] - bb[1] * x_[oke]
            z = (ue - mu) / sd
            cross = np.sum((np.abs(z[1:]) >= 2) & (np.abs(z[:-1]) < 2))
            pair_rows.append(dict(m=mi, a=pa, b=pb, grp=grp, sec=SEC[pa]["sector"] if grp == "сектор" else "",
                                  adf_f=tt, coint=tt <= -3.34, hl_f=half_life(u), sd_f=sd, beta=bb[1],
                                  adf_e=adf_t(ue), hl_e=half_life(ue), sd_ratio=ue.std() / sd,
                                  mshift=abs(ue.mean() - mu) / sd, cross2=cross, frac2=np.mean(np.abs(z) >= 2),
                                  corr_f=np.corrcoef(np.diff(la[okf]), np.diff(lb[okf]))[0, 1]))
        say(f"  месяц {time.strftime('%Y-%m', time.gmtime(a0))}: вселенная {len(U)}, остатков {len(E1)}, "
            f"с сектором {len(E2)}, пар {len(cand)} ({time.time() - t_start:.0f} с)")

    # ---------- вывод: доля дисперсии ----------
    say("\n## 1. Доля дисперсии часовых доходов, объяснённая вне выборки (модель — прошлый месяц)")
    say("R² рынка = 1 − Var(e1)/Var(r) (BTC + индекс альтов); добавка сектора = 1 − Var(e2)/Var(e1). Медиана по монето-месяцам.")
    for h in (1, 4, 8, 24):
        for bucket in ("топ-30", "31–100"):
            a = np.array(acc.get(("R2_mkt", h, bucket), [np.nan])); b = np.array(acc.get(("R2_sec_vs_mkt", h, bucket), [np.nan]))
            say(f"  {h:2d} ч, {bucket}: R² рынка {np.nanmedian(a):.2f} (n={len(a)}); сектор сверх рынка "
                f"{np.nanmedian(b):+.3f}, среднее {np.nanmean(b):+.3f}, доля > 0 {np.nanmean(b > 0):.2f} (n={len(b)})")

    say("\n## 2. Автокорреляция остатков (пулированная, часовые шаги)")
    for name, title in (("r", "сырые доходы"), ("e1", "остаток рынка e1"), ("e2", "остаток рынка и сектора e2")):
        for bucket in ("топ-30", "31–100"):
            parts = []
            for k in lag_list:
                s = acf_sum.get((name, bucket, k))
                if s is None:
                    continue
                rho = s[0] / np.sqrt(s[1] * s[2]); se = 1 / np.sqrt(s[3])
                med = np.nanmedian(acc.get(("acf_coin", name, bucket, k), [np.nan]))
                parts.append(f"{k}ч {rho:+.3f}" + (f" (мед. {med:+.3f})" if k == 1 else ""))
            say(f"  {title}, {bucket}: " + "; ".join(parts) + f"  [СО ≈ {se:.3f}]")
    say("\n## 3. Отношение дисперсий VR(h) = Var(сумма h ч) / (h·Var(1 ч)) остатков (медиана по монето-месяцам)")
    for name in ("e1", "e2"):
        for bucket in ("топ-30", "31–100"):
            say(f"  {name}, {bucket}: " + "; ".join(
                f"VR({h}) {np.nanmedian(acc.get(('VR', name, bucket, h), [np.nan])):.3f}" for h in (2, 4, 8, 24)))
    say("\n## 4. Наклон «прошлые k ч → следующие h ч» остатков (пулированный по всем часам, b = Σxy/Σx²; корреляция в скобках)")
    say("Амплитуда возврата для хода 2σ_k: b·2σ_k (σ_k — СО прошлой суммы), сравнивать с комиссией пары 0,2% за круг.")
    for name in ("e1", "e2", "r"):
        for bucket in ("топ-30", "31–100"):
            parts = []
            for k, h in KH:
                s = pf_sum.get((name, bucket, k, h))
                if s is None or s[1] <= 0:
                    continue
                b = s[0] / s[1]; rho = s[0] / np.sqrt(s[1] * s[2]); sk = np.sqrt(s[1] / s[3])
                parts.append(f"{k}→{h}: b {b:+.3f} (ρ {rho:+.3f}; 2σ {2 * sk:.2%} → {b * 2 * sk:+.2%})")
            say(f"  {name}, {bucket}: " + "; ".join(parts))

    say("\n## 4а. Остатки e1 по часу суток UTC (начало прошлого часа): наклон 1→1 и 1→4, амплитуда для хода 2σ")
    for bucket in ("топ-30", "31–100"):
        for k, h in ((1, 1), (1, 4)):
            parts = []
            for hh in range(24):
                s_ = pf_sum.get(("hod", bucket, k, h, hh))
                if s_ is None or s_[1] <= 0:
                    continue
                b = s_[0] / s_[1]; sk = np.sqrt(s_[1] / s_[3])
                parts.append(f"{hh:02d}: {b:+.2f}/{b * 2 * sk:+.2%}")
            say(f"  {bucket}, {k}→{h}: " + "; ".join(parts))
    say("\n## 5. Корреляции часовых доходов внутри и между секторами, устойчивость месяц к месяцу")
    for key, title in (("corr_r_same", "сырые, один сектор"), ("corr_r_diff", "сырые, разные сектора"),
                       ("corr_e1_same", "остатки e1, один сектор"), ("corr_e1_diff", "остатки e1, разные сектора"),
                       ("corr_e1_eco", "остатки e1, одна сеть (кроме Ethereum)"),
                       ("stab_pearson", "корреляция попарных корреляций остатков m и m+1"),
                       ("stab_top10_stay", "топ-10% пар месяца m остаются в топ-10% в m+1"),
                       ("stab_top10_next_mean", "корреляция остатков в m+1 у топ-10% пар месяца m"),
                       ("stab_same_next_mean", "… у пар одного сектора"),
                       ("stab_top10_same_next_mean", "… у топ-10% пар одного сектора"),
                       ("stab_all_next_mean", "… у всех пар")):
        v = np.array(acc.get((key,), [np.nan]), float)
        say(f"  {title}: {np.nanmean(v):+.3f} (по месяцам {np.nanmin(v):+.3f}…{np.nanmax(v):+.3f}, n={len(v)})")
    import collections
    agg = collections.Counter()
    for d in sector_counts:
        agg.update(d)
    say("  перпов сектора во вселенной (в среднем за месяц): " +
        ", ".join(f"{s} {n / len(sector_counts):.1f}" for s, n in agg.most_common()))

    import pandas as pd
    D = pd.DataFrame(pair_rows)
    D.to_pickle(f"{TMP}/pairs_design.pkl")
    say("\n## 6. Пары: коинтеграция Энгла–Грейнджера на часовых лог-ценах (30 сут модели → следующий месяц)")
    say("coint — ADF t ≤ −3,34 (5%); HL — полураспад AR(1) в часах; «держится» — ADF t ≤ −3,34 на месяце оценки с β модели;")
    say("σ — СО спреда в месяце модели; «пересечений |z|≥2» — входов z за порог 2 в следующем месяце (z по μ, σ модели).")
    for grp in ("сектор", "контроль", "топ-1% корр."):
        g = D[D.grp == grp]
        if not len(g):
            continue
        c = g[g.coint]
        say(f"  {grp}: пар-месяцев {len(g)}, коинтегрированы {g.coint.mean():.1%}; у них: держится в следующем месяце "
            f"{(c.adf_e <= -3.34).mean():.1%} (у прочих {(g[~g.coint].adf_e <= -3.34).mean():.1%}); HL модели медиана "
            f"{c.hl_f.median():.0f} ч (25–75%: {c.hl_f.quantile(.25):.0f}–{c.hl_f.quantile(.75):.0f}); HL в следующем месяце "
            f"медиана {c.hl_e.median():.0f} ч; σ спреда {c.sd_f.median():.2%}; СО в след. месяце / σ модели "
            f"{c.sd_ratio.median():.2f}; сдвиг среднего {c.mshift.median():.2f}σ; пересечений |z|≥2 в месяц "
            f"{c.cross2.median():.0f} (доля часов |z|≥2 {c.frac2.median():.2f}); корреляция доходов {c.corr_f.median():.2f}")
        say(f"     все пары группы: HL модели медиана {g.hl_f.median():.0f} ч, HL < 8 ч {np.mean(g.hl_f < 8):.1%}, "
            f"8–24 ч {np.mean((g.hl_f >= 8) & (g.hl_f < 24)):.1%}, 24–72 ч {np.mean((g.hl_f >= 24) & (g.hl_f < 72)):.1%}, "
            f"≥ 72 ч или нет возврата {np.mean(~(g.hl_f < 72)):.1%}")
    g = D[D.grp == "сектор"]
    if len(g):
        say("  по секторам (пар-месяцев; доля коинтегрированных; держится; HL медиана, ч):")
        for s, gg in g.groupby("sec"):
            c = gg[gg.coint]
            say(f"    {s:15s} {len(gg):5d}  {gg.coint.mean():6.1%}  {(c.adf_e <= -3.34).mean() if len(c) else np.nan:6.1%}  "
                f"{c.hl_f.median() if len(c) else np.nan:6.0f}")
    open(f"{OUT}/stats_design.txt", "w").write("\n".join(LINES) + "\n")
    print(f"готово за {time.time() - t_start:.0f} с → {OUT}/stats_design.txt")


if __name__ == "__main__":
    main()
