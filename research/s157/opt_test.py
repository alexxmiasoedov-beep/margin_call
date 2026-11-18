"""s157 — признаки опционов BTC и ETH как режим для шортов журналов на трёх периодах (гипотезы — ВЫВОДЫ.md, записаны
до расчёта). Признаки суток до дня входа: RR25 (перцентиль к 90 сут), ΔRR25 за 7 сут, NBP, VRP (IV около денег − реализованная
волатильность BTC за 30 сут), окно 24 ч до пятничной экспирации с OI BTC ≥ медианы 12 прошлых недель. Сделки: пампы со спотом
≥ 26%, ⏰, разлоки, отлив (и все пампы для отчёта). t — кластеры по неделям; плацебо — циклический сдвиг ряда признака
на 28–84 сут. Запуск из /home/user/mc_data: python3 <repo>/research/s157/opt_test.py"""
import io
import json
import os
import urllib.request
import zipfile

import numpy as np
import pandas as pd

DAY, WEEK = 86400, 7 * 86400
PER = {"2020–2022": ("2020-10-01", "2022-10-01"), "2022–2024": ("2022-10-01", "2024-10-01"), "2024–2026": ("2024-10-01", "2026-10-17")}
O9 = {"2020–2022": "s88/oos2020_trades.pkl", "2022–2024": "s88/oos_trades.pkl", "2024–2026": "s88/trades.pkl"}


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def btc_daily():
    path = "s157/btc_1d.json"
    if os.path.exists(path):
        return json.load(open(path))
    out = {}
    for m in pd.period_range("2020-06", "2026-10", freq="M"):
        u = f"https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1d/BTCUSDT-1d-{m}.zip"
        z = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "research-script/1.0"}), timeout=60).read()))
        for ln in z.read(z.namelist()[0]).decode().splitlines():
            q = ln.split(",")
            t = int(q[0]); t = t // 1000 if t > 1e14 else t        # с 2025 г. время в микросекундах
            out[str(t // 1000 if t > 1e12 else t)] = float(q[4])
    json.dump(out, open(path, "w"))
    return out


def features():
    F = pd.read_json("s157/daily_feat.jsonl", lines=True)
    F["d"] = F.day.map(ts)
    g = F.groupby("d")
    D = pd.DataFrame({"rr": g.rr25.mean(), "atm": g.atm.mean(),
                      "nbp": g.apply(lambda x: (x.put_net - x.call_net).sum() / x.prem.sum() if x.prem.sum() > 0 else np.nan)})
    D = D.reindex(np.arange(D.index.min(), D.index.max() + DAY, DAY))
    b = pd.Series({int(k): v for k, v in btc_daily().items()}).sort_index()
    lr = np.log(b).diff()
    rv = lr.rolling(30).std() * np.sqrt(365) * 100
    D["vrp"] = D.atm - rv.reindex(D.index).values
    D["drr"] = D.rr - D.rr.shift(7)

    def pct90(x):
        v = x.values; out = np.full(len(v), np.nan)
        for i in range(90, len(v)):
            w = v[i - 90:i]; w = w[np.isfinite(w)]
            if np.isfinite(v[i]) and len(w) >= 60:
                out[i] = (w < v[i]).mean()
        return out
    for c in ("rr", "drr", "nbp", "vrp"):
        D[c + "_p"] = pct90(D[c])
    return D


def expiry_windows():
    E = pd.DataFrame(json.load(open("s157/expiries.json")))
    E = E[(E.cur == "BTC") & E.type.isin(["W", "M", "Q"])].copy()
    E["tx"] = pd.to_datetime(E.t, utc=True).map(lambda x: int(x.timestamp()) // 3600 * 3600)
    E = E.sort_values("tx").drop_duplicates("tx")
    E["big"] = E.notional >= E.notional.rolling(12, min_periods=8).median().shift(1)
    return E[["tx", "big", "notional"]]


def trades():
    out = []
    for per in PER:
        P = pd.read_pickle(f"s154_pumps_{per}.pkl")
        out.append(pd.DataFrame(dict(j="пампы со спотом", per=per, te=P[P.share >= 0.26].t, net=P[P.share >= 0.26].net)))
        out.append(pd.DataFrame(dict(j="все пампы", per=per, te=P.t, net=P.net)))
        O = pd.read_pickle(O9[per]); O = O[O.open9 & (O.share >= 0.2) & (O.r1 >= 0.05)]
        out.append(pd.DataFrame(dict(j="⏰", per=per, te=O.t, net=O.S_10_25)))
        U = pd.read_pickle(f"s142_{per}.pkl")
        out.append(pd.DataFrame(dict(j="разлоки", per=per, te=U.t, net=U.net)))
        W = pd.read_pickle(f"s147_{per}.pkl"); W = W[W.r <= -0.01]
        out.append(pd.DataFrame(dict(j="отлив", per=per, te=W.t, net=W.net)))
    X = pd.concat(out, ignore_index=True).dropna(subset=["net"])
    X["te"] = X.te.astype(np.int64)
    X["dprev"] = X.te // DAY * DAY - DAY
    return X


def wdiff(a, b):
    """Разница средних a − b и t с кластерами по неделям входа."""
    if len(a) < 10 or len(b) < 10:
        return np.nan, np.nan
    wa = a.groupby(a.te // WEEK).net.mean(); wb = b.groupby(b.te // WEEK).net.mean()
    d = a.net.mean() - b.net.mean(); se = np.sqrt(wa.var() / len(wa) + wb.var() / len(wb))
    return d, d / se if se > 0 else np.nan


def groups(X, col, kind):
    if kind == "third":
        return X[X[col] >= 2 / 3], X[X[col] <= 1 / 3]
    if kind == "decile":
        return X[X[col] >= 0.9], X[X[col] <= 0.1]
    raise ValueError(kind)


def main():
    D = features(); E = expiry_windows(); X = trades()
    J4 = ["пампы со спотом", "⏰", "разлоки", "отлив"]
    H = [("Г1а RR25: верхняя треть лучше нижней", "rr_p", "third", +1),
         ("Г1б ΔRR25 за 7 сут: верхняя треть лучше нижней", "drr_p", "third", +1),
         ("Г2 NBP: верхний дециль лучше нижнего", "nbp_p", "decile", +1),
         ("Г6 VRP: верхняя треть хуже нижней", "vrp_p", "third", -1)]
    print("признаков по суткам:", int(D.rr.notna().sum()), "с", pd.to_datetime(D.index.min(), unit="s").date())
    for name, col, kind, sign in H:
        print(f"\n{name}")
        Y = X.assign(f=X.dprev.map(D[col])).dropna(subset=["f"]).rename(columns={"f": col})
        A4 = Y[Y.j.isin(J4)]
        for per in PER:
            a, b = groups(A4[A4.per == per], col, kind); d, t = wdiff(a, b)
            print(f"  {per}: четыре журнала — верх {len(a)} {a.net.mean():+.2%}, низ {len(b)} {b.net.mean():+.2%}, "
                  f"разница {sign * d:+.2%} в ожидаемую сторону (t {sign * t:+.1f})")
        a, b = groups(A4, col, kind); d, t = wdiff(a, b)
        signs = []
        for j in J4:
            aj, bj = groups(A4[A4.j == j], col, kind)
            dj, _ = wdiff(aj, bj); signs.append(f"{j} {sign * dj:+.2%}")
        pa, pb = groups(Y[Y.j == "все пампы"], col, kind); dp, tp = wdiff(pa, pb)
        # плацебо: циклический сдвиг ряда признака на 28–84 сут
        pl = []
        ser = D[col]
        for sh in range(28, 85):
            s2 = pd.Series(np.roll(ser.values, sh), index=ser.index)
            Z = A4.assign(g=A4.dprev.map(s2)).dropna(subset=["g"])
            za, zb = groups(Z, "g", kind)
            if len(za) > 10 and len(zb) > 10:
                pl.append(sign * (za.net.mean() - zb.net.mean()))
        share = np.mean(np.array(pl) >= sign * d) if pl else np.nan
        print(f"  шесть лет: {sign * d:+.2%} (t {sign * t:+.1f}); по журналам: {', '.join(signs)}; все пампы {sign * dp:+.2%} (t {sign * tp:+.1f}); "
              f"плацебо не хуже — {share:.0%} сдвигов")
    # Г3: окно 24 ч до крупной пятничной экспирации
    print("\nГ3 вход за 24 ч до крупной недельной экспирации хуже остальных")
    T = E.tx.values; big = E.big.values; last = int(T.max())
    Y = X[X.te <= last].copy()
    k = np.searchsorted(T, Y.te.values, "left")
    nxt = np.where(k < len(T), T[np.minimum(k, len(T) - 1)], 10 ** 12)
    inwin = (nxt - Y.te.values <= DAY) & (nxt - Y.te.values > 0) & np.where(k < len(T), big[np.minimum(k, len(T) - 1)], False)
    Y["win"] = inwin
    A4 = Y[Y.j.isin(J4)]
    for per in PER:
        a, b = A4[(A4.per == per) & A4.win], A4[(A4.per == per) & ~A4.win]; d, t = wdiff(b, a)
        print(f"  {per}: в окне {len(a)} {a.net.mean():+.2%}, вне {len(b)} {b.net.mean():+.2%}, разница (вне − в окне) {d:+.2%} (t {t:+.1f})")
    a, b = A4[A4.win], A4[~A4.win]; d, t = wdiff(b, a)
    print(f"  шесть лет: (вне − в окне) {d:+.2%} (t {t:+.1f}); экспирации до {pd.to_datetime(last, unit='s').date()}")


if __name__ == "__main__":
    main()
