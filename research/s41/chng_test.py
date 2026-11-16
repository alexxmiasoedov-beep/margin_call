"""s41 — проверка правил с CHNG (гипотезы — ВЫВОДЫ.md, записаны до проверки). Строки канала — s41/rows.pkl (chng_parse.py).
Событие: первый пост, где CHNG монеты ≥ порога, после ≥ 24 ч без такого. Признаки на момент поста: рост фьючерса за 24 ч,
фандинг на 8 ч (последнее начисление), загрузка пула x = ставка / 10-й перцентиль за 30 сут (s11/rates), серия — сколько
постов подряд за прошлые 3 ч CHNG ≥ порога. Сделки (s15/common.trade) с закрытия ближайшей 15-мин свечи:
S_7_20 — шорт, тейк 7%, стоп 20%, 48 ч (как в s9); S_10_15 — тейк 10%, стоп 15%, 24 ч (как 🇹🇷); S_7d — 7 сут, стоп +50%.
Плацебо — та же монета за 45/90/135 сут, тот же выход. Половины — до и после 01.04.2026 (как в s9) и по CUT 01.12.2025.
Итог — s41/events.pkl. Запуск из папки с данными."""
import glob
import os
import pickle
import sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s15")); sys.path.insert(0, os.path.join(HERE, "..", "s40"))
from common import K, fut_of, live, trade  # noqa: E402
import pool_test as PT  # noqa: E402

DAY = 86400
MID = 1775001600                                            # 01.04.2026 — половины как в s9
PL = (45, 90, 135)
EXITS = {"S_7_20": dict(tp=0.07, sl=0.20, hold_h=48), "S_10_15": dict(tp=0.10, sl=0.15, hold_h=24),
         "S_7d": dict(tp=None, sl=0.50, hold_h=168)}


def idx_at(s, ts):
    """Последняя закрытая 15-мин свеча к моменту ts."""
    t = K[s]["t"]; i = int(np.searchsorted(t, ts - 900, "right")) - 1
    return i if i >= 96 else None


def r24(s, i):
    c = K[s]["c"]
    return float(c[i] / c[i - 96] - 1) if c[i - 96] > 0 else np.nan


def deal(s, i, ex):
    r = trade(s, i, side=-1, **EXITS[ex])
    return r["net"] if r else None


def load_rates():
    X = {}
    for f in glob.glob("s11/rates/*.csv"):
        a = os.path.basename(f)[:-4]; s, _ = fut_of(a)
        if s is None:
            continue
        try:
            ser = PT.hourly(f)
        except Exception:
            continue
        if ser is None:
            continue
        fl = ser.rolling(720, min_periods=600).quantile(0.10).shift(1)
        X[s] = (ser.index.values, (ser / fl).values)
    return X


def load_at(X, s, t):
    if s not in X:
        return np.nan
    tt, x = X[s]; i = int(np.searchsorted(tt, t, "right")) - 1
    return float(x[i]) if i >= 0 else np.nan


def events(R, thr, X):
    """Событие — пост с CHNG ≥ порога, если прошлый такой пост этой монеты был ≥ 24 ч назад."""
    rows = []
    for c, g in R.groupby("c"):
        s, _ = fut_of(c)
        if s is None or s not in K:
            continue
        lo, hi = live(s)
        t, ch = g.t.values, g.chng.values
        q = np.flatnonzero(ch >= thr)
        prev_t = -np.inf
        for k in q:
            new_ev = t[k] - prev_t >= DAY
            prev_t = t[k]
            if not new_ev or t[k] - 3 * DAY < lo or t[k] > hi:
                continue
            i = idx_at(s, t[k])
            if i is None:
                continue
            a = int(np.searchsorted(t, t[k] - 3 * 3600))
            row = dict(c=c, s=s, t=t[k], chng=ch[k], run3=int((ch[a:k] >= thr).sum()), r24=r24(s, i),
                       f8=PT.funding8(s, t[k]), x=load_at(X, s, t[k]), i=i)
            for ex in EXITS:
                row[ex] = deal(s, i, ex)
            p = []
            for d in PL:
                j = idx_at(s, t[k] - d * DAY)
                if j is not None:
                    v = deal(s, j, "S_7_20")
                    if v is not None:
                        p.append(v)
            row["plac"] = np.mean(p) if p else np.nan
            rows.append(row)
    return pd.DataFrame(rows)


def ct(x, T):
    d = pd.Series(np.asarray(x, float), index=pd.to_datetime(np.asarray(T), unit="s").date).dropna()
    if len(d) < 5:
        return np.nan, np.nan, len(d)
    q = d.groupby(level=0).mean()
    return d.mean(), (q.mean() / q.std() * np.sqrt(len(q)) if len(q) > 2 and q.std() > 0 else np.nan), len(d)


def line(lab, x, col="S_7_20"):
    x = x[x[col].notna()]
    if len(x) < 8:
        return f"  {lab:46s}: мало ({len(x)})"
    m, t, n = ct(x[col], x.t)
    h1, h2 = x[x.t < MID][col], x[x.t >= MID][col]
    return (f"  {lab:46s}: n={n:4d} {m:+.2%} (t {t:+.1f}), в плюсе {(x[col] > 0).mean():.0%} | половины {h1.mean():+.2%} ({len(h1)}) "
            f"/ {h2.mean():+.2%} ({len(h2)}) | плацебо {x.plac.mean():+.2%}")


if __name__ == "__main__":
    R = pd.read_pickle("s41/rows.pkl")
    X = load_rates()
    PU = pickle.load(open("s15/kr_pumps.pkl", "rb"))
    res = {}
    for thr in (1.0, 0.5, 2.0, 3.0):
        E = events(R, thr, X)
        E["kr"] = [bool(s in PU and len(PU[s]) and (np.abs(K[s]["t"][PU[s]].astype(float) - t) <= DAY).any()) for s, t in zip(E.s, E.t)]
        res[thr] = E
    E = res[1.0]
    print(f"событий CHNG ≥ 1: {len(E)}, монет {E.s.nunique()}, период {pd.to_datetime(E.t.min(), unit='s'):%d.%m.%Y}–{pd.to_datetime(E.t.max(), unit='s'):%d.%m.%Y}")
    up = E[E.r24 >= 0.15]
    print("\nГ1. Ход цены за 24 ч до поста, CHNG ≥ 1, шорт S_7_20 (тейк 7%, стоп 20%, 48 ч)")
    for lab, sel in (("рост ≥ 15% (основное, повтор s9)", E.r24 >= 0.15), ("рост 5–15%", (E.r24 >= 0.05) & (E.r24 < 0.15)),
                     ("около нуля (±5%)", E.r24.abs() < 0.05), ("падение ≤ −10%", E.r24 <= -0.10)):
        print(line(lab, E[sel]))
    print(line("  основное без пампов 🇰🇷 (±24 ч)", up[~up.kr]))
    print("  доза — ответ (рост ≥ 15%):")
    for thr in (0.5, 1.0, 2.0, 3.0):
        x = res[thr]; print(line(f"    CHNG ≥ {thr}", x[x.r24 >= 0.15]))
    print("\nГ2. Кто занимает (основное событие)")
    print(line("направленный (фандинг ≥ 0)", up[up.f8 >= 0]))
    print(line("промежуточный", up[(up.f8 < 0) & (up.f8 > -0.0005)]))
    print(line("арбитражный (≤ −0,05%)", up[up.f8 <= -0.0005]))
    print("\nГ3. Этап пула (основное событие)")
    print(line("ранний (x < 1,5)", up[up.x < 1.5]))
    print(line("напряжённый (1,5–3)", up[(up.x >= 1.5) & (up.x < 3)]))
    print(line("выбранный (x ≥ 3)", up[up.x >= 3]))
    print(line("загрузка неизвестна", up[up.x.isna()]))
    print("\nГ4. Первый всплеск или продолжение (основное событие)")
    print(line("серия 0 (первый за 3 ч)", up[up.run3 == 0]))
    print(line("серия ≥ 1", up[up.run3 >= 1]))
    print("\nГ5. Выходы (основное событие)")
    for ex in EXITS:
        print(line(ex, up, ex))
    pickle.dump(res, open("s41/events.pkl", "wb"))
