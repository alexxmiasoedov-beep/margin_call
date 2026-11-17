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
# Названия — обычные слова или чужие монеты: из 20 случайных заголовков (--words) 25% и больше не о монете.
# Зафиксировано 17.11 по разбору заголовков, до расчёта доходов (ВЫВОДЫ.md, «Разбор заголовков»).
STOP = {"레이", "알파", "펌프", "스페이스", "스테이블", "사인", "자이", "우마",
        "THE", "MOVE", "OPEN", "ATH", "TRUMP"}
OTHER = ["스팀달러", "알파쿼크", "레이븐", "자이온"]   # чужие монеты вне словаря рынков: забирают совпадение у 스팀, 알파, 레이, 자이
LAT = re.compile(r"[A-Za-z][A-Za-z0-9]*")


def dictionary():
    """kor: корейское название → фьючерс или None. None — монеты, которые не считаются (лидеры, стейблкоины, без
    фьючерса, STOP), но остаются в словаре, чтобы самое длинное совпадение забрало их название у короткого чужого
    (알파쿼크 — AQT без фьючерса, а не 알파; 레이어제로 — ZRO, а не 레이)."""
    names = json.load(open("s86/kr_names.json"))
    kor, lat = {}, {}
    for c, kns in names.items():
        s, _ = fut_of(c)
        ok = c not in MAJ and c not in STABLE and bool(s) and s in K
        for kn in kns:
            for v in {kn, kn[:-2] if kn.endswith("코인") and len(kn) - 2 >= 2 else kn}:
                if len(v) >= 2:
                    kor[v] = s if ok and v not in STOP else kor.get(v)
        if ok and len(c) >= 3 and c not in STOP:
            lat[c.upper()] = s
    for v in OTHER:
        kor[v] = None
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


def hangul(ch):
    return "\uac00" <= ch <= "\ud7a3"


def kor_hits(h, kor, L):
    """Корейские названия в заголовке: начало слова (перед названием нет слога хангыля — частицы корейского
    пишутся справа, слева слог означает другое слово: 러시아, 프로그램, 하자마자) и самое длинное совпадение
    с этого места (매직에덴, а не 매직). Правило разбора зафиксировано 17.11 по --check, до расчёта доходов."""
    out, i = [], 0
    while i < len(h):
        if i and hangul(h[i - 1]):
            i += 1
            continue
        for n in range(min(L, len(h) - i), 1, -1):
            if h[i:i + n] in kor:
                out.append((h[i:i + n], kor[h[i:i + n]]))
                i += n
                break
        else:
            i += 1
    return out


def mentions(rows, kor, lat):
    L = max(map(len, kor)) if kor else 2
    out = []
    for t, h in rows:
        found = {s for _, s in kor_hits(h, kor, L) if s}
        for w in LAT.findall(h):
            s = lat.get(w.upper())
            if s:
                found.add(s)
        for s in found:
            out.append((t, s, h))
    return out


def words(rows, kor, lat):
    """--words: для каждого названия — число совпадений и примеры окружения; по ним составлен STOP."""
    import random
    L = max(map(len, kor))
    hk, hl = {}, {}
    for _, h in rows:
        for v, s in kor_hits(h, kor, L):
            if s:
                hk.setdefault(v, []).append(h)
        for w in LAT.findall(h):
            if w.upper() in lat:
                hl.setdefault(w.upper(), []).append(h)
    random.seed(1)
    for lab, hh, d in (("корейские", hk, kor), ("латинские", hl, lat)):
        print(f"--- {lab}: {len(hh)} названий")
        only = [a for a in sys.argv[2:] if not a.startswith("-")]
        for v, ex in sorted(hh.items(), key=lambda x: -len(x[1])):
            if only and v not in only:
                continue
            if not only and len(ex) < (150 if lab == "корейские" else 30):
                break
            smp = random.sample(ex, min(20 if only else 6, len(ex)))
            ctx = []
            for h in smp:
                j = h.upper().find(v) if lab == "латинские" else h.find(v)
                ctx.append(h[max(0, j - 6): j + len(v) + 8])
            print(f"  {v:10s} {d[v]:10s} {len(ex):6d} | " + " | ".join(ctx))


def main():
    kor, lat = dictionary()
    rows = posts()
    M = mentions(rows, kor, lat)
    D = pd.DataFrame(M, columns=["t", "s", "h"])
    print(f"Постов: {len(rows)} ({pd.Timestamp(min(r[0] for r in rows), unit='s'):%d.%m.%Y} … "
          f"{pd.Timestamp(max(r[0] for r in rows), unit='s'):%d.%m.%Y}); упоминаний монет: {len(D)}; монет: {D.s.nunique()}")
    if "--words" in sys.argv:
        words(rows, kor, lat)
        return
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

    def collect(cands, rise=None):
        """cands — (час, монета) по времени; rise — порог роста фьючерса за 24 ч (часть события H1.2)."""
        out, last = [], {}
        for T, s in cands:
            if T - last.get(s, -1e18) < 7 * DAY:
                continue
            lo, hi = live(s)
            if T < lo + DAY or T > hi:
                continue
            i = idx_at(s, T)
            if i is None:
                continue
            c = K[s]["c"]; r24 = float(c[i] / c[i - 96] - 1)
            if rise is not None and r24 < rise:
                continue
            last[s] = T
            a, b = wk.get(s, np.zeros(0)), dy.get(s, np.zeros(0))
            d = dict(s=s, t=T, n24=int(V24.at[T, s]), n6=int(V6.at[T, s]), r24=r24,
                     ov=bool(((a <= T) & (a >= T - 7 * DAY)).any() or ((b < T) & (b >= T - DAY)).any()))
            for nm, kw in EXITS.items():
                x = trade(s, i, **kw)
                d[nm] = x["net"] if x else np.nan
                p = [y["net"] for dd in (45, 90, 135) if (j := idx_at(s, T - dd * DAY)) is not None and (y := trade(s, j, **kw))]
                d["pl_" + nm] = np.mean(p) if p else np.nan
            out.append(d)
        return pd.DataFrame(out)

    def report(X, groups):
        months = (X.t.max() - X.t.min()) / (30.4 * DAY)
        print(f"Событий: {len(X)} ({len(X) / months:.1f} в месяц); с входами 🔝 👀 🇰🇷 🛒: {X.ov.mean():.0%};"
              f" медиана упоминаний за 24 ч {X.n24.median():.0f}, за 6 ч {X.n6.median():.0f}")
        for lab, x0 in groups:
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

    V6 = C.rolling(6, min_periods=6).sum()
    print("\n=== Основная гипотеза: впервые за 7 сут в пятёрке по упоминаниям за 24 ч ===")
    X = collect([(int(T), s) for T, row in ev.iterrows() for s in row.index[row.values]])
    X.to_pickle("s86/trades.pkl")
    report(X, (("без 🔝 👀 🇰🇷 🛒 (основная)", X[~X.ov]), ("все события", X), ("после роста ≥ 10%", X[X.r24 >= 0.10]),
               ("остальные", X[X.r24 < 0.10])))

    print("\n=== H1.2 «форум без оборота»: упоминаний за 6 ч ≥ 5 и ≥ 5× обычных 6 ч за 30 сут, рост фьючерса за 24 ч ≥ 10% ===")
    base = C.shift(6).rolling(720, min_periods=720).sum() / 120             # среднее за 6 ч в прошлые 30 суток
    hot = (V6 >= 5) & (V6 >= 5 * base)
    Y = collect([(int(T), s) for T, row in hot.iterrows() for s in row.index[row.values]], rise=0.10)
    Y.to_pickle("s86/trades_h12.pkl")
    report(Y, (("без 🔝 👀 🇰🇷 🛒 (основная)", Y[~Y.ov]), ("все события", Y)))

if __name__ == "__main__":
    main()
