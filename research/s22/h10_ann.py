"""Г10 (а) по объявлениям — то, что бот видит в реальном времени. События: первое за 7 суток объявление Binance о монете
из трёх семейств (s10/ann.pkl, с 10.2024; без Alpha и без запусков фьючерсов):
  list   — «Binance Will List X» (в т. ч. итоги «Vote to List»);
  hodler — «Introducing X on Binance HODLer Airdrops / Launchpool / Megadrop»;
  margin — «Binance Will Add X on … Margin» / «Binance Adds X … Margin».
Только монеты, у которых бессрочный фьючерс USDT-M торговался ≥ 1 суток до объявления. Вход — шорт перпа на закрытии
следующего часа после публикации (и через 24 ч — проверка запоздания). Сроки 7/14/21/30 суток, стоп +50% и +100% при
плече ×1, комиссия и фактический фандинг, хедж BTC; доход к рынку, к фьючерсам того же возраста и той же волатильности
(h10_margin.matched); половины, годы; по семейству первого объявления; с маржой в кластере и без; пересечение с 🆕 и с
открытием займа (h10_a). t — с кластеризацией по дню. Запуск из папки с данными."""
import re
import sys
import numpy as np, pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common22 import CUT, DAY, GR, H, K, NONCRYPTO, ct, fut_of, fwd, live, summ
from h10_margin import hour_up, matched
from borrow_trades import sims

FAM = {"list": r"\bWill List\b", "hodler": r"HODLer Airdrops|Launchpool|Megadrop",
       "margin": r"Will Add .*\bMargin\b|^Binance Adds .*\bMargin\b"}


def events():
    A = pd.read_pickle("s10/ann.pkl")
    g0 = GR["grid"][0]
    raw = []
    for a in A.values():
        ts = int(a["ts"]) / 1000; t = a["title"]
        if ts < g0 + DAY or "Alpha" in t or "Futures" in t:
            continue
        for fam, p in FAM.items():
            if re.search(p, t):
                for tok in re.findall(r"\(([^()\s,]{1,20})\)", t):
                    s = tok if tok in K else fut_of(tok)[0]
                    if s and s not in NONCRYPTO and s in GR["row"]:
                        raw.append((s, ts, fam))
    R = pd.DataFrame(raw, columns=["s", "ts", "fam"]).drop_duplicates().sort_values("ts")
    out = []
    for s, g in R.groupby("s"):
        last = -1e18
        for ts in g.ts.values:
            if ts - last < 30 * DAY:
                continue
            cl = g[(g.ts >= ts) & (g.ts < ts + 7 * DAY)]
            lo, hi = live(s)
            last = ts
            if lo > ts - DAY:
                continue                                           # фьючерса до объявления не было — другой случай
            out.append(dict(s=s, ts=ts, T=hour_up(ts), first=g[g.ts == ts].fam.iloc[0], fams="+".join(sorted(set(cl.fam))),
                            has_margin="margin" in set(cl.fam), age=(ts - lo) / DAY))
    return pd.DataFrame(out).sort_values("T").reset_index(drop=True)


def block(nm, E, full=True):
    print(f"\n{nm}: {len(E)} событий, дат {pd.to_datetime(E['T'], unit='s').dt.date.nunique()}")
    for h in (168, 720):
        x = np.array([fwd(s, T, h) for s, T in zip(E.s, E["T"])])
        line = f"  {h // 24:2d} сут: шорт к рынку {summ(x, E['T'].values)}"
        if full:
            for md, nmd in (("age", "сверстникам"), ("vol", "той же волатильности")):
                xm = np.array([matched(T, s, h, md) for s, T in zip(E.s, E["T"])])
                line += f" | к {nmd} {np.nanmean(xm) * 100:+.2f}% (t {ct(xm, E['T'].values)[1]:+.1f})"
        print(line)
    for hold, sl in ((7, 0.5), (30, 0.5), (30, 1.0)):
        R = sims(E, sl=sl, hold_h=hold * 24)
        if len(R):
            print(f"  сделки {hold} сут, стоп +{sl * 100:.0f}%: {summ(R.net.values, R['T'].values)}; стопов {(R.why == 'стоп').mean():.0%}; "
                  f"с хеджем BTC {np.nanmean(R.hedged) * 100:+.2f}%")


if __name__ == "__main__":
    E = events()
    print(f"событий (монета с уже торгующимся фьючерсом, первое объявление за 30 суток): {len(E)}; по годам "
          f"{E.groupby(pd.to_datetime(E['T'], unit='s').dt.year).size().to_dict()}; первое объявление: "
          f"{E['first'].value_counts().to_dict()}; с маржой в течение 7 суток: {E.has_margin.sum()}; возраст фьючерса — медиана "
          f"{E.age.median():.0f} сут")
    block("Все события", E)
    for k, g in E.groupby("first"):
        block(f"Первое объявление: {k}", g, full=False)
    block("С маржой в течение 7 суток", E[E.has_margin], full=False)
    block("Без маржи", E[~E.has_margin], full=False)
    block("Фьючерсу ≤ 30 суток", E[E.age <= 30], full=False)
    block("Фьючерсу > 30 суток", E[E.age > 30], full=False)
    D = E.copy(); D["T"] = D["T"] + 24 * H
    block("Вход через 24 ч после объявления", D, full=False)
    EA = pd.read_pickle("s22/h10_a.pkl"); NT = pd.read_pickle("s12/final_journals.pkl")["A"]
    E["rate_open"] = [bool(np.any(np.abs(EA[EA.s == s]["T"].values - T) <= 3 * DAY)) for s, T in zip(E.s, E["T"])]
    E["nt"] = [bool(np.any((NT[NT.s == s].te.values - T >= -DAY) & (NT[NT.s == s].te.values - T <= 15 * DAY))) for s, T in zip(E.s, E["T"])]
    print(f"\nПересечения: с открытием займа (h10_a, ±3 сут) {E.rate_open.sum()} из {len(E)} (событий h10_a всего {len(EA)}); "
          f"с 🆕 (−1…+15 сут) {E.nt.sum()}")
    block("Без 🆕 рядом", E[~E.nt], full=False)
    E.to_pickle("s22/h10_ann.pkl")
