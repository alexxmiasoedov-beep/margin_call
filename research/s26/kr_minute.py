"""s26 — минутные свечи фьючерса Binance вокруг корейских событий (s26/events.pkl): от 3 ч до поста до 22 ч после
(www.binance.com/fapi/v1/klines, 1m, кэш s26/m1/<символ>_<время>.npy: t, o, h, l, c, объём в $). Реакция шорта (простая
доходность 1 − P1/P0) от открытия минуты поста и от входа через 1, 2, 5, 15 мин. Запуск из папки с данными."""
import json
import os
import sys
import time
import urllib.request
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

E = pd.read_pickle("s26/events.pkl")
E = E[E.s.notna() & (E.ts > 1727740800)].sort_values("ts").reset_index(drop=True)   # с 01.10.2024
os.makedirs("s26/m1", exist_ok=True)


def m1(s, ts):
    path = f"s26/m1/{s}_{int(ts)}.npy"
    if os.path.exists(path):
        return np.load(path)
    t0 = (int(ts) // 60 - 180) * 60
    url = f"https://www.binance.com/fapi/v1/klines?symbol={s}USDT&interval=1m&startTime={t0 * 1000}&limit=1500"
    for i in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research)"})
            d = json.loads(urllib.request.urlopen(req, timeout=30).read())
            a = np.array([[r[0] / 1000, float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[7])] for r in d]) \
                if d else np.zeros((0, 6))
            np.save(path, a)
            time.sleep(0.4)
            return a
        except urllib.error.HTTPError as e:
            if e.code == 400:                                   # нет такого символа (делистинг фьючерса)
                np.save(path, np.zeros((0, 6)))
                return np.zeros((0, 6))
            time.sleep(3 + 3 * i)
        except Exception:
            time.sleep(3 + 3 * i)
    return None


if __name__ == "__main__":
    rows = []
    for r in E.itertuples():
        a = m1(r.s, r.ts)
        if a is None or len(a) < 400:
            continue
        t = a[:, 0]; k = int(np.searchsorted(t, r.ts, "right") - 1)      # минута поста
        if k < 120 or k + 900 >= len(a) or t[k] > r.ts:
            continue
        if a[k - 60:k, 5].sum() <= 0 or (a[k:k + 240, 5] > 0).mean() < 0.5:   # фьючерс уже не торгуется: свечи-заглушки
            continue
        o = a[k, 1]
        x = dict(ex=r.ex, kind=r.kind, s=r.s, ts=r.ts, sec=r.ts - t[k])
        x["до 60м"] = 1 - o / a[k - 60, 1]                               # шорт: + если цена до поста падала
        x["до 5м"] = 1 - o / a[k - 5, 1]
        for m in (1, 2, 5, 15, 60, 240):
            x[f"р{m}м"] = 1 - a[k + m - 1, 4] / o                         # от открытия минуты поста до закрытия минуты k+m−1
        for d in (1, 2, 5, 15):
            e = a[k + d - 1, 4]                                          # вход в закрытии минуты k + d − 1 (≈ d мин после поста)
            for m in (60, 240, 900):
                x[f"в{d}→{m}м"] = 1 - a[min(k + d - 1 + m, len(a) - 1), 4] / e
        x["оборот час до, $"] = a[k - 60:k, 5].sum()
        rows.append(x)
    R = pd.DataFrame(rows)
    R.to_pickle("s26/minute.pkl")
    print(f"событий с минутками: {len(R)} из {len(E)}")
    for k in ("촉구", "предупреждение", "делистинг", "снятие"):
        x = R[R.kind == k]
        print(f"\n=== {k}: n={len(x)} (среднее / медиана, %, шорт; секунд от начала минуты до поста — медиана {x.sec.median():.0f})")
        for c in ["до 60м", "до 5м", "р1м", "р2м", "р5м", "р15м", "р60м", "р240м",
                  "в1→60м", "в1→240м", "в1→900м", "в2→240м", "в5→240м", "в15→240м", "в15→900м"]:
            v = x[c].values * 100
            print(f"  {c:9s} {np.nanmean(v):+6.2f} / {np.nanmedian(v):+6.2f}  в плюсе {(v > 0).mean():.0%}")
    for ex in ("upbit", "bithumb"):
        x = R[(R.ex == ex) & R.kind.isin(["предупреждение", "делистинг"])]
        print(f"\n{ex}: предупреждения и делистинги n={len(x)}: до 5м {x['до 5м'].mean()*100:+.2f}%, р1м {x['р1м'].mean()*100:+.2f}%, "
              f"р5м {x['р5м'].mean()*100:+.2f}%, р15м {x['р15м'].mean()*100:+.2f}%")
