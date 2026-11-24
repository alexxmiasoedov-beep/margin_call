"""s271 Г4 — частота «плотностей» (крупная лимитная заявка рядом с ценой) по снимкам стакана bookDepth (data.binance.vision,
с 2023 г.; снимок каждые ~33 с: накопленный объём заявок до ±0,2, ±1, ±2, …, ±5% от цены). Выборка: 4 дня × 24 перпа
из четырёх слоёв ликвидности (места по обороту дня 1–6, 31–36, 101–106, 201–206). Доходы не считаются.

Определения (по стороне покупок; продажи — зеркально):
- W = $ заявок в полосе 0,2–1% от цены (накопленное до 1% минус до 0,2%); M — скользящая медиана W за прошлые 6 ч;
- «плотность появилась» (A): W ≥ 3·M не меньше 4 снимков подряд (~2 мин), до этого ≥ 30 мин без плотности;
- «касание» (D): пока плотность стоит, $ в полосе до 0,2% ≥ 3× своей медианы — цена подошла к заявке (сетап «отскок»);
- конец плотности: W < 1,5·M; «пробой» (B) — к этому моменту цена (средняя цена полосы 0,2%) ушла в сторону заявки на ≥ 0,5%
  от цены появления; иначе «снята» (C).
Запуск из /home/user/mc_data: python3 -I <repo>/research/s271/study/freq_walls.py"""
import io
import os
import sys
import time
import urllib.request
import zipfile

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common271 import DAY, TMP, crypto_perps, load_k, ts  # noqa: E402

DAYS = ["2025-03-03", "2025-08-04", "2025-12-01", "2026-06-01"]
RANKS = {"1–6": range(0, 6), "31–36": range(30, 36), "101–106": range(100, 106), "201–206": range(200, 206)}
UA = {"User-Agent": "research-script/1.0"}


def fetch(sym, day):
    url = f"https://data.binance.vision/data/futures/um/daily/bookDepth/{sym}USDT/{sym}USDT-bookDepth-{day}.zip"
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                z = zipfile.ZipFile(io.BytesIO(r.read()))
            return pd.read_csv(io.BytesIO(z.read(z.namelist()[0])))
        except Exception as e:  # noqa: BLE001
            if "404" in str(e):
                return None
            time.sleep(2 + 3 * k)
    return None


def walls(df):
    df = df.copy()
    df["t"] = (pd.to_datetime(df["timestamp"]) - pd.Timestamp("1970-01-01")) // pd.Timedelta("1s")
    piv = df.pivot_table(index="t", columns="percentage", values="notional", aggfunc="last").sort_index()
    dep = df.pivot_table(index="t", columns="percentage", values="depth", aggfunc="last").sort_index()
    res = {}
    for side, p1, p02 in (("bid", -1.0, -0.2), ("ask", 1.0, 0.2)):
        if p1 not in piv:
            continue
        if p02 in piv:                      # полоса ±0,2% есть в архиве с 2025 г.; без неё — вся полоса до 1%, без касаний
            W = (piv[p1] - piv[p02]).astype(float)
            N02 = piv[p02].astype(float)
            mid = (piv[p02] / dep[p02]).astype(float)
        else:
            W = piv[p1].astype(float)
            N02 = pd.Series(np.nan, index=W.index)
            mid = (piv[p1] / dep[p1]).astype(float)
        M = W.rolling(650, min_periods=200).median().shift(1)
        M02 = N02.rolling(650, min_periods=200).median().shift(1)
        on = (W >= 3 * M).values
        off = (W < 1.5 * M).values
        touch = (N02 >= 3 * M02).values
        tt = W.index.values; pm = mid.values
        A = B = C = D = 0
        last_end = -10 ** 18
        i, n = 0, len(W)
        while i < n - 4:
            if on[i] and on[i:i + 4].all() and tt[i] - last_end >= 1800 and np.isfinite(M.values[i]):
                A += 1
                p_a = pm[i]
                j = i + 4
                touched = False
                while j < n and not off[j]:
                    touched |= bool(touch[j])
                    j += 1
                D += int(touched)
                if j < n:
                    move = (pm[j] / p_a - 1) * (-1 if side == "bid" else 1)
                    if move >= 0.005:
                        B += 1
                    else:
                        C += 1
                last_end = tt[min(j, n - 1)]
                i = j + 1
            else:
                i += 1
        res[side] = (A, B, C, D)
    return res


def main():
    K = load_k("2024–2026")
    P = crypto_perps(K)
    rows = []
    for day in DAYS:
        d0 = ts(day)
        vol = []
        for p in P:
            a = K[p]
            m = (a["t"] >= d0) & (a["t"] < d0 + DAY)
            v = float(a["qv"][m].sum())
            if v > 0 and m.sum() >= 90:
                vol.append((v, p))
        vol.sort(reverse=True)
        for g, rr in RANKS.items():
            for r in rr:
                if r >= len(vol):
                    continue
                v, p = vol[r]
                df = fetch(p, day)
                time.sleep(0.4)
                if df is None:
                    rows.append(dict(day=day, grp=g, s=p, ok=False))
                    continue
                w = walls(df)
                d = dict(day=day, grp=g, s=p, ok=True, qv=v)
                for side, (A, B, C, D) in w.items():
                    d.update({f"{side}_A": A, f"{side}_B": B, f"{side}_C": C, f"{side}_D": D})
                rows.append(d)
                print(day, g, p, w, flush=True)
    X = pd.DataFrame(rows)
    X.to_csv(f"{TMP}/walls_sample.csv", index=False)
    X = X[X.ok]
    print("\nсобытий на монето-сутки (среднее по выборке):")
    cols = [c for c in X.columns if c[:4] in ("bid_", "ask_")]
    print(X.groupby("grp")[cols].mean().round(2).to_string())
    print("монето-суток:", X.groupby("grp").size().to_dict())


if __name__ == "__main__":
    main()
