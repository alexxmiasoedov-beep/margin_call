"""s277 — внутридневные двойники ⏰ и 🇰🇷 (выход через 8 ч, стоп 10%) по записи ВЫВОДЫ.md (коммит 3bfda8c).

Запуск по периодам — в папке периода (свечи и фандинг периода — s2/k2y.pkl и s2/fund2y.pkl, как s270):
  cd ~/mc_2020 && python3 -I <repo>/research/s277/run.py 2020–2022
  cd ~/mc_oos  && python3 -I <repo>/research/s277/run.py 2022–2024
  cd ~/mc_data && python3 -I <repo>/research/s277/run.py 2024–2026
Сводка трёх периодов: python3 -I <repo>/research/s277/run.py report. Сделки — /home/user/mc_data/s277_<период>.pkl."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
D = "/home/user/mc_data"
SRC = {"2020–2022": dict(o9=f"{D}/s88/oos2020_trades.pkl", pump="/home/user/mc_2020/s118_kr.pkl"),   # доля Кореи 2020–2022 — s118
       "2022–2024": dict(o9=f"{D}/s88/oos_trades.pkl", pump="/home/user/mc_oos/s119_old.pkl"),
       "2024–2026": dict(o9=f"{D}/s88/trades.pkl", pump=f"{D}/s49/trades.pkl", kt=f"{D}/s65/trades.pkl",
                         rt=f"{D}/s83/trades.pkl")}
WIN = {"2020–2022": ("2020-10-01", "2022-10-01"), "2022–2024": ("2022-10-01", "2024-10-01"),
       "2024–2026": ("2024-10-01", "2026-10-19")}
EXITS = (("8 ч", 0.10, 8), ("4 ч", 0.10, 4), ("24 ч", 0.10, 24))
MAIN = {"⏰": "8 ч", "🇰🇷": "8 ч"}
DAY, WEEK, BAR = 86400, 7 * 86400, 900
MONTH = 30.44 * DAY


def ts(s):
    return int(pd.Timestamp(s, tz="UTC").timestamp())


def cooldown(df, sec):
    keep, last = [], {}
    for i, r in enumerate(df.itertuples()):
        if r.t - last.get(r.s, -10 ** 12) >= sec:
            keep.append(i); last[r.s] = r.t
    return df.iloc[keep]


def events(per):
    src = SRC[per]
    out = {}
    X = pd.read_pickle(src["o9"])
    X = X[X.open9.astype(bool) & (X.r1 >= 0.05) & (X.share >= 0.20)][["s", "t"]].copy()
    X["s"] = [v[:-4] if v.endswith("USDT") else v for v in X.s.astype(str)]      # в таблицах s88 за 2020–2024 — «XXXUSDT»
    out["⏰"] = X
    P = pd.read_pickle(src["pump"])[["s", "t", "kr"]].copy()
    P["t"] = P.t.astype(float).astype(np.int64)
    P = P.sort_values("t")
    out["🇰🇷"] = cooldown(P[P.kr >= 0.20], 2 * DAY)[["s", "t"]]
    out["🇰🇷, доля Кореи ≥ 40%"] = cooldown(P[P.kr >= 0.40], 2 * DAY)[["s", "t"]]
    if "kt" in src:
        out["🔝"] = pd.read_pickle(src["kt"])[["s", "t"]].copy()
        out["👀"] = pd.read_pickle(src["rt"])[["s", "t"]].copy()
    for k in out:
        out[k]["t"] = out[k].t.astype(float).astype(np.int64)
    return out


def run(per):
    sys.path.insert(0, os.path.join(HERE, "..", "s187"))
    import fastbt as FB  # noqa: E402  (свечи периода — s2/k2y.pkl в текущей папке)
    t0, t1 = ts(WIN[per][0]), ts(WIN[per][1])
    rows = []
    for name, X in events(per).items():
        X = X[(X.t >= t0) & (X.t < t1)]
        for s, g in X.groupby("s"):
            if s not in FB.K:
                continue
            t = FB.K[s]["t"].astype(np.int64)
            I = np.searchsorted(t, g.t.values - BAR)
            ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == g.t.values - BAR)
            I = I[ok]
            if not len(I):
                continue
            for lab, sl, hold in EXITS:
                okt, net, stp, bars, tend = FB.trades(s, I, sl, hold, -1)
                te = t[I] + BAR
                alt = FB.alt_mv(te, np.where(okt, tend, te))
                pl = FB.placebo(s, I, sl, hold, -1, days=(7, 14, 21))
                for j in range(len(I)):
                    if okt[j]:
                        rows.append(dict(h=name, ex=lab, s=s, te=int(te[j]), net=float(net[j]), stop=bool(stp[j]),
                                         hed=float(net[j] + alt[j]), pl=float(pl[j])))
    R = pd.DataFrame(rows)
    R.to_pickle(f"{D}/s277_{per}.pkl")
    print(per, "сделок", len(R), R[R.ex == "8 ч"].groupby("h").size().to_dict(), flush=True)


def ct(x, t):
    x = np.asarray(x, float); w = (np.asarray(t, np.int64) // WEEK) * WEEK; ok = np.isfinite(x); x, w = x[ok], w[ok]
    if len(x) < 5:
        return np.nan, np.nan, len(x)
    m = x.mean(); s = pd.Series(x - m).groupby(w).sum(); se = np.sqrt((s ** 2).sum()) / len(x)
    return m, (m / se if se > 0 else np.nan), len(x)


def report():
    R = {p: pd.read_pickle(f"{D}/s277_{p}.pkl") for p in WIN if os.path.exists(f"{D}/s277_{p}.pkl")}
    names = ["⏰", "🇰🇷", "🇰🇷, доля Кореи ≥ 40%", "🔝", "👀"]
    for h in names:
        for lab, _, _ in EXITS:
            main = MAIN.get(h) == lab
            print(f"\n### {h} — выход {lab}{'' if main else ' (для отчёта)'}")
            signs, allx = [], []
            for p, X in R.items():
                x = X[(X.h == h) & (X.ex == lab)]
                if len(x) < 5:
                    continue
                mo = (ts(WIN[p][1]) - ts(WIN[p][0])) / MONTH
                m, t, n = ct(x.net, x.te); mh, th, _ = ct(x.hed, x.te); md, td, _ = ct(x.net - x.pl, x.te)
                mid = float(np.median(x.te)); h1, h2 = x[x.te < mid].net.mean(), x[x.te >= mid].net.mean()
                print(f"  {p}: n={n} ({n / mo:.1f} в мес.), {m:+.2%} (t {t:+.1f}); половины {h1:+.2%} / {h2:+.2%}; "
                      f"с хеджем {mh:+.2%} (t {th:+.1f}); сверх плацебо {md:+.2%} (t {td:+.1f}); стопов {x.stop.mean():.0%}")
                signs.append(m > 0); allx.append(x)
                if main and p == "2024–2026":
                    conds = (("≥ 20 в месяц", n / mo >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
                             ("сверх плацебо > 0", md > 0), ("с хеджем > 0", mh > 0))
                    print("    правило владельца: " + "; ".join(f"{k} — {'да' if c else 'нет'}" for k, c in conds)
                          + f" → {'выполнено' if all(c for _, c in conds) else 'не выполнено'}")
            if len(allx) > 1:
                A = pd.concat(allx); m, t, n = ct(A.net, A.te); mh, th, _ = ct(A.hed, A.te)
                ok = all(signs) and t >= 3 and len(allx) == 3
                print(f"  вместе ({len(allx)} пер.): {m:+.2%} (t {t:+.1f}, n={n}); с хеджем {mh:+.2%} (t {th:+.1f}); "
                      f"знак плюс во всех — {'да' if all(signs) else 'нет'} → {'ПОРОГ ПРОЙДЕН' if ok else 'не пройден'}")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
