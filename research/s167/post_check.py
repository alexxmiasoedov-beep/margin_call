"""s167 — вариант s160 «заводы на Binance» после конца периода 2024–2026 (17.10.2026 и позже): события s160_events.pkl,
15-мин свечи фьючерса — дневные архивы data.binance.vision (кэш s167/post). Шорт на закрытии первой 15-мин свечи не раньше чем
через 15 мин после блока, 24 ч, стоп +25% (+0,2% проскальзывания), комиссия 0,1%; фандинг не учтён (в архиве за ноябрь его ещё
нет). Запуск из /home/user/mc_data: python3 <repo>/research/s167/post_check.py"""
import io
import os
import time
import urllib.request
import zipfile

import numpy as np
import pandas as pd

UA = {"User-Agent": "research-script/1.0"}


def day_klines(sym, d):
    path = f"s167/post/{sym}-{d}.csv"
    if not os.path.exists(path):
        u = f"https://data.binance.vision/data/futures/um/daily/klines/{sym}/15m/{sym}-15m-{d}.zip"
        for k in range(4):
            try:
                b = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read()
                open(path, "w").write(zipfile.ZipFile(io.BytesIO(b)).read(zipfile.ZipFile(io.BytesIO(b)).namelist()[0]).decode())
                break
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return None
                time.sleep(3 + 3 * k)
            except Exception:
                time.sleep(3 + 3 * k)
        time.sleep(0.3)
    if not os.path.exists(path):
        return None
    z = pd.read_csv(path, header=None)
    z = z[pd.to_numeric(z[0], errors="coerce").notna()].astype(float)
    return pd.DataFrame({"t": (z[0] // 1000).astype(np.int64), "o": z[1], "h": z[2], "l": z[3], "c": z[4]})


def main():
    E = pd.read_pickle("s160_events.pkl")
    E = E[E.first_all & (E.exch == "Binance") & (E.t >= int(pd.Timestamp("2026-10-17", tz="UTC").timestamp()))]
    rows = []
    for r in E.itertuples():
        sym = r.perp + "USDT"; te = int(-(-(int(r.t) + 900) // 900) * 900)
        days = sorted({pd.Timestamp(x, unit="s").strftime("%Y-%m-%d") for x in (te - 900, te + 86400)})
        parts = [day_klines(sym, d) for d in days]
        if any(p is None for p in parts):
            continue
        k = pd.concat(parts).drop_duplicates("t").sort_values("t").reset_index(drop=True)
        i = np.flatnonzero(k.t.values + 900 == te)
        if not len(i):
            continue
        i = int(i[0]); n = 96
        if i + n >= len(k):
            continue
        p0 = k.c[i]; w = k.iloc[i + 1:i + n + 1]
        hit = np.flatnonzero(w.h.values >= p0 * 1.25)
        if len(hit):
            px = max(p0 * 1.25, w.o.values[hit[0]]) * 1.002; why = "стоп"
        else:
            px = k.c[i + n]; why = "время"
        rows.append(dict(s=r.perp, t=te, frac=r.frac, net=1 - px / p0 - 0.001, why=why))
    X = pd.DataFrame(rows)
    X.to_pickle("s167_post.pkl")
    if len(X):
        g = X.groupby(pd.to_datetime(X.t, unit="s").dt.date).net.mean()
        print(f"событий {len(X)} (из {len(E)}), шорт 24 ч {X.net.mean():+.2%}, медиана {X.net.median():+.2%}, в плюсе {(X.net > 0).mean():.0%}, "
              f"t по дням {g.mean() / (g.std() / np.sqrt(len(g))):+.1f} ({len(g)} дней), стопов {(X.why == 'стоп').mean():.0%}")
        print(X.sort_values("t").assign(d=pd.to_datetime(X.t, unit="s")).loc[:, ["d", "s", "frac", "net"]].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
