"""s178 — перетоки денег между сетями (гипотезы и порог — ВЫВОДЫ.md, записаны до расчёта). Шаги:
  run <период> — сделки «монета × неделя» для всех монет, привязанных к сетям (вход во вторник 00:15 UTC, шорт 7 сут,
                 стоп 25%, хедж индексом альтов); запуск из /home/user/mc_data (старые периоды — с MC_K/MC_F);
  report       — события Г2 (нижняя пятая часть по притоку USDT + USDC за 4 недели), Г3 (z ≤ −2 за неделю),
                 Г4 (оборот DEX ≤ 0,5 средней за 4 недели), контроль, перестановки привязки, порог.
Данные сетей — кэш s177 (/home/user/mc_data/s177/chains), привязка — s177/study/chain_events.token_chains."""
import json
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s141", "s174"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from trapped import ct, diff  # noqa: E402

OUT, DAY = "/home/user/mc_data", 86400
CH = f"{OUT}/s177/chains"
PER = {"2020–2022": ("2020-10-01", "2022-10-01", "2021-10-01"), "2022–2024": ("2022-10-01", "2024-10-01", "2023-10-01"),
       "2024–2026": ("2024-10-01", "2026-10-17", "2025-12-01")}
NPERM = 500


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def ce_call(fn_name, *a):
    """Вызов функции s177/study/chain_events с подменой argv: модули s177 читают папку данных из argv[1]."""
    argv = sys.argv; sys.argv = [argv[0], OUT]
    try:
        sys.path.insert(0, os.path.join(HERE, "..", "s177", "study"))
        import chain_events as CE
        return getattr(CE, fn_name)(*a) if fn_name else CE
    finally:
        sys.argv = argv


def base(s):
    m = re.match(r"^(1000000|100000|10000|1000|1M)(.+)$", s)
    b = m.group(2) if m else s
    return "POL" if b == "MATIC" else b


def mapping():
    perps = ce_call("perp_sets")
    tc, how = ce_call("token_chains", set().union(*perps.values()))
    return {s: c for s, c in tc.items() if c and c != "Ethereum"}, how


def run(per):
    from common import K, live, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    from flow_test import alt_index  # noqa: E402
    t0, t1 = ts(PER[per][0]), ts(PER[per][1])
    M, how = mapping()
    T_, I_ = alt_index(K)

    def ix(tt):
        j = int(np.searchsorted(T_, tt - 900, "right")) - 1
        return I_[j] if 0 <= j < len(I_) else np.nan

    sundays = pd.date_range(pd.Timestamp(PER[per][0]) - pd.Timedelta(days=7), pd.Timestamp(PER[per][1]), freq="W-SUN")
    rows = []
    for s in sorted(K):
        b = base(s); ch = M.get(b)
        if ch is None or "qv" not in K[s]:
            continue
        a = K[s]; t = a["t"].astype(np.int64); cq = np.r_[0.0, np.cumsum(a["qv"].astype(float))]
        lo, _ = live(s)
        if not np.isfinite(lo):
            continue
        for sun in sundays:
            te = int(sun.timestamp()) + 2 * DAY + 900
            if not (t0 <= te < t1) or te < lo + 30 * DAY:
                continue
            i = idx_at(s, te)
            if i is None or t[i] + 900 != te or cq[i + 1] - cq[i + 1 - 96] < 5e6:
                continue
            z = trade(s, i, tp=None, sl=0.25, hold_h=168, side=-1)
            if not z:
                continue
            rows.append(dict(s=s, b=b, chain=ch, how=how.get(b), week=sun, t=te, net=z["net"], why=z["why"],
                             hed=z["net"] + ix(te + int(z["bars"]) * 900) / ix(te) - 1))
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/s178_{per}.pkl")
    print(per, "сделок «монета × неделя»", len(X), "монет", X.s.nunique() if len(X) else 0, "сетей",
          X.chain.nunique() if len(X) else 0, flush=True)


def weekly_clean():
    """USDT + USDC в сети (circulating, $) по неделям (последний день недели до воскресенья включительно)."""
    tot = {}
    for i in (1, 2):
        d = json.load(open(f"{CH}/coin/sc_{i}.json"))
        for ch, v in (d.get("chainBalances") or {}).items():
            for r in v.get("tokens") or []:
                x = float((r.get("circulating") or {}).get("peggedUSD") or 0)
                tot.setdefault(ch, {}); tot[ch][int(r["date"])] = tot[ch].get(int(r["date"]), 0.0) + x
    out = {}
    for ch, dd in tot.items():
        s = pd.Series(dd); s.index = pd.to_datetime(s.index, unit="s")
        out[ch] = s.sort_index().resample("W-SUN").last()
    return pd.DataFrame(out)


def weekly_all():
    CE = ce_call(None)
    out = {}
    for f in os.listdir(f"{CH}/sc"):
        s = CE.series_sc(f[:-8])
        if s is not None:
            out[f[:-8]] = s.resample("W-SUN").last()
    return pd.DataFrame(out)


def ev_g2(W):
    W = W.drop(columns=["Ethereum"], errors="ignore")
    g4 = np.log(W / W.shift(4)); elig = W.shift(4) >= 5e7
    ev, ctl = set(), set()
    for t in W.index:
        row = g4.loc[t][elig.loc[t].fillna(False).values].replace([np.inf, -np.inf], np.nan).dropna()
        if len(row) < 10:
            continue
        cut = row.quantile(0.2)
        for c, v in row.items():
            (ev if v <= cut else ctl).add((c, t))
    return ev, ctl


def ev_g3(W):
    W = W.drop(columns=["Ethereum"], errors="ignore")
    with np.errstate(all="ignore"):
        lg = np.log(W / W.shift(1)).replace([np.inf, -np.inf], np.nan)
    z = lg / lg.rolling(26, min_periods=13).std().shift(1); ok = W.shift(1) >= 5e7
    ev = {(c, t) for c in W for t in W.index[(ok[c] & (z[c] <= -2)).fillna(False).values]}
    ctl = {(c, t) for c in W for t in W.index[(ok[c] & (z[c].abs() < 1)).fillna(False).values]}
    return ev, ctl


def ev_g4():
    CE = ce_call(None)
    ev, ctl = set(), set()
    for f in os.listdir(f"{CH}/dex"):
        c = f[:-8]
        if c == "Ethereum":
            continue
        x = CE.series_dex(c)
        if x is None or not len(x):
            continue
        w = x.resample("W-SUN").sum(); nd = (x > 0).resample("W-SUN").sum()
        b = w.shift(1).rolling(4).mean(); r = w / b; good = (b >= 5e6) & (nd == 7)
        ev |= {(c, t) for t in w.index[(good & (r <= 0.5)).fillna(False).values]}
        ctl |= {(c, t) for t in w.index[(good & (r >= 0.8) & (r <= 1.25)).fillna(False).values]}
    return ev, ctl


def perm_p(X, ev, obs, rng):
    """Доля перестановок привязки монет к сетям внутри недели со средним доходом событий не ниже фактического."""
    evw = {}
    for c, t in ev:
        evw.setdefault(t, set()).add(c)
    G = [(g.chain.to_numpy(), g.hed.to_numpy(), np.array(sorted(evw.get(w, set())), dtype=object))
         for w, g in X.groupby("week") if w in evw]
    if not G:
        return np.nan
    cnt = 0
    for _ in range(NPERM):
        s = n = 0.0
        for chs, h, e in G:
            m = np.isin(rng.permutation(chs), e)
            s += np.nansum(h[m]); n += m.sum()
        if n and s / n >= obs:
            cnt += 1
    return cnt / NPERM


def summary(nm, A, ev, ctl, rng, full=True):
    print(f"\n{nm}")
    res = {}
    for per, X in A.items():
        a, b, cut = PER[per]; months = (ts(b) - ts(a)) / (30.4 * DAY); c = ts(cut)
        key = list(zip(X.chain, X.week))
        E = X[[k in ev for k in key]]; C = X[[k in ctl for k in key]]
        if len(E) < 5:
            print(f"  {per}: событий {len(E)}"); continue
        m, t, n = ct(E.hed, E.t); mr, tr, _ = ct(E.net, E.t)
        Y = pd.concat([E.assign(e=1.0), C.assign(e=0.0)], ignore_index=True)
        d, se = diff(Y, Y.e, "hed") if len(C) >= 5 else (np.nan, np.nan)
        p = perm_p(X, ev, m, rng) if full else np.nan
        top = E.groupby("chain").size().sort_values(ascending=False)
        res[per] = dict(m=m, t=t, h1=E[E.t < c].hed.mean(), h2=E[E.t >= c].hed.mean(), p=p, mr=mr, tr=tr, n=n, months=months,
                        r1=E[E.t < c].net.mean(), r2=E[E.t >= c].net.mean(), cr=C.net.mean())
        print(f"  {per}: n {n:5d} ({n / months:5.1f}/мес, сетей-недель {E.groupby(['chain', 'week']).ngroups / months:4.1f}/мес) | "
              f"с хеджем {m:+.2%} (t {t:+.1f}), половины {res[per]['h1']:+.2%} / {res[per]['h2']:+.2%} | перестановки p {p:.2f} | "
              f"без хеджа {mr:+.2%} (t {tr:+.1f}) | контроль с хеджем {C.hed.mean():+.2%} (n {len(C)}), Δ {d:+.2%} (t {d / se:+.1f}) | "
              f"3 сети {top.head(3).sum() / len(E):.0%}: {', '.join(top.head(3).index)}")
        if full:
            for hw, g in E.groupby(E.how.fillna("?")):
                print(f"      {hw}: n {len(g)}, с хеджем {g.hed.mean():+.2%}")
    r = res.get("2024–2026")
    if r and full:
        ok1 = r["h1"] > 0 and r["h2"] > 0 and r["t"] >= 3 and r["p"] <= 0.05
        ok2 = res.get("2022–2024", {}).get("m", -1) > 0
        ok3 = r["r1"] > 0 and r["r2"] > 0 and r["tr"] >= 3 and r["n"] / r["months"] >= 20 and r["mr"] > r["cr"]
        print(f"  порог: 1) 2024–2026 с хеджем {'да' if ok1 else 'нет'}; 2) 2022–2024 в плюсе {'да' if ok2 else 'нет'}; "
              f"3) правило владельца (без хеджа: половины {r['r1']:+.2%} / {r['r2']:+.2%}, t {r['tr']:+.1f}) {'да' if ok3 else 'нет'}")


def report():
    A = {per: pd.read_pickle(f"{OUT}/s178_{per}.pkl") for per in PER}
    rng = np.random.default_rng(178)
    Wc = weekly_clean()
    g2, g2c = ev_g2(Wc); g3, g3c = ev_g3(Wc); g4, g4c = ev_g4()
    summary("Г2 — нижняя пятая часть сетей по притоку USDT + USDC за 4 недели", A, g2, g2c, rng)
    summary("Г3 — резкий отток USDT + USDC за неделю (z ≤ −2)", A, g3, g3c, rng)
    summary("Г4 — оборот DEX сети за неделю ≤ 0,5 средней за 4 прошлые", A, g4, g4c, rng)
    Wa = weekly_all()
    a2, a2c = ev_g2(Wa); a3, a3c = ev_g3(Wa)
    summary("Для отчёта: Г2 по всем стейблкоинам", A, a2, a2c, rng, full=False)
    summary("Для отчёта: Г3 по всем стейблкоинам", A, a3, a3c, rng, full=False)


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
