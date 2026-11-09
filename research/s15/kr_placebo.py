"""Плацебо для шорта после корейского листинга: та же монета, тот же шорт на 168 ч без стопа, но в случайный момент
за 30–90 суток до листинга или через 30–90 суток после. Если молодые монеты падают и без листинга, разница будет мала.
Ещё сравнение с рынком: медиана шорта всех фьючерсов за то же окно. Запуск из папки с данными: python3 s15/kr_placebo.py"""
import os
import sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import BAR, K, fut_of, live
from kr_short3 import signals

H = 168
rng = np.random.default_rng(15)


def short_at(s, T):
    t = K[s]["t"]; c = K[s]["c"]
    i = int(np.searchsorted(t, T, side="right")) - 1
    k = i + 4 * H
    if i < 0 or k >= len(t) or t[k] != t[i] + 4 * H * BAR or t[i] < T - BAR:
        return np.nan
    lo_t, hi_t = live(s)
    if t[i] < lo_t + 86400 or t[k] > hi_t:
        return np.nan
    return 1 - float(c[k]) / float(c[i])


if __name__ == "__main__":
    rows = []
    for e in signals():
        s, _ = fut_of(e["base"])
        if s is None or live(s)[0] > e["t"] - 86400:
            continue
        real = short_at(s, e["t"])
        if np.isnan(real):
            continue
        before = [short_at(s, e["t"] - d * 86400) for d in rng.uniform(30, 90, 4)]
        after = [short_at(s, e["t"] + d * 86400) for d in rng.uniform(30, 90, 4)]
        rows.append(dict(t=e["t"], ex=e["ex"], real=real, before=np.nanmean(before) if np.isfinite(before).any() else np.nan,
                         after=np.nanmean(after) if np.isfinite(after).any() else np.nan))
    R = pd.DataFrame(rows)
    print(f"листингов с полными свечами на 168 ч: {len(R)}")
    for col, nm in (("real", "в момент листинга"), ("before", "та же монета, 30–90 сут до"), ("after", "та же монета, 30–90 сут после")):
        x = R[col].dropna()
        print(f"  шорт 168 ч {nm:30s}: n={len(x)}, среднее {x.mean() * 100:+.1f}%, медиана {x.median() * 100:+.1f}%, в плюсе {(x > 0).mean():.0%}")
    both = R.dropna(subset=["before", "after"])
    d = both.real - (both.before + both.after) / 2
    h = both.t < both.t.median()
    se = d.std() / np.sqrt(len(d))
    print(f"  разница «листинг − плацебо той же монеты»: {d.mean() * 100:+.1f}% (t = {d.mean() / se:.1f}), 1-я/2-я половина "
          f"{d[h].mean() * 100:+.1f}/{d[~h].mean() * 100:+.1f}%, Upbit {d[both.ex == 'upbit'].mean() * 100:+.1f}%, Bithumb {d[both.ex == 'bithumb'].mean() * 100:+.1f}%")
