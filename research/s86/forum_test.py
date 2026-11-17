"""s86 — внимание корейской розницы по форуму DCInside (гипотеза — ВЫВОДЫ.md, записана до выгрузки). Заголовки
s86/dc.jsonl (время KST → UTC), словарь монет s86/kr_names.json (корейские названия рынков к воне Upbit и Bithumb):
полное корейское название, оно же без хвоста «코인» (если остаётся ≥ 2 слогов), латинский тикер из 3+ букв отдельным
словом; без лидеров 🔝, стейблкоинов, монет без фьючерса и названий из STOP. Событие — монета впервые за 7 сут в пятёрке
по упоминаниям за 24 ч (≥ 5 упоминаний), фьючерс ≥ суток, одно событие на монету за 7 сут; основная группа — без входов
🔝/👀 за 7 сут и 🇰🇷/🛒 за прошлые сутки. Шорт 10/25/48 (основной) и 7 сут со стопом 50%; плацебо — та же монета
за 45/90/135 сут. Запуск из папки с данными; с ключом --check — только разбор (без доходов)."""
import json
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s66"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, fut_of, live  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402
from attn_test import EXITS, idx_at, trade  # noqa: E402

MAJ = {"XRP", "BTC", "ETH", "DOGE", "SOL", "SUI", "ONDO", "ADA", "WLD", "SHIB"}
STABLE = {"USDT", "USDC", "USDE", "USD1", "USDS", "DAI", "FDUSD", "TUSD", "PYUSD", "RLUSD"}
STOP = set()                       # названия-обычные слова: заполняется после проверки разбора, до расчёта доходов
LAT = re.compile(r"[A-Za-z][A-Za-z0-9]*")


def dictionary():
    names = json.load(open("s86/kr_names.json"))
    kor, lat = {}, {}
    for c, kns in names.items():
        if c in MAJ or c in STABLE:
            continue
        s, _ = fut_of(c)
        if not s or s not in K:
            continue
        for kn in kns:
            for v in {kn, kn[:-2] if kn.endswith("코인") and len(kn) - 2 >= 2 else kn}:
                if len(v) >= 2 and v not in STOP:
                    kor[v] = s
        if len(c) >= 3 and c not in STOP:
            lat[c.upper()] = s
    return kor, lat


def posts():
    seen, rows = set(), []
    for line in open("s86/dc.jsonl"):
        no, ts, title = json.loads(line)
        if no in seen:
            continue
        seen.add(no)
        rows.append((pd.Timestamp(ts).timestamp() - 9 * 3600, title))       # KST → UTC
    return rows


def mentions(rows, kor, lat):
    L = max(map(len, kor)) if kor else 2
    out = []
    for t, h in rows:
        found = set()
        for i in range(len(h)):
            for n in range(2, min(L, len(h) - i) + 1):
                s = kor.get(h[i:i + n])
                if s:
                    found.add(s)
        for w in LAT.findall(h):
            s = lat.get(w.upper())
            if s:
                found.add(s)
        for s in found:
            out.append((t, s, h))
    return out


def main():
    kor, lat = dictionary()
    rows = posts()
    M = mentions(rows, kor, lat)
    D = pd.DataFrame(M, columns=["t", "s", "h"])
    print(f"Постов: {len(rows)} ({pd.Timestamp(min(r[0] for r in rows), unit='s'):%d.%m.%Y} … "
          f"{pd.Timestamp(max(r[0] for r in rows), unit='s'):%d.%m.%Y}); упоминаний монет: {len(D)}; монет: {D.s.nunique()}")
    if "--check" in sys.argv:
        top = D.s.value_counts().head(40)
        for s, n in top.items():
            ex = D[D.s == s].h.sample(min(3, n), random_state=1).values
            print(f"  {s:10s} {n:6d} | " + " || ".join(x[:45] for x in ex))
        return
    H = ((D.t // 3600) + 1).astype(np.int64) * 3600                          # конец часа
    C = pd.crosstab(H, D.s)
    grid = np.arange(int(C.index.min()), int(C.index.max()) + 1, 3600)
    C = C.reindex(grid, fill_value=0)
    V24 = C.rolling(24, min_periods=24).sum()
    R = V24.rank(axis=1, ascending=False, method="first")
    top = (R <= 5) & (V24 >= 5)
    in7 = top.rolling(168, min_periods=1).max().shift(1).fillna(0).astype(bool)
    ev = top & ~in7
    S65 = pd.read_pickle("s65/trades.pkl"); S83 = pd.read_pickle("s83/trades.pkl")
    S49 = pd.read_pickle("s49/trades.pkl"); S49 = S49[S49.share >= 0.259]
    S20 = pd.read_pickle("s20/trades.pkl"); S20 = S20[S20.journal == "🇰🇷"]
    wk = {}
    for s, t in list(zip(S65.s, S65.t)) + list(zip(S83.s, S83.t)):
        wk.setdefault(s, []).append(t)
    dy = {}
    for s, t in list(zip(S49.s, S49.t)) + list(zip(S20.s, S20.te)):
        dy.setdefault(s, []).append(t)
    wk = {s: np.array(v) for s, v in wk.items()}; dy = {s: np.array(v) for s, v in dy.items()}
    out, last = [], {}
    for T, row in ev.iterrows():
        T = int(T)
        for s in row.index[row.values]:
            if T - last.get(s, -1e18) < 7 * DAY:
                continue
            lo, hi = live(s)
            if T < lo + DAY or T > hi:
                continue
            i = idx_at(s, T)
            if i is None:
                continue
            last[s] = T
            a, b = wk.get(s, np.zeros(0)), dy.get(s, np.zeros(0))
            c = K[s]["c"]
            d = dict(s=s, t=T, n24=int(V24.at[T, s]), r24=float(c[i] / c[i - 96] - 1),
                     ov=bool(((a <= T) & (a >= T - 7 * DAY)).any() or ((b < T) & (b >= T - DAY)).any()))
            for nm, kw in EXITS.items():
                x = trade(s, i, **kw)
                d[nm] = x["net"] if x else np.nan
                p = [y["net"] for dd in (45, 90, 135) if (j := idx_at(s, T - dd * DAY)) is not None and (y := trade(s, j, **kw))]
                d["pl_" + nm] = np.mean(p) if p else np.nan
            out.append(d)
    X = pd.DataFrame(out)
    X.to_pickle("s86/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"Событий: {len(X)} ({len(X) / months:.1f} в месяц); с входами 🔝 👀 🇰🇷 🛒: {X.ov.mean():.0%};"
          f" медиана упоминаний за 24 ч {X.n24.median():.0f}")
    for lab, x0 in (("без 🔝 👀 🇰🇷 🛒 (основная)", X[~X.ov]), ("все события", X), ("после роста ≥ 10%", X[X.r24 >= 0.10]),
                    ("остальные", X[X.r24 < 0.10])):
        for col in ("S_10_25", "S_7d"):
            x = x0[x0[col].notna()]
            if len(x) < 8:
                continue
            m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
            h1, h2 = x[x.t < CUT], x[x.t >= CUT]
            (m1, t1, _), (m2, t2, _) = ct(h1[col], h1.t), ct(h2[col], h2.t)
            print(f"  {lab:26s} {col:8s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
                  f" половины {m1:+6.2%} (t {t1:+4.1f}) / {m2:+6.2%} (t {t2:+4.1f}) | плацебо {x['pl_' + col].mean():+6.2%},"
                  f" разница {dp:+6.2%} (t {tp:+4.1f})")


if __name__ == "__main__":
    main()
