"""s40 — состояния пула займа по ставке Binance (гипотезы — ВЫВОДЫ.md, записаны до проверки).
Ставки — s11/rates/<актив>.csv (время, дневная ставка; запись при пересчёте, между записями ставка держится).
Почасовой ряд; пол — 10-й перцентиль за прошлые 30 сут; загрузка x = ставка / пол.
В1: x впервые ≥ 3 после ≥ 7 сут с x < 1,5. В2: x ≥ 3 непрерывно 72 ч (момент на 72-м часу). В3: первый час x < 1,5 в пределах
7 сут после эпизода x ≥ 3 длиной ≥ 72 ч. Одно событие вида на монету за 7 сут.
Фандинг — последнее начисление до события на 8 ч: направленный ≥ 0, арбитражный ≤ −0,05%, иначе промежуточный.
Сделка — шорт фьючерса с закрытия ближайшей 15-мин свечи, 7 сут, стоп +50%, комиссия 0,1%, фандинг (s15/common.trade);
плацебо — та же монета за 45/90/135 сут; половины до и после 01.12.2025; t по дням. Итог — s40/events.pkl.
Запуск из папки с данными."""
import glob
import os
import pickle
import sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s15"))
from common import K, FU, fut_of, live, trade  # noqa: E402

H, DAY = 3600, 86400
CUT = 1764547200
PL = (45, 90, 135)


def hourly(path):
    a = np.loadtxt(path, delimiter=",", ndmin=2)
    if len(a) < 200:
        return None
    t, r = a[:, 0].astype(np.int64), a[:, 1]
    o = np.argsort(t); t, r = t[o], r[o]
    grid = np.arange((t[0] // H + 1) * H, t[-1] + 1, H)
    i = np.searchsorted(t, grid, "right") - 1
    return pd.Series(r[i], index=grid)


def funding8(s, ts):
    f = FU.get(s)
    if f is None or not len(f):
        return np.nan
    a = np.array([(float(x[0]), float(x[2])) for x in f])
    a = a[np.argsort(a[:, 0])]
    i = int(np.searchsorted(a[:, 0], ts, "right")) - 1
    if i < 1:
        return np.nan
    iv = (a[i, 0] - a[i - 1, 0]) / H
    return a[i, 1] * 8 / iv if iv > 0 else np.nan


def events_for(ser):
    floor = ser.rolling(720, min_periods=600).quantile(0.10).shift(1)
    x = (ser / floor).values; T = ser.index.values
    out = []
    low_run = 0; hi_run = 0; last_hi_end = None; done_ep = False
    last = {"В1": -np.inf, "В2": -np.inf, "В3": -np.inf}
    for k in range(len(x)):
        v = x[k]
        if not np.isfinite(v):
            low_run = hi_run = 0; continue
        if v >= 3:
            if hi_run == 0 and low_run >= 168 and T[k] - last["В1"] >= 7 * DAY:
                out.append(("В1", T[k], v)); last["В1"] = T[k]
            hi_run += 1
            if hi_run == 72 and T[k] - last["В2"] >= 7 * DAY:
                out.append(("В2", T[k], v)); last["В2"] = T[k]
            low_run = 0
        else:
            if hi_run >= 72:
                last_hi_end = T[k]
            hi_run = 0
            if v < 1.5:
                low_run += 1
                if last_hi_end is not None and T[k] - last_hi_end <= 7 * DAY and T[k] - last["В3"] >= 7 * DAY:
                    out.append(("В3", T[k], v)); last["В3"] = T[k]; last_hi_end = None
            else:
                low_run = 0
    return out


def idx(s, te):
    t = K[s]["t"]; i = int(np.searchsorted(t, te - 900))
    return i if i < len(t) and t[i] == te - 900 else None


def short(s, te):
    i = idx(s, te)
    if i is None:
        return None
    r = trade(s, i, tp=None, sl=0.5, hold_h=168, side=-1)
    return r["net"] if r else None


def ct(x, T):
    d = pd.Series(np.asarray(x, float), index=pd.to_datetime(np.asarray(T), unit="s").date).dropna()
    if len(d) < 5:
        return np.nan, np.nan, len(d)
    q = d.groupby(level=0).mean()
    return d.mean(), (q.mean() / q.std() * np.sqrt(len(q)) if len(q) > 2 and q.std() > 0 else np.nan), len(d)


if __name__ == "__main__":
    rows = []
    for f in sorted(glob.glob("s11/rates/*.csv")):
        asset = os.path.basename(f)[:-4]
        s, _ = fut_of(asset)
        if s is None:
            continue
        try:
            ser = hourly(f)
        except Exception:
            continue
        if ser is None:
            continue
        lo, hi = live(s)
        for kind, t, v in events_for(ser):
            if t - 30 * DAY < lo or t > hi:
                continue
            te = (int(t) // 900 + 1) * 900
            n = short(s, te)
            if n is None:
                continue
            p = [short(s, te - d * DAY) for d in PL]
            p = [x for x in p if x is not None]
            fr = funding8(s, t)
            cls = "направленный" if fr >= 0 else "арбитражный" if fr <= -0.0005 else "промежуточный" if np.isfinite(fr) else "нет данных"
            rows.append(dict(kind=kind, s=s, te=te, x=v, f8=fr, cls=cls, net=n, plac=np.mean(p) if p else np.nan))
    D = pd.DataFrame(rows)
    pickle.dump(D, open("s40/events.pkl", "wb"))
    print(f"событий: {len(D)} — {D.kind.value_counts().to_dict()}; монет {D.s.nunique()}")
    for kind in ("В1", "В2", "В3"):
        X = D[D.kind == kind]
        print(f"\n{kind}: шорт фьючерса на 7 сут, стоп +50%")
        for cls in ("все", "направленный", "промежуточный", "арбитражный"):
            x = X if cls == "все" else X[X.cls == cls]
            if len(x) < 5:
                print(f"  {cls:13s}: мало ({len(x)})"); continue
            m, t, n = ct(x.net, x.te)
            h1, h2 = x[x.te < CUT].net, x[x.te >= CUT].net
            print(f"  {cls:13s}: n={n:4d} {m:+.2%} (t {t:+.1f}), медиана {x.net.median():+.2%}, в плюсе {(x.net > 0).mean():.0%}, "
                  f"стопов {(x.net < -0.45).mean():.0%} | половины {h1.mean():+.2%} ({len(h1)}) / {h2.mean():+.2%} ({len(h2)}) | "
                  f"плацебо {x.plac.mean():+.2%}", flush=True)
