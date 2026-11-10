"""«Зачем заняли» и «кто выигрывает» (research/s21): займы монет маржинального канала MarginData — BOR (займ за 24 ч),
REP (отдача за 24 ч) — против фандинга и против движения цены.

1. Зачем заняли. При отрицательном фандинге займ монеты — часто арбитраж: занять, продать спот, купить фьючерс и получать
   фандинг (ставки на падение нет). При фандинге около нуля и выше — скорее направленный шорт. Группы по среднему
   фандингу за 24 ч до момента (в пересчёте на 8 ч).
2. Кто выигрывает. Займ ускорился (BOR ≥ ×1,5 к значению 4 ч назад) или отдача ускорилась (REP ≥ ×1,5), а цена за 4 ч
   выросла на 5%+ (шорты против цены — «зажатые»), упала на 5%+ (шорты выигрывают) или стоит.

Наблюдения — закрытия часов, когда монета в канале (пост не старше 30 мин); одно наблюдение на монету и группу за 24 ч.
Исход — шорт фьючерса Binance через 24 / 72 / 168 ч: только цена, к рынку (минус медиана всех торгующихся фьючерсов
за то же окно) и с фандингом и комиссией 0,1%. База — все наблюдения монет канала с тем же отбором.
Запуск из папки с данными: python3 s21/borrow_study.py"""
import os
import pickle
import sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s15"))
from common import BAR, FEE, K, funding, fut_of, live

H = 3600
HS = (24, 72, 168)
M = pickle.load(open("s7/margin.pkl", "rb")); G = M["G"]


def market_grid():
    """Медиана доходности (лонг) всех торгующихся фьючерсов от часа k до k + h — по сетке закрытий часов."""
    t0 = min(int(a["t"][0]) for a in K.values()); t1 = max(int(a["t"][-1]) for a in K.values())
    grid = np.arange((t0 // H + 1) * H, t1, H)
    C = np.full((len(K), len(grid)), np.nan, dtype=np.float32)
    for n, a in enumerate(K.values()):
        t = a["t"].astype(np.int64) + BAR                     # время закрытия свечи
        i = np.searchsorted(grid, t)
        ok = (i < len(grid)) & (grid[np.minimum(i, len(grid) - 1)] == t) & (a["qv"] > 0)
        C[n, i[ok]] = a["c"][ok]
    out = {}
    for h in HS:
        r = C[:, h:] / C[:, :-h] - 1
        out[h] = np.r_[np.nanmedian(r, axis=0), np.full(h, np.nan)]
    return grid, out


def coin_rows(coin, g, grid, MK):
    s, _ = fut_of(coin)
    if s is None:
        return []
    a = K[s]; t = a["t"].astype(np.int64) + BAR; c = a["c"].astype(float); lo, hi = live(s)
    tp, bor, rep = g[:, 0], g[:, 1], g[:, 2]
    T = grid[(grid >= tp[0]) & (grid <= tp[-1])]
    k = np.searchsorted(tp, T, side="right") - 1
    present = (k >= 0) & (T - tp[np.maximum(k, 0)] <= 1800)
    T, k = T[present], k[present]
    if not len(T):
        return []
    k4 = np.searchsorted(tp, T - 4 * H, side="right") - 1
    in4 = (k4 >= 0) & (T - 4 * H - tp[np.maximum(k4, 0)] <= 1800)
    ic = np.searchsorted(t, T)
    ok = (ic < len(t)) & (t[np.minimum(ic, len(t) - 1)] == T) & (T - BAR >= lo + 86400) & (T <= hi)
    T, k, k4, in4, ic = T[ok], k[ok], k4[ok], in4[ok], ic[ok]
    if not len(T):
        return []
    i4 = ic - 16
    fr = funding(s); ft = fr[:, 0] if len(fr) else np.zeros(0)
    cs = np.r_[0.0, np.cumsum(fr[:, 1])] if len(fr) else np.zeros(1)
    gapf = np.r_[8.0, np.maximum(1.0, np.round(np.diff(ft) / H))] if len(fr) else np.zeros(0)
    norm = np.r_[0.0, np.cumsum(fr[:, 1] * 8 / gapf)] if len(fr) else np.zeros(1)
    gi = np.searchsorted(grid, T)
    rows = []
    for n in range(len(T)):
        Tn, j = T[n], ic[n]
        a0, a1 = np.searchsorted(ft, Tn - 86400, "right"), np.searchsorted(ft, Tn, "right")
        f24 = (norm[a1] - norm[a0]) / max(1, a1 - a0) if a1 > a0 else np.nan
        r = dict(s=s, T=int(Tn), bor=bor[k[n]], rep=rep[k[n]], bor4=bor[k4[n]] if in4[n] else 0.0,
                 rep4=rep[k4[n]] if in4[n] else 0.0, in4=bool(in4[n]),
                 r4=c[j] / c[i4[n]] - 1 if i4[n] >= 0 and t[i4[n]] == Tn - 4 * H else np.nan, f24=f24)
        for h in HS:
            jj = j + 4 * h
            if jj < len(t) and t[jj] == Tn + h * H and t[jj] <= hi + BAR:
                px = 1 - c[jj] / c[j]
                b0, b1 = np.searchsorted(ft, Tn, "right"), np.searchsorted(ft, Tn + h * H, "right")
                r[f"s{h}"] = px
                r[f"x{h}"] = px + MK[h][gi[n]] if np.isfinite(MK[h][gi[n]]) else np.nan
                r[f"n{h}"] = px + (cs[b1] - cs[b0]) - FEE
        rows.append(r)
    return rows


def thin(d, gap=86400):
    """Одно наблюдение на монету за 24 ч — первое в окне."""
    keep, last = [], {}
    for i, (s, T) in enumerate(zip(d.s.values, d["T"].values)):
        if T - last.get(s, -1e18) >= gap:
            keep.append(i); last[s] = T
    return d.iloc[keep]


def line(g, base, cut):
    if len(g) < 20:
        return f"n={len(g)} — мало"
    out = [f"n={len(g):5d}"]
    for h in HS:
        x, b = g[f"x{h}"].dropna(), base[f"x{h}"].dropna()
        if len(x) < 20:
            continue
        se = np.sqrt(x.var() / len(x) + b.var() / len(b))
        h1, h2 = x[g.loc[x.index, "T"] < cut], x[g.loc[x.index, "T"] >= cut]
        out.append(f"{h} ч: к рынку {x.mean() * 100:+5.2f}% (t к базе {(x.mean() - b.mean()) / se:+4.1f}; половины "
                   f"{h1.mean() * 100:+5.2f}/{h2.mean() * 100:+5.2f}), с фандингом {g[f'n{h}'].mean() * 100:+5.2f}%")
    return " | ".join(out)


if __name__ == "__main__":
    grid, MK = market_grid()
    rows = []
    for coin, g in G.items():
        if coin in ("DAI", "USDC", "FDUSD", "TUSD", "USDP", "BUSD"):
            continue
        rows += coin_rows(coin, g, grid, MK)
    D = pd.DataFrame(rows)
    D.to_pickle("s21/panel.pkl")
    cut = float(D["T"].median())
    base = thin(D)
    print(f"монето-часов в канале: {len(D):,}, монет {D.s.nunique()}; база (одно наблюдение на монету за сутки): {len(base)}")
    print(f"  база: {line(base, base, cut)}")

    print("\n1. Зачем заняли — средний фандинг за 24 ч до момента (на 8 ч):")
    for nm, lo_, hi_ in (("≤ −0,1% (сильный арбитраж)", -9, -0.001), ("−0,1…−0,03%", -0.001, -0.0003), ("−0,03…+0,005%", -0.0003, 0.00005),
                         ("+0,005…+0,02% (обычный)", 0.00005, 0.0002), ("≥ +0,02% (перегрев лонгов)", 0.0002, 9)):
        g = thin(D[(D.f24 > lo_) & (D.f24 <= hi_)])
        print(f"  {nm:30s} {line(g, base, cut)}")

    print("\n2. Кто выигрывает — займ или отдача за 4 ч × цена за 4 ч:")
    acc_b = (D.bor >= 1.5 * D.bor4) & (D.bor >= 50e3) & D.in4
    acc_r = (D.rep >= 1.5 * D.rep4) & (D.rep >= 20e3) & D.in4
    new = ~D.in4
    up, dn = D.r4 >= 0.05, D.r4 <= -0.05
    flat = ~up & ~dn
    for fn, f in (("займ ускорился", acc_b & ~acc_r), ("отдача ускорилась", acc_r & ~acc_b), ("монета только вошла в канал", new)):
        for pn, p in (("цена +5%+ (шорты против цены)", up), ("цена −5%− (шорты выигрывают)", dn), ("цена стоит", flat)):
            g = thin(D[f & p])
            print(f"  {fn:28s} | {pn:30s} {line(g, base, cut)}")
