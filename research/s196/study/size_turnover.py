"""s196 — размер событий к обороту перпа Binance (без доходов): для крупных выходов (≥ 0,1% обращения) — стоимость
по цене CMC на дату события к среднему суточному обороту перпа за 7 сут ДО события (панели s183, колонка qv).
Показывает, у каких монет выход сопоставим с рынком. Только описание."""
import collections
import glob
import json
import statistics
import pandas as pd
from common196 import OUT, DAY, D, PERIODS, ts
from freq_lib import pname, fmt_t
import cosmos_freq as CF

PAN = {}


def panel(p):
    if p not in PAN:
        d = pd.read_pickle(f"{D}/s183/daily_{p}.pkl")[["d", "s", "qv"]]
        PAN[p] = {s: g.set_index("d")["qv"].sort_index() for s, g in d.groupby("s")}
    return PAN[p]


def turnover(sym, t):
    p = pname(t)
    if not p:
        p = "2024–2026"
    P = panel(p)
    for s in (sym, f"1000{sym}", f"{sym}USDT"):
        if s in P:
            q = P[s]
            w = q[(q.index < t) & (q.index >= t - 7 * DAY)]
            if len(w) < 3 and len(q) and t > q.index.max():   # снимок «сейчас» позже конца панели (19.10.2026)
                w = q.iloc[-7:]
            if len(w) >= 3:
                return float(w.mean())
    return None


def price(sym, t):
    rows = json.load(open(f"{OUT}/circ/{sym}.json"))
    best = None
    for d_, c, px in rows:
        tt = ts(d_)
        if tt <= t and px:
            best = px
    return best


def main():
    out = collections.defaultdict(list)
    # Cosmos: архивные снимки и «сейчас»
    for ch, sym in CF.SYM.items():
        for p in sorted(glob.glob(f"{OUT}/cosmos/{ch}_*.json")):
            s = json.load(open(p))
            a = CF.analyze(s, sym, 6)
            if not a:
                continue
            px, tv = price(sym, a["t"]), turnover(sym, a["t"])
            for f, dday, k in a["e1"]:
                if f >= 0.001 and px and tv:
                    out[sym].append(f * a["circ"] * px / tv)
    for p in sorted(glob.glob(f"{OUT}/cosmos/now_*.json")):
        s = json.load(open(p))
        sym = s["tk"]
        if sym in ("INIT", "OM", "ATOM", "TIA", "KAVA"):
            continue
        a = CF.analyze(s, sym, s["exp"])
        if not a:
            continue
        px, tv = price(sym, a["t"]), turnover(sym, a["t"])
        for f, dday, k in a["e1"]:
            if f >= 0.001 and px and tv:
                out[sym].append(f * a["circ"] * px / tv)
    print("Выходы ≥ 0,1% обращения: стоимость к среднему суточному обороту перпа Binance за 7 сут до (медиана, макс, n)")
    allv = []
    for sym, v in sorted(out.items(), key=lambda kv: -statistics.median(kv[1])):
        allv += v
        print(f"  {sym:6s} медиана {statistics.median(v):6.2f}  макс {max(v):6.2f}  n {len(v)}")
    if allv:
        print(f"  ВСЕ: медиана {statistics.median(allv):.2f} оборота суток, ≥ 0,5 суток — {sum(x >= 0.5 for x in allv)} из {len(allv)}")


if __name__ == "__main__":
    main()
