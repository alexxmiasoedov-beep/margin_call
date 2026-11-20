"""s221 — 🐋 на токенах Solana (гипотеза — ВЫВОДЫ.md, записана до расчёта, коммит 76405df). События — s220/events/<фьючерс>_all.json
(сметания на Binance 1, подписанные плательщиком 5JPA…), монеты в обращении — s220/sol_circ.json. Правило сделки — как у 🐋
(s213/run.py): вход на закрытии первой 15-мин свечи не раньше чем через 15 мин после блока, ход фьючерса за 24 ч ±5%,
фьючерс старше суток, шорт 24 ч, стоп 25%. Запуск из /home/user/mc_data: python3 <repo>/research/s221/run.py"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s187", "s182", "s213"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
DAY, WEEK = 86400, 7 * 86400
GAP, BIG, CALM = 48 * 3600, 0.005, 0.05
T0 = pd.Timestamp("2024-10-01", tz="UTC").timestamp()
MID = pd.Timestamp("2025-10-01", tz="UTC").timestamp()


def events():
    C = json.load(open("s220/sol_circ.json"))
    rows = []
    for p in glob.glob("s220/events/*_all.json"):
        E = json.load(open(p)); fs = E["fs"]
        days = {d: c for d, c, _ in C[fs]["days"]}
        dd = sorted(days)
        for t, amt, dep, sig in E["events"]:
            d = pd.Timestamp(int(t) - DAY, unit="s").strftime("%Y-%m-%d")
            i = int(np.searchsorted(dd, d, "right")) - 1
            circ = days[dd[i]] if i >= 0 else np.nan
            rows.append((fs, int(t), float(amt), amt / circ if circ else np.nan, dep, sig))
    X = pd.DataFrame(rows, columns=["perp", "t", "amt", "frac", "dep", "sig"]).sort_values(["perp", "t"])
    X = X[(X.frac >= BIG) & (X.t >= T0)]
    out = []
    for perp, g in X.groupby("perp"):
        last = -10 ** 12
        for r in g.itertuples():
            if r.t - last >= GAP:
                out.append(r); last = r.t
    return pd.DataFrame(out)


def wk(t):
    return (np.asarray(t, np.int64) // WEEK) * WEEK


def ct(x, t):
    x = np.asarray(x, float); w = wk(t); ok = np.isfinite(x); x, w = x[ok], w[ok]
    if len(x) < 5:
        return np.nan, np.nan, len(x)
    m = x.mean(); s = pd.Series(x - m).groupby(w).sum(); se = np.sqrt((s ** 2).sum()) / len(x)
    return m, m / se if se > 0 else np.nan, len(x)


def trades(E):
    import fastbt as FB  # noqa: E402
    from run import mult  # noqa: E402  (s213)
    E = E.assign(entry=(np.ceil((E.t + 900) / 900) * 900).astype(np.int64))
    res = []
    for s, g in E.groupby("perp"):
        if s not in FB.K:
            continue
        t = FB.K[s]["t"].astype(np.int64); c = FB.K[s]["c"].astype(float); qv = FB.K[s]["qv"].astype(float)
        lo, _ = FB.live(s)
        g = g.sort_values("entry").copy()
        st = g.entry.values - 900
        I = np.searchsorted(t, st)
        ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == st) & (I >= 96)
        ok &= t[np.minimum(I, len(t) - 1)] >= lo + DAY
        g, I = g[ok].copy(), I[ok]
        if not len(g):
            continue
        g["r24"] = c[I] / c[I - 96] - 1
        cs = np.r_[0.0, np.cumsum(qv)]
        vbar = np.where(I >= 672, (cs[I] - cs[np.maximum(I - 672, 0)]) / 7.0, np.nan)
        g["lam"] = g.amt.values * c[I] / mult(s) / np.where(vbar > 0, vbar, np.nan)
        okt, net, stp, bars, tend = FB.trades(s, I, 0.25, 24, -1)
        g["net"] = np.where(okt, net, np.nan); g["stop"] = np.where(okt, stp, False)
        g["hed"] = g.net.values + FB.alt_mv(t[I] + 900, tend)
        g["pl"] = FB.placebo(s, I, 0.25, 24, -1)
        res.append(g)
    return pd.concat(res, ignore_index=True)


def line(x, months):
    m, t, n = ct(x.net, x.entry); mh, th, _ = ct(x.hed, x.entry); md, td, _ = ct(x.net - x.pl, x.entry)
    h1, h2 = x[x.entry < MID].net.mean(), x[x.entry >= MID].net.mean()
    return (f"n={n} ({n / months:.1f} в месяц), {m:+.2%} (t по неделям {t:+.1f}); половины {h1:+.2%} / {h2:+.2%}; "
            f"с хеджем {mh:+.2%} (t {th:+.1f}); сверх плацебо {md:+.2%} (t {td:+.1f}); стопов {x.stop.mean():.0%}")


def main():
    E = events()
    print("событий ≥ 0,5% обращения (первые за 48 ч):", len(E), "монет", E.perp.nunique() if len(E) else 0)
    R = trades(E)
    R.to_pickle("s221_trades.pkl")
    months = (pd.Timestamp("2026-10-19", tz="UTC").timestamp() - T0) / (30.44 * DAY)
    x = R[R.net.notna() & (R.r24.abs() <= CALM)]
    print(f"\n🐋 Solana (спокойный рынок ±5%): {line(x, months)}")
    print(f"все события без фильтра рынка: {line(R[R.net.notna()], months)}")
    print(f"🐋ᵛ Solana (λ ≥ 0,05): {line(x[x.lam >= 0.05], months)}")
    m, t, n = ct(x.net, x.entry); mh, _, _ = ct(x.hed, x.entry); md = (x.net - x.pl).mean()
    print("\nпорог s221: " + "; ".join(f"{k} — {'да' if ok else 'нет'}" for k, ok in
                                      (("среднее > 0 и t ≥ 2", m > 0 and t >= 2), ("с хеджем > 0", mh > 0), ("сверх плацебо > 0", md > 0))))
    # вместе с 🐋 Ethereum (s213: события 🐋 на 2024–2026 гг. по правилу бота)
    W = pd.read_pickle("s213_main_2024–2026.pkl")
    W = W[W.net.notna() & (W.r24.abs() <= CALM)][["perp", "entry", "net", "hed", "pl", "stop", "lam"]]
    A = pd.concat([W.assign(net_src="eth"), x[["perp", "entry", "net", "hed", "pl", "stop", "lam"]].assign(net_src="sol")])
    print(f"🐋 Ethereum + Solana вместе: {line(A, months)}")


if __name__ == "__main__":
    main()
