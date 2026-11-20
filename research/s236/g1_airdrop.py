"""s236 Г1 — эйрдроп Alpha на монете с живым фьючерсом → шорт фьючерса с листинга в Alpha (метод — ВЫВОДЫ.md, записан
до расчёта). События — s236/events.pkl (E1, фьючерс жив ≥ 1 сут до листинга). Вход — закрытие 15-мин свечи, в которой
лежит время листинга. Сделки — s187/fastbt.trades (шорт 4 ч стоп 10%, 24 ч стоп 25%), хедж индексом альтов
(fastbt.alt_mv), плацебо — тот же час ±7 и ±14 сут. Запуск из /home/user/mc_data:
MC_K=s224/k_d.pkl MC_F=s224/fund_d.pkl python3 <repo>/research/s236/g1_airdrop.py"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s187"))
import fastbt as FB  # noqa: E402

DAY, WEEK, BAR = 86400, 7 * 86400, 900
STABLE = {"USDC", "USD1", "FDUSD", "TUSD", "USDE", "USDP", "DAI", "BUSD", "U", "USDT"}
OUT = {"4 ч": (0.10, 4), "24 ч": (0.25, 24)}


def ct(x, t):
    x = np.asarray(x, float); w = (np.asarray(t, float) // WEEK).astype(np.int64); ok = np.isfinite(x); x, w = x[ok], w[ok]
    if len(x) < 5:
        return (x.mean() if len(x) else np.nan), np.nan, len(x)
    m = x.mean(); s = pd.Series(x - m).groupby(w).sum(); se = np.sqrt((s ** 2).sum()) / len(x)
    return m, (m / se if se > 0 else np.nan), len(x)


def one(s, t_entry, sl, hold):
    """Шорт с входом в закрытии свечи, открытой в t_entry − 900. → (net, hedged) или (nan, nan)."""
    a = FB.K[s]; t = a["t"].astype(np.int64)
    I = int(np.searchsorted(t, t_entry - BAR))
    if I >= len(t) or t[I] != t_entry - BAR:
        return np.nan, np.nan
    ok, net, _, _, tend = FB.trades(s, np.array([I]), sl, hold, -1)
    if not ok[0]:
        return np.nan, np.nan
    hed = net[0] + FB.alt_mv(np.array([t[I] + BAR]), np.array([tend[0]]))[0]
    return net[0], hed


def main():
    E = pd.read_pickle("s236/events.pkl")
    E = E[(E.kind == "E1 эйрдроп Alpha") & E.live & ~E.tick.str.upper().isin(STABLE)].copy()
    E["te"] = (np.floor(E.t / BAR) * BAR + BAR).astype(np.int64)        # закрытие свечи, в которой лежит листинг
    rows = []
    for r in E.itertuples():
        rec = {"tick": r.tick, "fs": r.fs, "t": r.t, "te": r.te}
        for lab, (sl, hold) in OUT.items():
            n, h = one(r.fs, r.te, sl, hold)
            pls = [one(r.fs, r.te + d * DAY, sl, hold)[1] for d in (-14, -7, 7, 14)]
            rec[f"net {lab}"], rec[f"hed {lab}"] = n, h
            rec[f"pl {lab}"] = np.nanmean(pls) if np.isfinite(pls).any() else np.nan
        rows.append(rec)
    R = pd.DataFrame(rows).dropna(subset=["hed 4 ч"]).sort_values("t").reset_index(drop=True)
    R.to_pickle("s236/g1_trades.pkl")
    mid = R.t.median()
    months = (R.t.max() - R.t.min()) / (30.44 * DAY)
    print(f"событий с исходом: {len(R)} ({len(R) / months:.1f} в мес.), {pd.to_datetime(R.t.min(), unit='s'):%d.%m.%Y} – "
          f"{pd.to_datetime(R.t.max(), unit='s'):%d.%m.%Y}; медианная дата {pd.to_datetime(mid, unit='s'):%d.%m.%Y}")
    for lab in OUT:
        h = R[f"hed {lab}"]; n = R[f"net {lab}"]; pl = R[f"pl {lab}"]
        m, t, k = ct(h, R.t); mn, tn, _ = ct(n, R.t); md, td, _ = ct(h - pl, R.t)
        h1, h2 = h[R.t < mid].mean(), h[R.t >= mid].mean()
        print(f"шорт {lab}: с хеджем {m:+.2%} (t {t:+.1f}, n {k}); без хеджа {mn:+.2%} (t {tn:+.1f}); половины "
              f"{h1:+.2%} / {h2:+.2%}; плацебо {pl.mean():+.2%}, сверх плацебо {md:+.2%} (t {td:+.1f}); в плюсе "
              f"{(h > 0).mean():.0%}, медиана {h.median():+.2%}")
    ok = any(ct(R[f"hed {lab}"], R.t)[1] >= 2 and R[f"hed {lab}"][R.t < mid].mean() > 0
             and R[f"hed {lab}"][R.t >= mid].mean() > 0 and (R[f"hed {lab}"] - R[f"pl {lab}"]).mean() > 0 for lab in OUT)
    print("порог изучения:", "пройден" if ok else "не пройден")


if __name__ == "__main__":
    main()
