"""s273 — проверка Г1 и Г2 изучения s271 (правила записаны до расчёта в research/s271/ВЫВОДЫ.md, коммит a083de0):
- Г1 «вынос лонгов на перпе»: час T — перп за час ≤ −5% и OI в монетах ≤ −5%, перп ведёт (премия к индексу на T ≤ −0,3%;
  нет премии — перп упал сильнее спота Binance на ≥ 1 п. п.), перп ≥ 7 сут, первое у монеты за 24 ч → лонг на T, 2 ч,
  стоп −8%. Для отчёта: без условия «ведёт перп» (и на 2022–2024 гг.), порог −3%, вход T + 15 мин, выход 1 и 4 ч, зеркало.
- Г2 «внезапный дисконт перпа к споту»: на отметке часа перп / спот Binance − 1 ≤ −1%, медиана |разрыва| за 4 прошлых
  часа ≤ 0,3%, оборот спота за час ≥ 50 тыс. $, перп ≥ 7 сут, первое за 24 ч → лонг 1 ч, стоп −5%. Для отчёта: 15 мин и
  4 ч, зеркало (премия ≥ +1% → шорт).
Сделки — s187/fastbt (комиссия 0,1%, стоп + 0,2%, фактический фандинг); хедж — индекс альтов; плацебо — та же монета
в тот же час 7/14/21 сут раньше; t по неделям.
Запуск из /home/user/mc_data: python3 -I <repo>/research/s273/run.py 2024–2026 | 2022–2024"""
import os
import pickle
import sys

PER = sys.argv[1]
CFG = {"2024–2026": ("s224/k_d.pkl", "s224/fund_d.pkl"), "2022–2024": ("s117/k_oos.pkl", "s117/fund_oos.pkl")}
os.environ["MC_K"], os.environ["MC_F"] = CFG[PER]
HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s187", os.path.join("s271", "study")):
    sys.path.insert(0, os.path.join(HERE, "..", p))
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import fastbt as FB  # noqa: E402
import freq_flush as FF  # noqa: E402
from common271 import PER as P271, cooldown, live_idx, hourly_close, base, crypto_perps  # noqa: E402

DAY, WEEK, BAR, H = 86400, 7 * 86400, 900, 3600
T0, T1, MID = P271[PER]["t0"], P271[PER]["t1"], P271[PER]["mid"]
MONTH = 30.44 * DAY


def trades(ev, side, sl, hold, shift=0, tag=""):
    """ev — {перп: массив T}; вход на закрытии 15-мин свечи, кончающейся в T (+ shift свечей)."""
    rows = []
    for p, Ts in ev.items():
        if p not in FB.K or not len(Ts):
            continue
        t = FB.K[p]["t"].astype(np.int64)
        I = np.searchsorted(t, Ts - BAR)
        ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == Ts - BAR)
        I, Tt = I[ok] + shift, Ts[ok]
        if not len(I):
            continue
        okt, net, stp, bars, tend = FB.trades(p, I, sl, hold, side)
        te = t[I] + BAR
        alt = FB.alt_mv(te, np.where(okt, tend, te))
        pl = FB.placebo(p, I, sl, hold, side, days=(7, 14, 21))
        for j in range(len(I)):
            if okt[j]:
                rows.append(dict(s=p, te=int(te[j]), net=float(net[j]), stop=bool(stp[j]), hed=float(net[j] - side * alt[j]),
                                 pl=float(pl[j]), tag=tag))
    return pd.DataFrame(rows)


def ct(x, t):
    x = np.asarray(x, float); w = (np.asarray(t, np.int64) // WEEK) * WEEK; ok = np.isfinite(x); x, w = x[ok], w[ok]
    if len(x) < 5:
        return np.nan, np.nan, len(x)
    m = x.mean(); s = pd.Series(x - m).groupby(w).sum(); se = np.sqrt((s ** 2).sum()) / len(x)
    return m, (m / se if se > 0 else np.nan), len(x)


def line(name, X, verdict=False):
    X = X[(X.te >= T0) & (X.te < T1)] if len(X) else X
    if len(X) < 5:
        print(f"{name}: n={len(X)}"); return
    m, t, n = ct(X.net, X.te); mh, th, _ = ct(X.hed, X.te); md, td, _ = ct(X.net - X.pl, X.te)
    mid = float(np.median(X.te)); h1, h2 = X[X.te < mid].net.mean(), X[X.te >= mid].net.mean()
    mo = (T1 - T0) / MONTH
    print(f"{name}: n={n} ({n / mo:.1f} в мес.), {m:+.2%} (t по неделям {t:+.1f}); половины {h1:+.2%} / {h2:+.2%}; "
          f"с хеджем {mh:+.2%} (t {th:+.1f}); сверх плацебо {md:+.2%} (t {td:+.1f}); стопов {X.stop.mean():.0%}")
    if verdict:
        conds = (("≥ 20 в месяц", n / mo >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
                 ("сверх плацебо > 0", md > 0), ("с хеджем > 0", mh > 0))
        print("   порог: " + "; ".join(f"{k} — {'да' if c else 'нет'}" for k, c in conds)
              + f" → {'ПРОЙДЕН' if all(c for _, c in conds) else 'не пройден'}")


def flush_events(rows, side, X, Y, lead):
    out = {}
    for p, Ts, dp, doi, prem, ds, hs in rows:
        m = (side * dp >= X) & (doi <= -Y)
        if lead:
            m &= np.where(np.isfinite(prem), side * prem >= 0.003, np.isfinite(ds) & (side * (dp - ds) >= 0.01))
        if m.any():
            Tm = Ts[m]
            out[p] = Tm[cooldown(Tm, DAY)]
    return out


def gap_events(side, thr):
    """Г2: разрыв перп–спот Binance на отметке часа (код freq_gap.py s271, порог и сторона — параметры)."""
    SP = pickle.load(open("s23/spot1h.pkl", "rb"))
    out = {}
    for p in crypto_perps(FB.K):
        sp = SP.get(p) if p in SP else SP.get(base(p))
        if sp is None or not len(sp):
            continue
        i0, _ = live_idx(FB.K[p])
        if i0 is None:
            continue
        t_live = int(FB.K[p]["t"][i0])
        T, px, _ = hourly_close(FB.K[p])
        st = sp[:, 0].astype(np.int64) + H
        k = np.searchsorted(st, T); k2 = np.minimum(k, len(st) - 1)
        hit = (k < len(st)) & (st[k2] == T)
        T, px, k2 = T[hit], px[hit], k2[hit]
        sc = sp[k2, 4].astype(float); sv = sp[k2, 1].astype(float)
        ok = (sc > 0) & (px > 0) & (sv >= 5e4) & (T - t_live >= 7 * DAY)
        if not ok.any():
            continue
        mult = 10.0 ** np.round(np.log10(np.nanmedian(px[ok] / sc[ok])))
        g = np.where(ok, px / (sc * mult) - 1, np.nan)
        med = np.full(len(g), np.nan)
        if len(g) > 4:
            w = np.lib.stride_tricks.sliding_window_view(np.abs(g), 4)[:-1]
            med[4:] = np.nanmedian(w, axis=1)
        m = ok & (med <= 0.003) & (side * g >= thr)
        if m.any():
            Tm = T[m]
            out[p] = Tm[cooldown(Tm, DAY)]
    return out


def main():
    cache = f"/dev/shm/s273/flush_{PER}.pkl"
    os.makedirs("/dev/shm/s273", exist_ok=True)
    if os.path.exists(cache):
        rows = pickle.load(open(cache, "rb"))
    else:
        rows = FF.panel(PER)
        pickle.dump(rows, open(cache, "wb"))
    print(f"== {PER}: монет с метриками {len(rows)}")
    if PER == "2024–2026":
        ev = flush_events(rows, -1, 0.05, 0.05, True)
        A = trades(ev, 1, 0.08, 2)
        line("Г1 вынос лонгов с дисконтом перпа → лонг 2 ч, стоп 8% (основная)", A, verdict=True)
        line("  вход T + 15 мин", trades(ev, 1, 0.08, 2, shift=1))
        line("  выход 1 ч", trades(ev, 1, 0.08, 1))
        line("  выход 4 ч", trades(ev, 1, 0.08, 4))
        line("  порог −3% / OI −5%", trades(flush_events(rows, -1, 0.03, 0.05, True), 1, 0.08, 2))
        line("  зеркало: вынос шортов, который ведёт перп → шорт 2 ч", trades(flush_events(rows, 1, 0.05, 0.05, True), -1, 0.08, 2))
    line("Г1 без условия «ведёт перп» (цена −5%, OI −5%) → лонг 2 ч", trades(flush_events(rows, -1, 0.05, 0.05, False), 1, 0.08, 2))
    if PER == "2024–2026":
        gev = gap_events(-1, 0.01)
        G = trades(gev, 1, 0.05, 1)
        line("\nГ2 внезапный дисконт перпа к споту ≥ 1% → лонг 1 ч, стоп 5% (основная)", G, verdict=True)
        line("  выход 15 мин", trades(gev, 1, 0.05, 0.25))
        line("  выход 4 ч", trades(gev, 1, 0.05, 4))
        line("  вход через 15 мин", trades(gev, 1, 0.05, 1, shift=1))
        line("  зеркало: внезапная премия ≥ 1% → шорт 1 ч", trades(gap_events(1, 0.01), -1, 0.05, 1))
        pd.concat([A.assign(h="Г1"), G.assign(h="Г2")]).to_pickle("s273_trades.pkl")


if __name__ == "__main__":
    main()
