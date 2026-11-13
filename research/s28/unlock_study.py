"""s28 — путь цены фьючерса Binance вокруг разлоков (s28/ev — события CoinMarketCap, s28/hist — монеты в обращении, цена,
оборот). Событие: разлоки монеты в пределах 2 сут объединены, доля в обращении на день до разлока ≥ 1% (без истории
обращения — доля общего предложения из CoinMarketCap). Сверка тикера: цена CMC и фьючерса Binance (с поправкой 1000x)
отличаются не больше чем на 25%. Доход шорта к рынку (1 − P1/P0 + медиана простой доходности всех фьючерсов) за окна до
и после разлока на часовой сетке s22. Плацебо — та же монета за 45, 90, 135 сут до разлока без разлоков ≥ 0,5% в ±10 сут.
Сделки — common.trade (15-мин свечи, комиссия 0,1%, фактический фандинг). Запуск из папки с данными."""
import datetime
import glob
import json
import os
import re
import sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s22"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common22 import BAR, CUT, DAY, GR, H, K, ct, live, trade     # noqa: E402
from cmc_fetch import tokens                                       # noqa: E402

g = GR["grid"]; C = GR["C"]; ROW = GR["row"]
TEAM = re.compile(r"team|core|founder|advisor|investor|seed|private|strategic|series|backer|contributor|employee|"
                  r"pre-?sale|kol|partner|early", re.I)


def ts(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def hist(cid):
    p = f"s28/hist/{cid}.json"
    if not os.path.exists(p):
        return None
    h = pd.DataFrame(json.load(open(p)), columns=["d", "px", "vol", "mcap", "circ"])
    if h.empty:
        return None
    h["t"] = (pd.to_datetime(h.d) - pd.Timestamp("1970-01-01")) // pd.Timedelta("1s") + 86400   # закрытие дня d — 00:00 d+1
    return h.sort_values("t").reset_index(drop=True)


def build():
    rows = []
    for cid, sym, fut in tokens():
        p = f"s28/ev/{cid}_past.json"
        if not os.path.exists(p) or fut not in ROW:
            continue
        ev = sorted(json.load(open(p)), key=lambda e: e["time"])
        h = hist(cid)
        grp = []
        for e in ev:
            t = ts(e["time"])
            if t < 1727740800 or t > 1792368000:                   # 01.10.2024 … 18.10.2026 (архив свечей)
                continue
            if grp and t - grp[-1]["t"] <= 2 * DAY:
                grp[-1]["amount"] += e["amount"]; grp[-1]["pct_total"] += e["percentage"] or 0
                grp[-1]["alloc"] += e["allocations"]
            else:
                grp.append(dict(t=t, amount=e["amount"], pct_total=e["percentage"] or 0, alloc=list(e["allocations"])))
        for x in grp:
            circ = px = vol30 = np.nan
            if h is not None:
                b = h[h.t < x["t"] - 6 * H]
                if len(b):
                    circ = b.circ.iloc[-1]; px = b.px.iloc[-1]; vol30 = b.vol.tail(30).mean()
            names = [a["allocationName"] for a in x["alloc"]]; vt = {a["vestingType"] for a in x["alloc"]}
            team_amt = sum(a["amount"] for a in x["alloc"] if TEAM.search(a["allocationName"] or ""))
            rows.append(dict(cid=cid, sym=sym, s=fut, t=x["t"], amount=x["amount"], pct_total=x["pct_total"],
                             pct_circ=x["amount"] / circ * 100 if circ and circ > 0 else np.nan,
                             usd=x["amount"] * px if px == px else np.nan, vol30=vol30,
                             cliff="cliff" in vt, team=team_amt / x["amount"] if x["amount"] else 0, names="; ".join(sorted(set(names)))[:120]))
    E = pd.DataFrame(rows)
    if E.empty:
        return E
    E["size"] = E.pct_circ.where(E.pct_circ.notna(), E.pct_total)
    E["usd_vol"] = E.usd / E.vol30
    return E


def px_ok(r):
    """Цена CMC за день до разлока против закрытия фьючерса Binance (1000x — поправка)."""
    h = hist(r.cid)
    if h is None:
        return True
    b = h[h.t < r.t - 6 * H]
    if not len(b) or not b.px.iloc[-1]:
        return True
    k = int(np.searchsorted(g, r.t - DAY))
    c = C[ROW[r.s], min(k, len(g) - 1)]
    mult = 1000.0 if r.s.startswith("1000") and not r.s.startswith("1000000") else 1e6 if r.s.startswith("1000000") else 1.0
    return bool(np.isfinite(c) and 0.8 <= c / (b.px.iloc[-1] * mult) <= 1.25)


def window(s, t0, t1):
    k0, k1 = np.searchsorted(g, t0), np.searchsorted(g, t1)
    if k1 >= len(g) or k0 >= len(g) or k0 == k1:
        return np.nan
    c = C[ROW[s]]
    if not (np.isfinite(c[k0]) and np.isfinite(c[k1])):
        return np.nan
    with np.errstate(all="ignore"):
        m = float(np.nanmedian(C[:, k1] / C[:, k0] - 1))
    return 1 - float(c[k1]) / float(c[k0]) + m


WIN = {"до 30д": (-30, 0), "до 14д": (-14, 0), "до 7д": (-7, 0), "до 1д": (-1, 0),
       "после 1д": (0, 1), "после 7д": (0, 7), "после 14д": (0, 14), "после 30д": (0, 30)}


def paths(E):
    out = []
    for r in E.itertuples():
        out.append({**r._asdict(), **{k: window(r.s, r.t + a * DAY, r.t + b * DAY) for k, (a, b) in WIN.items()}})
    return pd.DataFrame(out)


def table(D, label):
    print(f"\n{label}")
    for k in WIN:
        x = D[k].values.astype(float); T = D.t.values; ok = np.isfinite(x)
        if ok.sum() < 10:
            continue
        m, t, n = ct(x[ok], T[ok])
        h1 = np.nanmean(x[ok & (T < CUT)]); h2 = np.nanmean(x[ok & (T >= CUT)])
        print(f"  {k:10s} n={n:4d} {m*100:+6.2f}% (t {t:+4.1f}, медиана {np.nanmedian(x)*100:+5.2f}%, шорт в плюсе "
              f"{(x[ok] > 0).mean():.0%}) половины {h1*100:+.2f}/{h2*100:+.2f}%")


if __name__ == "__main__":
    E = build()
    print(f"событий-групп: {len(E)}, монет {E.s.nunique() if len(E) else 0}; с долей в обращении {E.pct_circ.notna().sum() if len(E) else 0}")
    E = E[E["size"] >= 1].copy()
    E["ok"] = [px_ok(r) for r in E.itertuples()]
    print(f"разлоков ≥ 1%: {len(E)}, после сверки цены {E.ok.sum()}")
    E = E[E.ok]
    D = paths(E)
    D.to_pickle("s28/paths.pkl")
    table(D, "=== все разлоки ≥ 1% (шорт к рынку)")
    for lo, hi in ((1, 2), (2, 5), (5, 1e9)):
        table(D[(D["size"] >= lo) & (D["size"] < hi)], f"=== размер {lo}–{hi if hi < 1e9 else '∞'}%")
    table(D[D.team >= 0.5], "=== команда и инвесторы ≥ половины объёма")
    table(D[D.team < 0.5], "=== прочие получатели")
    table(D[D.cliff], "=== есть cliff")
    table(D[D.usd_vol >= 1], "=== стоимость разлока ≥ среднего дневного оборота")
    D = D.sort_values("t")
    first = D[D["size"] >= 5].groupby("s").head(1)
    table(first, "=== первый разлок монеты ≥ 5% (обычно годовой cliff после запуска)")
    # плацебо
    allt = {s: E[E.s == s].t.values for s in E.s.unique()}
    P = []
    for r in E.itertuples():
        for back in (45, 90, 135):
            tp = r.t - back * DAY
            if np.any(np.abs(allt[r.s] - tp) < 10 * DAY):
                continue
            P.append(dict(s=r.s, t=tp, **{k: window(r.s, tp + a * DAY, tp + b * DAY) for k, (a, b) in WIN.items()}))
    table(pd.DataFrame(P), "--- плацебо (та же монета за 45–135 сут до разлока)")
