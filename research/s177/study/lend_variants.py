"""s177 — варианты порогов для займов альтов в DeFi и размер поперечного среза. Без доходов и цен.

Берёт кэш lend_events.py (<папка данных>/s177/lend_panel.pkl). Считает:
  1) сколько монет с перпом Binance имеют займ в DeFi (не родной для сети) ≥ 0,25 / 1 млн $ в среднем по неделям;
  2) частоту «сдвига спроса» при мягких порогах: займ ≥ 0,25 млн $; рост ×1,3 за 3 сут или ×1,5 за 7 сут;
  3) займ к рыночной капитализации свободного оборота не считается (нужна цена) — только ед. токена.
Запуск: python3 -I lend_variants.py [папка данных]
"""
import os
import pickle
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lend_events as L  # noqa: E402

D = sys.argv[1] if len(sys.argv) > 1 else "/home/user/mc_data"
L.D = D
L.PROTO = os.path.join(D, "s177", "proto")
L.CACHE = os.path.join(D, "s177", "lend_panel.pkl")


def main():
    perps = L.perp_sets()
    allperp = set().union(*perps.values())
    df, _ = L.load_panel()
    df = df[~df.sym.isin(L.STABLE | L.MAJOR)]
    df["native"] = [L.NATIVE.get(c) == s for c, s in zip(df.chain, df.sym)]
    df = df[df.sym.isin(allperp) & ~df.native]
    tok = df.groupby(["sym", "day"], as_index=False)[["tvl_u", "bor_u", "bor_usd"]].sum()
    tok["date"] = pd.to_datetime(tok.day * 86400, unit="s")

    print("Поперечный срез: монет-перпов с займом в DeFi (не родным для сети), среднее по неделям")
    print("  период | ≥ 0,25 млн $ | ≥ 1 млн $ | ≥ 5 млн $")
    for pn, a, z in L.PERIODS:
        m = (tok.date >= a) & (tok.date < z) & tok.sym.isin(perps[pn])
        x = tok[m].copy()
        x["wk"] = x.date.dt.to_period("W")
        w = x.groupby(["wk", "sym"]).bor_usd.mean().reset_index()
        res = [w[w.bor_usd >= t].groupby("wk").size().reindex(w.wk.unique(), fill_value=0).mean()
               for t in (2.5e5, 1e6, 5e6)]
        print(f"  {pn} | {res[0]:6.1f} | {res[1]:6.1f} | {res[2]:6.1f}")

    variants = {
        "D025: ×1,3 за 3 сут, U ↑, займ ≥ 0,25 млн $": (3, 1.3, 2.5e5),
        "D7: ×1,5 за 7 сут, U ↑, займ ≥ 1 млн $": (7, 1.5, 1e6),
        "D7_025: ×1,5 за 7 сут, U ↑, займ ≥ 0,25 млн $": (7, 1.5, 2.5e5),
    }
    ev = defaultdict(list)
    for sym, g in tok.groupby("sym"):
        g = L.daily(g[["day", "tvl_u", "bor_u", "bor_usd"]])
        b = g.bor_u.values
        s = g.tvl_u.values + b
        bu = g.bor_usd.values
        days = g.index.values
        for nm, (h, k, thr) in variants.items():
            with np.errstate(divide="ignore", invalid="ignore"):
                r = b[h:] / b[:-h]
                dU = b[h:] / s[h:] - b[:-h] / s[:-h]
            m = np.isfinite(r) & np.isfinite(dU) & (r >= k) & (dU > 0) & (bu[h:] >= thr) & (bu[:-h] >= thr / 2)
            for d in L.first_in(days[h:][m], 7):
                ev[nm].append((sym, d))
    print("\nСобытия «сдвиг спроса» в месяц при мягких порогах (не родные, монеты-перпы своего периода):")
    for nm in variants:
        e = pd.DataFrame(ev[nm], columns=["sym", "day"])
        e["date"] = pd.to_datetime(e.day * 86400, unit="s")
        parts = []
        for pn, a, z in L.PERIODS:
            m = (e.date >= a) & (e.date < z) & e.sym.isin(perps[pn])
            months = (pd.Timestamp(z) - pd.Timestamp(a)).days / 30.44
            parts.append(f"{pn}: {m.sum() / months:5.2f} ({e[m].sym.nunique()} монет)")
        print(f"  {nm}\n      " + " | ".join(parts))


def new_markets():
    """Новые рынки займа (аналог «designated list» Гонконга и «new entrants» Jones–Lamont): первый день, когда
    у пары протокол-сеть-монета займ ≥ 50 тыс. $, не раньше 30 сут после начала разбивки по монетам в этой сети."""
    perps = L.perp_sets()
    df, first = L.load_panel()
    df = df[~df.sym.isin(L.STABLE | L.MAJOR)]
    df["native"] = [L.NATIVE.get(c) == s for c, s in zip(df.chain, df.sym)]
    df = df[df.sym.isin(set().union(*perps.values()))]
    out = []
    for (slug, ch, sym), g in df[df.bor_usd >= 5e4].groupby(["slug", "chain", "sym"]):
        d0 = g.day.min()
        if d0 - first.get((slug, ch), d0) >= 30:
            out.append((slug, ch, sym, d0, L.NATIVE.get(ch) == sym))
    e = pd.DataFrame(out, columns=["slug", "chain", "sym", "day", "native"])
    e["date"] = pd.to_datetime(e.day * 86400, unit="s")
    # первый рынок займа монеты во всём DeFi (по данным), после 2021-01
    tok_first = df[df.bor_usd >= 1e5].groupby("sym").day.min()
    tf = pd.to_datetime(tok_first * 86400, unit="s")
    print("\nНовые рынки займа альта (протокол-сеть-монета, займ ≥ 50 тыс. $ впервые), в месяц:")
    for pn, a, z in L.PERIODS:
        m = (e.date >= a) & (e.date < z) & e.sym.isin(perps[pn])
        months = (pd.Timestamp(z) - pd.Timestamp(a)).days / 30.44
        mt = (tf >= max(pd.Timestamp(a), pd.Timestamp("2021-01-01"))) & (tf < z) & tf.index.isin(list(perps[pn]))
        print(f"  {pn}: рынков {(m & ~e.native).sum() / months:5.2f} в мес. (+ родные {(m & e.native).sum() / months:4.2f});"
              f" монета впервые занимается в DeFi (≥ 0,1 млн $): {mt.sum() / months:4.2f} в мес.")


if __name__ == "__main__":
    main()
    new_markets()
