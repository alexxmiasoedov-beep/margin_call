"""Окончание вынужденной продажи: дата делистинга спота Binance. Объявления «Binance Will Delist X, Y on ГГГГ-ММ-ДД» (раздел
161, s10/ann.pkl). Фьючерс монеты продолжает торговаться после даты (свечи с объёмом через 14 суток) → доход к рынку
(лонг) от объявления до даты и после даты делистинга (дата 03:00 UTC — обычное время): 1, 3, 7, 14, 30 суток; к фьючерсам
того же возраста. Запуск из папки с данными."""
import pickle
import re
import sys
import numpy as np, pandas as pd
sys.path.insert(0, "/home/user/margin_call/research/s22")
from common22 import CUT, DAY, H, K, ct, fwd, fut_of, live      # noqa: E402
from h10_margin import hour_up, matched                          # noqa: E402

A = pickle.load(open("s10/ann.pkl", "rb"))
rows = []
for a in A.values():
    t = a["title"]; ts = int(a["ts"]) / 1000
    m = re.match(r"^Binance Will Delist (.+?) on (\d{4}-\d{2}-\d{2})", t)
    if not m or ts < 1727740800:
        continue
    day = pd.Timestamp(m.group(2) + " 03:00", tz="UTC").timestamp()
    for c in [x.strip() for x in re.split(r",|&| and ", m.group(1)) if x.strip()]:
        s = c if c in K else fut_of(c)[0]
        if not s:
            continue
        lo, hi = live(s)
        if not (lo <= ts - DAY and hi >= day + 14 * DAY):
            continue
        rows.append(dict(s=s, ann=ts, day=day, gap=(day - ts) / DAY))
E = pd.DataFrame(rows).drop_duplicates(["s", "day"])
print(f"делистингов спота с живым фьючерсом через 14 суток после даты: {len(E)}, монет {E.s.nunique()}, "
      f"от объявления до даты медиана {E.gap.median():.1f} сут")
A0 = [hour_up(x) for x in E.ann]; D0 = [hour_up(x - 1) for x in E.day]
pre = np.array([-fwd(s, T, int(round((d - T) / H))) for s, T, d in zip(E.s, A0, D0)])
m, t, n = ct(pre, np.array(A0))
print(f"  объявление → дата делистинга: лонг к рынку {m * 100:+.2f}% (t {t:+.1f}, n {n})")
for k in (1, 3, 7, 14, 30):
    y = np.array([-fwd(s, T, 24 * k) for s, T in zip(E.s, D0)])
    ya = np.array([-matched(T, s, 24 * k, "age") for s, T in zip(E.s, D0)])
    m, t, n = ct(y, np.array(D0)); ma, ta, na = ct(ya, np.array(D0))
    T = np.array(D0); ok = np.isfinite(y)
    print(f"  после даты {k:2d} сут: лонг к рынку {m * 100:+.2f}% (t {t:+.1f}, n {n}; половины {np.nanmean(y[ok & (T < CUT)]) * 100:+.1f} / "
          f"{np.nanmean(y[ok & (T >= CUT)]) * 100:+.1f}; в плюсе {(y[ok] > 0).mean():.0%}) | к сверстникам {ma * 100:+.2f}% (t {ta:+.1f})")
