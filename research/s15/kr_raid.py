"""«Корейский набег»: правило журнала 🇹🇷 (research/s2), но вместо доли пары к лире — доля Кореи (Upbit + Bithumb).
На закрытии часа: доля Кореи в обороте за час ≥ X и в M+ раз выше обычной (медиана за 7 суток), фьючерс за 4 ч вырос
на Y+, оборот за час ≥ 200 тыс. $ → шорт; одна сделка на монету за 48 ч. Выходы — как у 🇹🇷 (тейк 10 / стоп 15 / 24 ч)
и как у 🇰🇷 (тейк 10 / стоп 25 / 48 ч). Отдельно — сверка с 🇰🇷 по тем же данным и пересечение с его сигналами.

Пороги выбираются по первой половине истории, проверка — на второй. Запуск из папки с данными: python3 s15/kr_raid.py"""
import os
import pickle
import sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import K, trade

P = pickle.load(open("s15/kr_panel.pkl", "rb")); PU = pickle.load(open("s15/kr_pumps.pkl", "rb"))
P = {s: d for s, d in P.items() if s not in {"USDC", "USDT", "USDE", "USD1", "DAI", "FDUSD", "TUSD", "PYUSD", "USDS", "RLUSD"}}
EXITS = {"🇹🇷 10/15/24ч": dict(tp=0.10, sl=0.15, hold_h=24), "🇰🇷 10/25/48ч": dict(tp=0.10, sl=0.25, hold_h=48)}


def kr_signals():
    """Сигналы 🇰🇷 по панели: памп (15 мин) и доля Кореи ≥ 20% за последний полный час до закрытия свечи пампа."""
    out = []
    for s, d in P.items():
        pj = PU.get(s)
        if pj is None or not len(pj):
            continue
        Tp = K[s]["t"][pj] + 900
        k = np.searchsorted(d["T"].values, Tp, side="right") - 1
        for jp, tp_, kk in zip(pj, Tp, k):
            if kk < 0 or tp_ - d["T"].values[kk] >= 3600:
                continue
            sh = float(d["share"].values[kk]); sh2 = float(d["share"].values[min(kk + 1, len(d) - 1)])
            out.append(dict(s=s, j=int(jp), T=int(tp_), share=sh, share_next=sh2))
    return pd.DataFrame(out)


def raid(sh_min=0.20, ratio=3.0, rise=0.10, vol_min=2e5, gap_h=48):
    ev = []
    for s, d in P.items():
        m = ((d.share >= sh_min) & (d.share >= ratio * d.norm) & (d.r4 >= rise) & (d.kr + d.bin >= vol_min)).values
        last = -1e18
        for r in d[m].itertuples():
            if r.T - last >= gap_h * 3600:
                ev.append(dict(s=s, j=int(r.j), T=int(r.T), share=r.share, norm=r.norm, r4=r.r4, r1=r.r1, prem=r.prem)); last = r.T
    return pd.DataFrame(ev)


def with_trades(E, **kw):
    rows = []
    for e in E.itertuples():
        x = trade(e.s, e.j, **kw)
        if x:
            rows.append(dict(e._asdict(), **x))
    return pd.DataFrame(rows)


def line(r, cut):
    if not len(r):
        return "нет сделок"
    h = r["T"] < cut
    trim = r.net.sort_values().iloc[:-5].mean() if len(r) > 20 else np.nan
    return (f"n={len(r):4d} | {r.net.mean() * 100:+5.2f}% (медиана {r.net.median() * 100:+5.2f}%, без 5 лучших {trim * 100:+5.2f}%, "
            f"в плюсе {(r.net > 0).mean():3.0%}, фандинг {r.fund.mean() * 100:+4.1f}%) | "
            f"1-я/2-я половина {r.net[h].mean() * 100:+5.2f}/{r.net[~h].mean() * 100:+5.2f}% ({h.sum()}/{(~h).sum()})")


def overlap(E, S, before_h=24, after_h=1):
    """Есть ли у монеты сигнал 🇰🇷 в окне [T − before_h, T + after_h]."""
    by = {s: g["T"].values for s, g in S.groupby("s")}
    return np.array([bool(((by.get(e.s, np.array([])) >= e.T - before_h * 3600) & (by.get(e.s, np.array([])) <= e.T + after_h * 3600)).any())
                     for e in E.itertuples()])


if __name__ == "__main__":
    allT = np.concatenate([d["T"].values for d in P.values()])
    cut = float(np.median(allT))
    print(f"панель: монет {len(P)}, строк {len(allT):,}; середина истории {pd.to_datetime(cut, unit='s'):%d.%m.%Y}")
    S = kr_signals()
    S20 = S[S.share >= 0.20]
    print(f"\nсверка с 🇰🇷 (пампы монет, торгующихся в Корее: {len(S)}; доля Кореи ≥ 20% за прошлый час: {len(S20)})")
    for nm, kw in EXITS.items():
        print(f"  🇰🇷 по панели, выход {nm}: {line(with_trades(S20, **kw), cut)}")
    print("\nсетка «корейского набега» (выход 🇹🇷 10/15/24 ч), без пересечения с 🇰🇷 за 24 ч до сигнала:")
    grid = []
    for sh in (0.10, 0.20, 0.30, 0.40):
        for ratio in (2.0, 3.0, 5.0):
            for rise in (0.0, 0.05, 0.10, 0.15):
                E = raid(sh, ratio, rise)
                if len(E) < 30:
                    continue
                E = E[~overlap(E, S20)]
                r = with_trades(E, **EXITS["🇹🇷 10/15/24ч"])
                if len(r) < 30:
                    continue
                h = r["T"] < cut
                grid.append(dict(sh=sh, ratio=ratio, rise=rise, n=len(r), all=r.net.mean(), h1=r.net[h].mean(), h2=r.net[~h].mean(),
                                 n1=int(h.sum()), win=(r.net > 0).mean()))
                print(f"  доля ≥ {sh:.0%}, ×{ratio:.0f}, рост за 4 ч ≥ {rise:4.0%}: {line(r, cut)}")
    G = pd.DataFrame(grid)
    G.to_pickle("s15/kr_raid_grid.pkl")
    if len(G):
        best = G[G.n1 >= 40].sort_values("h1", ascending=False).head(5)
        print("\nлучшие по первой половине (проверка — вторая половина):")
        for g in best.itertuples():
            print(f"  доля ≥ {g.sh:.0%}, ×{g.ratio:.0f}, рост ≥ {g.rise:.0%}: 1-я {g.h1 * 100:+.2f}% ({g.n1}) → 2-я {g.h2 * 100:+.2f}% ({g.n - g.n1})")
