"""s26 — независимая проверка на старых событиях Bithumb (01.2022–09.2024, до начала архива s2/k2y.pkl): шорт фьючерса
Binance USDT-M после предупреждения, делистинга и призыва к осторожности. Свечи 15 мин и фандинг — месячные архивы
data.binance.vision (кэш s26/old/), фьючерс — <ТИКЕР>USDT или 1000<ТИКЕР>USDT, если в месяц события он торговался.
Вход в закрытии 15-мин свечи поста, срок 7 / 14 / 30 сут, без стопа и со стопом +50%, комиссия 0,1%, фактический фандинг;
хедж — лонг BTC той же суммы. Запуск из папки с данными."""
import io
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile
import numpy as np, pandas as pd

BAR, FEE, DAY = 900, 0.001, 86400
OLD = "s26/old"
os.makedirs(OLD, exist_ok=True)


def month_list(ts, before=1, after=2):
    d = pd.Timestamp(ts, unit="s")
    m0 = pd.Period(d, "M")
    return [str(m0 + k) for k in range(-before, after + 1)]


def fetch(kind, sym, m):
    """kind: klines | fundingRate. Массив или None (нет файла)."""
    path = f"{OLD}/{sym}-{kind}-{m}.npy"
    if os.path.exists(path):
        a = np.load(path)
        return a if len(a) else None
    if kind == "klines":
        url = f"https://data.binance.vision/data/futures/um/monthly/klines/{sym}/15m/{sym}-15m-{m}.zip"
    else:
        url = f"https://data.binance.vision/data/futures/um/monthly/fundingRate/{sym}/{sym}-fundingRate-{m}.zip"
    for i in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                z = zipfile.ZipFile(io.BytesIO(r.read()))
            rows = []
            for ln in z.read(z.namelist()[0]).decode().splitlines():
                p = ln.split(",")
                if not p[0].isdigit():
                    continue
                if kind == "klines":                                 # t, o, h, l, c, оборот $
                    rows.append((int(p[0]) // 1000, float(p[1]), float(p[2]), float(p[3]), float(p[4]), float(p[7])))
                else:                                                # t, ставка
                    rows.append((int(p[0]) // 1000, float(p[2])))
            a = np.array(rows, float)
            np.save(path, a)
            time.sleep(0.2)
            return a
        except urllib.error.HTTPError as e:
            if e.code == 404:
                np.save(path, np.zeros((0, 6)))
                return None
            time.sleep(3 + 3 * i)
        except Exception:
            time.sleep(3 + 3 * i)
    return None


def series(kind, sym, months):
    parts = [fetch(kind, sym, m) for m in months]
    parts = [p for p in parts if p is not None and len(p)]
    if not parts:
        return None
    a = np.concatenate(parts)
    return a[np.argsort(a[:, 0])]


def short(k, f, btc, ts, hold_d, sl):
    t = k[:, 0]; i = int(np.searchsorted(t, ts, "right") - 1)          # свеча поста
    n = int(hold_d * 96)
    if i < 700 or i + n >= len(t) or t[i + n] != t[i] + n * BAR or k[i:i + n, 5].sum() <= 0:
        return None
    p0 = k[i, 4]; hi, op = k[i + 1:i + n + 1, 2], k[i + 1:i + n + 1, 1]
    ks = np.flatnonzero(hi >= p0 * (1 + sl)) if sl else np.array([], int)
    if len(ks):
        x = int(ks[0]); px = max(p0 * (1 + sl), op[x]) * 1.002; xi = i + 1 + x; why = "стоп"
    else:
        px = k[i + n, 4]; xi = i + n; why = "время"
    t0, t1 = t[i] + BAR, t[xi] + BAR
    fund = float(f[(f[:, 0] > t0) & (f[:, 0] <= t1), 1].sum()) if f is not None and len(f) else 0.0
    price = 1 - px / p0
    b = btc[:, 0]; j0, j1 = np.searchsorted(b, t0 - BAR), np.searchsorted(b, t1 - BAR)
    hedge = btc[min(j1, len(b) - 1), 4] / btc[j0, 4] - 1
    pre7 = 1 - p0 / k[i - 672, 4]
    return dict(net=price + fund - FEE, price=price, fund=fund, why=why, hedge=price + fund - FEE + hedge, pre7=pre7)


if __name__ == "__main__":
    E = pd.read_pickle("s26/events.pkl")
    E = E[(E.ts < 1727740800) & E.kind.isin(["делистинг", "предупреждение", "촉구"])].sort_values("ts")
    rows = []
    for r in E.itertuples():
        months = month_list(r.ts)
        for sym in (f"{r.tok}USDT", f"1000{r.tok}USDT"):
            if fetch("klines", sym, months[1]) is None:
                continue
            k = series("klines", sym, months); f = series("fundingRate", sym, months)
            btc = series("klines", "BTCUSDT", months)
            for hd, sl in ((7, None), (7, 0.5), (14, None), (14, 0.5), (30, None), (30, 0.5)):
                x = short(k, f, btc, r.ts, hd, sl)
                if x:
                    rows.append(dict(kind=r.kind, tok=r.tok, sym=sym, ts=r.ts, hold=hd, sl=sl or 0, **x))
            break
    R = pd.DataFrame(rows)
    R.to_pickle("s26/old_trades.pkl")
    print(f"событий с фьючерсом: {R.groupby('kind').tok.nunique().to_dict()}")
    for (k, hd, sl), x in R.groupby(["kind", "hold", "sl"]):
        d = pd.Series(x.net.values, index=pd.to_datetime(x.ts.values, unit="s").date).groupby(level=0).mean()
        t = d.mean() / d.std() * np.sqrt(len(d)) if len(d) > 2 else np.nan
        print(f"  {k:14s} {hd:2d} сут стоп {sl:.0%}: n={len(x):3d} чистыми {x.net.mean()*100:+6.2f}% (t {t:+.1f}, медиана "
              f"{x.net.median()*100:+5.1f}%, в плюсе {(x.net>0).mean():.0%}, стопов {(x.why=='стоп').mean():.0%}) "
              f"с хеджем BTC {x.hedge.mean()*100:+6.2f}% фандинг {x.fund.mean()*100:+5.2f}% до 7д {x.pre7.mean()*100:+5.1f}%")
    x = R[(R.kind == "делистинг") & (R.hold == 7) & (R.sl == 0)]
    print(x.assign(d=pd.to_datetime(x.ts, unit="s").dt.strftime("%Y-%m-%d"))[["d", "sym", "net", "fund", "hedge", "pre7"]]
          .round(3).to_string(index=False))
