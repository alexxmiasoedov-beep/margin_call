"""s190 Г1 — «займ пошёл» (гипотеза — ВЫВОДЫ.md, записана до расчёта). Часовая ставка займа маржи Binance:
01.2023–09.2024 — /home/user/mc_data/s190/rates (rates_fetch.py), с 09.2024 — s11/rates. x = ставка / 10-й перцентиль
ставки за прошлые 30 сут; событие — x ≥ 1,5 впервые после ≥ 7 сут с x < 1,2; f7 — сумма фандинга перпа за 7 сут до
события; f7 ≥ 0 — событие, f7 ≤ −0,3% — контроль (а); фьючерс старше 30 сут; одна сделка на монету за 7 сут (по виду).
Шорт с закрытия 15-мин свечи, начинающейся в час ставки, 7 сут, стоп 50%; хедж — индекс альтов s103; плацебо 45/90/135.
Запуск из /home/user/mc_data: [MC_K=… MC_F=…] python3 <repo>/research/s190/g1.py <2022–2024|2024–2026>;
сводка: … g1.py report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s187"))
sys.path.insert(0, os.path.join(HERE, "..", "s182"))

DAY, H, OUT = 86400, 3600, "/home/user/mc_data"
SUB = {"03.2023–09.2024": ("2023-03-01", "2024-10-01"), "10.2024–09.2025": ("2024-10-01", "2025-10-01"),
       "10.2025–10.2026": ("2025-10-01", "2026-10-19")}


def rates(asset):
    parts = []
    for fn in (f"{OUT}/s190/rates/{asset}.csv", f"{OUT}/s11/rates/{asset}.csv"):
        if os.path.exists(fn) and os.path.getsize(fn) > 0:
            d = pd.read_csv(fn, header=None, names=["t", "r"])
            parts.append(d)
    if not parts:
        return None
    d = pd.concat(parts).drop_duplicates("t").sort_values("t")
    s = pd.Series(d.r.values, index=pd.to_datetime(d.t.values, unit="s", utc=True))
    s = s[~s.index.duplicated()].resample("1h").last().ffill(limit=6)
    return s


MODE = os.environ.get("G1_MODE", "daily")         # основной — суточный ряд (уточнение до расчёта), hourly — для отчёта


def events(asset):
    s = rates(asset)
    if s is None or len(s) < 24 * 40:
        return []
    if MODE == "daily":
        d = s.resample("1D").last()
        fl = d.rolling(30, min_periods=20).quantile(0.10).shift(1)
        x = d / fl.where(fl > 0)
        low = (x < 1.2).astype(float).where(x.notna())
        calm = low.rolling(7, min_periods=7).min().shift(1) == 1          # прошлые 7 сут все x < 1,2
        hit = (x >= 1.5) & calm
        return [int(t.timestamp()) + DAY for t in x.index[hit.fillna(False).values]]   # вход в начале следующих суток
    fl = s.rolling("30D", min_periods=24 * 20).quantile(0.10).shift(1)
    x = s / fl.where(fl > 0)
    low = (x < 1.2).astype(float).where(x.notna())
    calm = low.rolling(168, min_periods=168).min().shift(1) == 1          # прошлые 7 сут все x < 1,2
    hit = (x >= 1.5) & calm
    return [int(t.timestamp()) for t in x.index[hit.fillna(False).values]]


def run(per):
    import fastbt as FB  # noqa: E402
    from common import fut_of, funding  # noqa: E402
    import common182 as C  # noqa: E402
    K = FB.K
    t0, t1 = C.ts(C.PER[per][0]), C.ts(C.PER[per][1])
    assets = sorted({f[:-4] for f in os.listdir(f"{OUT}/s11/rates")} |
                    {f[:-4] for f in os.listdir(f"{OUT}/s190/rates") if f.endswith(".csv")})
    rows = []
    for a in assets:
        sym, _ = fut_of(a)
        if sym is None or sym not in K:
            continue
        ev = [t for t in events(a) if t0 <= t < t1]
        if not ev:
            continue
        lo, hi = FB.live(sym)
        fr = funding(sym)
        ft = fr[:, 0].astype(np.int64) if len(fr) else np.zeros(0, np.int64)
        cs = np.r_[0.0, np.cumsum(fr[:, 1])] if len(fr) else np.zeros(1)
        T = np.array(ev, np.int64)
        f7 = cs[np.searchsorted(ft, T, "right")] - cs[np.searchsorted(ft, T - 7 * DAY, "right")] if len(ft) else np.zeros(len(T))
        kind = np.where(f7 >= 0, "event", np.where(f7 <= -0.003, "ctl", ""))
        keep, last = [], {}
        for k_, (t, kd) in enumerate(zip(T, kind)):
            if not kd or t < lo + 30 * DAY or t - last.get(kd, -10 ** 12) < 7 * DAY:
                continue
            keep.append(k_); last[kd] = t
        if not keep:
            continue
        T, kind, f7 = T[keep], kind[keep], f7[keep]
        t = K[sym]["t"].astype(np.int64)
        I = np.searchsorted(t, T)
        ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == T) & (I >= 96)
        if not ok.any():
            continue
        T, kind, f7, I = T[ok], kind[ok], f7[ok], I[ok]
        okt, net, stp, bars, tend = FB.trades(sym, I, 0.50, 168, -1)
        mv = FB.alt_mv(t[I] + 900, tend)
        pl = FB.placebo(sym, I, 0.50, 168, -1)
        for j in range(len(T)):
            if okt[j]:
                rows.append(dict(a=a, s=sym, t=int(T[j]), kind=kind[j], f7=f7[j], net=net[j], stop=bool(stp[j]),
                                 hed=net[j] + mv[j], pl=pl[j]))
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/s190_g1_{per}{'' if MODE == 'daily' else '_h'}.pkl")
    print(per, X.groupby("kind").size().to_dict() if len(X) else 0, flush=True)


def report():
    import common182 as C  # noqa: E402
    X = pd.concat([pd.read_pickle(f"{OUT}/s190_g1_{p}{'' if MODE == 'daily' else '_h'}.pkl") for p in ("2022–2024", "2024–2026")], ignore_index=True)
    X["why"] = np.where(X.stop, "стоп", "время")
    print("Г1 — «займ пошёл»: ставка займа Binance x ≥ 1,5 после 7 сут у пола, f7 ≥ 0 → шорт 7 сут, стоп 50%;"
          " контроль (а) — то же при f7 ≤ −0,3%\n")
    parts = []
    for name, (a, b) in SUB.items():
        x = X[(X.t >= C.ts(a)) & (X.t < C.ts(b))]
        e, c = x[x.kind == "event"], x[x.kind == "ctl"]
        mo = (C.ts(b) - C.ts(a)) / (30.4 * DAY)
        m, t, n = C.ct(e.net, e.t); mh, th, _ = C.ct(e.hed, e.t); mp, tp, _ = C.ct(e.net - e.pl, e.t)
        d, se = C.diff(x.net, x.kind == "event", x.t) if len(c) >= 10 else (np.nan, np.nan)
        parts.append((d, se, len(e)))
        print(f"{name}: событие n={n} ({n / mo:.1f}/мес) {m:+.2%} (t {t:+.1f}) | с хеджем {mh:+.2%} (t {th:+.1f}) | "
              f"сверх плацебо {mp:+.2%} (t {tp:+.1f}) | стопов {e.stop.mean():.0%}")
        print(f"   контроль (а) n={len(c)} {c.net.mean():+.2%} | Δ {d:+.2%} (t {d / se:+.1f})")
    m, t = C.combine([p for p in parts if np.isfinite(p[0])])
    print(f"\nвместе Δ = {m:+.2%} (t {t:+.1f})")
    e = X[(X.kind == "event") & (X.t >= C.ts("2024-10-01"))]
    cut = C.ts("2025-12-01")
    m, t, n = C.ct(e.net, e.t)
    print(f"\nправило владельца, 10.2024–10.2026: n={n} ({n / C.months('2024–2026'):.1f}/мес) {m:+.2%} (t {t:+.1f}), "
          f"половины {e[e.t < cut].net.mean():+.2%} / {e[e.t >= cut].net.mean():+.2%}, сверх плацебо {(e.net - e.pl).mean():+.2%}")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
