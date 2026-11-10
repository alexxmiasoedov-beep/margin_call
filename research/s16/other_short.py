"""Шорт фьючерса Binance после листинга на Coinone (к воне) и Coinbase (к доллару) — то же правило, что у журнала 🇰🇷🆕
(research/s15): фьючерс торгуется ≥ суток, 7 суток без тейка, стоп +50%; для сравнения 48 ч / стоп 25%. Каждый листинг —
отдельный сигнал, пропуск, если по монете уже открыта сделка этой биржи. Отдельно — листинги без корейского (Upbit/Bithumb)
в пределах ±7 суток: только они добавили бы журналу новые сделки. Плацебо — та же монета в случайный момент за 30–90 суток
до или после листинга (шорт 168 ч без стопа).
Запуск из папки с данными: python3 s16/other_short.py (нужны s16/listings_other.pkl, s15/kr_listings.pkl)."""
import os
import pickle
import sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s15"))
from common import BAR, K, fut_of, live, trade

O = pickle.load(open("s16/listings_other.pkl", "rb"))
KR = pickle.load(open("s15/kr_listings.pkl", "rb"))
KRT = {}
for x in KR:
    KRT.setdefault(x["base"], []).append(x["t"])
rng = np.random.default_rng(16)


def entry_bar(s, T, min_age_d=1):
    a = K[s]; t = a["t"]; lo, hi = live(s)
    if lo > T - min_age_d * 86400:
        return None
    j = int(np.searchsorted(t, T, side="right")) - 1
    return j if j >= 8 and t[j] >= T - BAR else None


def journal(ev, hold_h=168, sl=0.5):
    rows, busy = [], {}
    for e in sorted(ev, key=lambda x: x["t"]):
        s, _ = fut_of(e["base"])
        if s is None or busy.get((e["ex"], s), -1) > e["t"]:
            continue
        j = entry_bar(s, e["t"])
        if j is None:
            continue
        r = trade(s, j, sl=sl, hold_h=hold_h)
        if r is None:
            continue
        busy[(e["ex"], s)] = float(K[s]["t"][j + r["bars"]]) + BAR
        kr = [t for t in KRT.get(e["base"], []) if abs(t - e["t"]) <= 7 * 86400]
        rows.append(dict(r, t=e["t"], ex=e["ex"], base=e["base"], sym=s, kr_near=bool(kr)))
    return pd.DataFrame(rows)


def short_at(s, T, H=168):
    t = K[s]["t"]; c = K[s]["c"]; lo, hi = live(s)
    i = int(np.searchsorted(t, T, side="right")) - 1; k = i + 4 * H
    if i < 0 or k >= len(t) or t[k] != t[i] + 4 * H * BAR or t[i] < max(T - BAR, lo + 86400) or t[k] > hi:
        return np.nan
    return 1 - float(c[k]) / float(c[i])


def stats(r):
    if not len(r):
        return "нет сделок"
    h = r.t < r.t.median()
    trim = r.net.sort_values().iloc[:-5].mean() if len(r) > 15 else np.nan
    return (f"n={len(r):3d} | {r.net.mean() * 100:+5.1f}% на сделку (медиана {r.net.median() * 100:+5.1f}%, без 5 лучших {trim * 100:+5.1f}%) | "
            f"в плюсе {(r.net > 0).mean():3.0%} | стопов {(r.why == 'стоп').mean():3.0%} | 1-я/2-я половина {r.net[h].mean() * 100:+5.1f}/{r.net[~h].mean() * 100:+5.1f}%")


if __name__ == "__main__":
    for ex in ("coinone", "coinbase"):
        ev = [x for x in O if x["ex"] == ex]
        print(f"\n===== {ex}: листингов после 01.10.2024 — {len(ev)}")
        for nm, kw in (("168 ч, стоп 50% (как 🇰🇷🆕)", dict()), ("48 ч, стоп 25%", dict(hold_h=48, sl=0.25))):
            r = journal(ev, **kw)
            if not len(r):
                print(f"  {nm}: нет сделок"); continue
            print(f"  {nm:28s} все:                     {stats(r)}")
            print(f"  {'':28s} Upbit/Bithumb рядом (±7 сут): {stats(r[r.kr_near])}")
            print(f"  {'':28s} без корейского листинга:  {stats(r[~r.kr_near])}")
            if kw == {}:
                q = r.groupby(pd.to_datetime(r.t, unit="s").dt.to_period("Q")).net.agg(["size", "mean"])
                print("  по кварталам: " + ", ".join(f"{k} {v['mean'] * 100:+.1f}% ({int(v['size'])})" for k, v in q.iterrows()))
        rows = []
        for e in ev:
            s, _ = fut_of(e["base"])
            if s is None or entry_bar(s, e["t"]) is None:
                continue
            real = short_at(s, e["t"])
            pl = [short_at(s, e["t"] + sg * d * 86400) for sg in (-1, 1) for d in rng.uniform(30, 90, 2)]
            if np.isfinite(real) and np.isfinite(pl).any():
                rows.append(dict(t=e["t"], real=real, pl=np.nanmean(pl), kr=any(abs(t - e["t"]) <= 7 * 86400 for t in KRT.get(e["base"], []))))
        R = pd.DataFrame(rows)
        if len(R):
            d = R.real - R.pl; se = d.std() / np.sqrt(len(d)); h = R.t < R.t.median()
            dn = d[~R.kr]
            print(f"  плацебо (шорт 168 ч без стопа): листинг {R.real.mean() * 100:+.1f}%, та же монета в другой момент {R.pl.mean() * 100:+.1f}%, "
                  f"разница {d.mean() * 100:+.1f}% (t = {d.mean() / se:.1f}, n = {len(d)}), по половинам {d[h].mean() * 100:+.1f}/{d[~h].mean() * 100:+.1f}%; "
                  f"без корейского листинга рядом {dn.mean() * 100:+.1f}% (n = {len(dn)})")
