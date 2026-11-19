"""s180 — круглые уровни цены (гипотезы и порог — ВЫВОДЫ.md, записаны до расчёта): Г1 — первое за 30 сут закрытие часа
Upbit/Bithumb выше уровня сетки в вонах; Г2 — долларовые уровни на 15-мин свечах перпа: B «отказ» (вход на свече касания),
A «пробой» (вход через 4 ч). Сетки: {1…9} круглая и контрольная (геометрические середины), {1, 2, 5} и её контроль,
99 сдвигов сетки {1…9} на 10^(j/100) для перестановки. Шорт 24 ч стоп 10% (основная), 24/25, 48/10, 48/25.
Запуск из /home/user/mc_data: MC_K=… MC_F=… python3 <repo>/research/s180/round_test.py <период> (2024–2026 — без MC_K/MC_F);
сводка: python3 … report"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s141", "s174"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from trapped import NONCRYPTO, ct, diff  # noqa: E402

OUT, DAY, H = "/home/user/mc_data", 86400, 3600
PER = {"2020–2022": ("2020-10-01", "2022-10-01", "2021-10-01", "s88/oos2020/kc", "s88/oos2020/map.pkl"),
       "2022–2024": ("2022-10-01", "2024-10-01", "2023-10-01", "s88/oos/kc", "s88/oos/map.pkl"),
       "2024–2026": ("2024-10-01", "2026-10-17", "2025-12-01", None, None)}
D9 = tuple(range(1, 10))
GRIDS = {"r9": D9, "c9": tuple(np.sqrt(np.arange(1, 10) * np.arange(2, 11))), "r125": (1, 2, 5),
         "c125": (np.sqrt(2), np.sqrt(10), np.sqrt(50))}
for j in range(1, 100):
    GRIDS[f"s{j}"] = tuple(sorted(m * 10 ** (j / 100) if m * 10 ** (j / 100) < 10 else m * 10 ** (j / 100) / 10 for m in D9))
EXITS = {"n": (24, 0.10), "n25": (24, 0.25), "n48": (48, 0.10), "n48s25": (48, 0.25)}


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def mult(s):
    return 1e6 if s.startswith(("1000000", "1M")) else (1e3 if s.startswith("1000") else 1.0)


def rfloor(p, steps):
    """Наибольший уровень сетки ≤ p (сетка — мантиссы в [1, 10))."""
    p = np.asarray(p, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        e = np.floor(np.log10(np.where(p > 0, p, np.nan)))
    m = p / 10 ** e; st = np.asarray(sorted(steps), float)
    k = np.searchsorted(st, m + 1e-12, side="right") - 1
    return np.where(k >= 0, st[np.clip(k, 0, len(st) - 1)] * 10 ** e, st[-1] * 10 ** (e - 1))


def dedupe(ev):
    """Одно событие на монету в сутки UTC — самое раннее."""
    ev = sorted(ev, key=lambda x: x[1]); seen, out = set(), []
    for s, t, *rest in ev:
        if (s, t // DAY) not in seen:
            seen.add((s, t // DAY)); out.append((s, t, *rest))
    return out


def kr_series(per, base):
    a, b, cut, path, mp = PER[per]
    out = []
    if path is None:
        for ex in ("upbit", "bithumb"):
            for coin, x in pickle.load(open(f"{OUT}/s15/kr_candles_{ex}.pkl", "rb")).items():
                fut = base.get(coin)
                if fut:
                    out.append((ex, coin, fut, np.asarray(x["t"], np.int64), np.asarray(x["c"], float), np.asarray(x["v"], float)))
        return out
    m = pickle.load(open(f"{OUT}/{mp}", "rb"))
    for ex in ("upbit", "bithumb"):
        d = f"{OUT}/{path}/{ex}"
        for f in os.listdir(d):
            x = pickle.load(open(os.path.join(d, f), "rb")) if f.endswith(".pkl") else None
            if not (isinstance(x, dict) and "t" in x and len(x["t"])):
                continue
            coin = f[:-4].replace("KRW-", "").replace("_KRW", "")
            fut = m.get(coin); fut = fut[:-4] if fut and fut.endswith("USDT") else fut
            fut = fut or base.get(coin)
            if fut:
                out.append((ex, coin, fut, np.asarray(x["t"], np.int64), np.asarray(x["c"], float), np.asarray(x["v"], float)))
    return out


def kr_events(t, c, v, t0, t1):
    """{сетка: [время сигнала (закрытие часа), …]} для одного рынка к воне."""
    o = np.argsort(t); t, c, v = t[o], c[o], v[o]
    T = np.arange(t[0] // H, t[-1] // H + 1) * H
    cc = pd.Series(c, index=t // H * H).groupby(level=0).last().reindex(T).ffill().values
    vv = pd.Series(v, index=t // H * H).groupby(level=0).sum().reindex(T).fillna(0).values
    v24 = pd.Series(vv).rolling(24, min_periods=24).sum().values
    pmax = pd.Series(cc).shift(1).rolling(720, min_periods=720).max().values
    cand = np.flatnonzero((v24 >= 1e9) & (T + H >= t0) & (T + H < t1) & (cc > pmax))
    return {g: (T[cand][rfloor(cc[cand], st) > pmax[cand]] + H) for g, st in GRIDS.items()}


def usd_events(k, s, t0, t1):
    """{сетка: ([(время закрытия свечи события, уровень)] для A, то же для B)} по 15-мин свечам перпа."""
    t = np.asarray(k["t"], np.int64) + 900; qv = np.asarray(k["qv"], float)
    mu = mult(s); c = np.asarray(k["c"], float) / mu; h = np.asarray(k["h"], float) / mu
    v24 = pd.Series(qv).rolling(96, min_periods=96).sum().values
    pc = pd.Series(c).shift(1).rolling(2880, min_periods=2880).max().values
    ph = pd.Series(h).shift(1).rolling(2880, min_periods=2880).max().values
    ok = (v24 >= 5e6) & (qv > 0) & (t >= t0) & (t < t1)
    ca = np.flatnonzero(ok & (c > pc)); cb = np.flatnonzero(ok & (h > ph) & (c < h))
    out = {}
    for g, st in GRIDS.items():
        ra = rfloor(c[ca], st); ea = ca[ra > pc[ca]]
        rb = rfloor(h[cb], st); mb = (rb > ph[cb]) & (c[cb] < rb) & (rb > pc[cb]); eb = cb[mb]
        out[g] = (t[ea], t[eb])
    return out


def run(per):
    from common import K, live, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    from flow_test import alt_index  # noqa: E402
    t0, t1 = ts(PER[per][0]), ts(PER[per][1])
    kind = pd.read_pickle(f"{OUT}/s12/perp_kind.pkl"); bad = set(kind.get("tradfi", set())) | NONCRYPTO
    syms = [s for s in K if s not in bad and not s.endswith("USDC") and "qv" in K[s]]
    base = {}
    for s in syms:
        for p in ("1000000", "1000", "1M", ""):
            if s.startswith(p) and len(s) > len(p):
                base.setdefault(s[len(p):], s)
    T_, I_ = alt_index(K)

    def ix(tt):
        j = int(np.searchsorted(T_, tt - 900, "right")) - 1
        return I_[j] if 0 <= j < len(I_) else np.nan

    cache = {}

    def deal(s, te, full):
        key = (s, te, full)
        if key in cache:
            return cache[key]
        r = None
        i = idx_at(s, te) if s in K else None
        lo, _ = live(s) if s in K else (np.inf, 0)
        if i is not None and int(K[s]["t"][i]) + 900 == te and te >= lo + DAY:
            r = {}
            for nm, (hold, sl) in (EXITS.items() if full else [("n", EXITS["n"])]):
                z = trade(s, i, tp=None, sl=sl, hold_h=hold, side=-1)
                r[nm] = z["net"] if z else np.nan
                if nm == "n":
                    if z is None:
                        r = None; break
                    r["why"] = z["why"]; r["hed"] = z["net"] + ix(te + int(z["bars"]) * 900) / ix(te) - 1
            if r is not None and full:
                pl = []
                for back in (45, 90, 135):
                    j = idx_at(s, te - back * DAY)
                    w = trade(s, j, tp=None, sl=0.10, hold_h=24, side=-1) if j is not None else None
                    if w:
                        pl.append(w["net"])
                r["pl"] = float(np.mean(pl)) if pl else np.nan
        cache[key] = r
        return r

    rows = []
    # Г1: вона
    ev = {g: [] for g in GRIDS}
    for ex, coin, fut, t, c, v in kr_series(per, base):
        if fut not in K:
            continue
        for g, tl in kr_events(t, c, v, t0, t1).items():
            ev[g] += [(fut, int(x), ex, coin) for x in tl]
    for g, lst in ev.items():
        full = not g.startswith("s")
        for fut, sig, ex, coin in dedupe(lst):
            r = deal(fut, sig + 900, full)
            if r:
                rows.append(dict(h="KRW", g=g, s=fut, t=sig + 900, ex=ex, coin=coin, **r))
    print(per, "Г1 готов:", sum(1 for r in rows if r["g"] == "r9"), "событий круглой сетки", flush=True)
    # Г2: доллар
    evA = {g: [] for g in GRIDS}; evB = {g: [] for g in GRIDS}
    for s in syms:
        for g, (ta, tb) in usd_events(K[s], s, t0, t1).items():
            evA[g] += [(s, int(x)) for x in ta]; evB[g] += [(s, int(x)) for x in tb]
    for nm, E, lag in (("A", evA, 4 * H), ("B", evB, 0)):
        for g, lst in E.items():
            full = not g.startswith("s")
            for s, tc in dedupe(lst):
                r = deal(s, tc + lag, full)
                if r:
                    rows.append(dict(h=nm, g=g, s=s, t=tc + lag, **r))
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/s180_{per}.pkl")
    print(per, X[X.g.isin(["r9", "c9"])].groupby(["h", "g"]).size().to_dict(), flush=True)


def journals():
    J = []
    for f, flt in (("s65/trades.pkl", None), ("s83/trades.pkl", None), ("s88/trades.pkl", "o9"), ("s49/trades.pkl", "sp")):
        a = pd.read_pickle(f"{OUT}/{f}")
        if flt == "o9":
            a = a[(a.open9.astype(bool)) & (a.r1 >= 0.05) & (a.share >= 0.20)]
        elif flt == "sp":
            a = a[a.share >= 0.26]
        a = a[["s", "t"]].copy(); a["s"] = a.s.astype(str).str.replace("USDT$", "", regex=True)
        a["t"] = pd.to_numeric(a.t) if np.issubdtype(a.t.dtype, np.number) else pd.to_datetime(a.t, utc=True).astype("int64") // 10 ** 9
        J.append(a)
    J = pd.concat(J); return {s: np.sort(g.t.to_numpy(np.int64)) for s, g in J.groupby("s")}


def report():
    A = {per: pd.read_pickle(f"{OUT}/s180_{per}.pkl") for per in PER}
    JR = journals()
    for hyp, nm in (("KRW", "Г1 — круглая цена в вонах"), ("B", "Г2 B — отказ у круглого уровня в долларах"),
                    ("A", "Г2 A — пробой круглого уровня в долларах, вход через 4 ч")):
        print(f"\n===== {nm}  (шорт 24 ч, стоп 10%)")
        dd, ss, ww = [], [], []
        for per, X in A.items():
            a, b, cut = PER[per][:3]; months = (ts(b) - ts(a)) / (30.4 * DAY); c = ts(cut)
            Y = X[(X.h == hyp)]
            R, C = Y[Y.g == "r9"], Y[Y.g == "c9"]
            Z = pd.concat([R.assign(e=1.0), C.assign(e=0.0)], ignore_index=True)
            d, se = diff(Z, Z.e, "n")
            m, t, n = ct(R.n, R.t); mh, th, _ = ct(R.hed, R.t); mp, tp_, _ = ct(R.n - R.pl, R.t)
            print(f"  {per}: круглые n {n} ({n / months:.0f}/мес) {m:+.2%} (t {t:+.1f}), половины {R[R.t < c].n.mean():+.2%} / "
                  f"{R[R.t >= c].n.mean():+.2%}, с хеджем {mh:+.2%}, сверх плацебо {mp:+.2%} (t {tp_:+.1f}) | контроль n {len(C)} "
                  f"{C.n.mean():+.2%} | Δ {d:+.2%} (t {d / se:+.1f}) | {{1,2,5}}: {Y[Y.g == 'r125'].n.mean():+.2%} против "
                  f"{Y[Y.g == 'c125'].n.mean():+.2%} | другие выходы Δ: " + ", ".join(
                      f"{col} {diff(Z, Z.e, col)[0]:+.2%}" for col in ("n25", "n48", "n48s25")))
            dd.append(d); ss.append(se); ww.append(n)
        w = np.array(ww, float) / sum(ww); dc = float(np.dot(w, dd)); sc = float(np.sqrt(np.dot(w ** 2, np.array(ss) ** 2)))
        allX = pd.concat([X[X.h == hyp] for X in A.values()])
        S = allX.groupby("g").n.mean()
        sh = S[[g for g in S.index if g.startswith("s")]]
        p = float((sh >= S["r9"]).mean()) if len(sh) else np.nan
        print(f"  Δ вместе {dc:+.2%} (t {dc / sc:+.1f}); по периодам " + ", ".join(f"{x:+.2%}" for x in dd)
              + f" | сдвиги сетки: круглая {S['r9']:+.2%}, сдвиги от {sh.min():+.2%} до {sh.max():+.2%}, p {p:.2f} ({len(sh)} сдвигов)")
        X = A["2024–2026"]; a, b, cut = PER["2024–2026"][:3]; months = (ts(b) - ts(a)) / (30.4 * DAY)
        R = X[(X.h == hyp) & (X.g == "r9")].copy()
        R["jr"] = [bool(len(JR.get(s, []))) and bool(np.any(np.abs(JR[s] - t) <= DAY)) for s, t in zip(R.s, R.t)]
        for lab, Q in (("без журналов", R[~R.jr]), ("с журналами", R[R.jr])):
            m, t, n = ct(Q.n, Q.t); mp, tp_, _ = ct(Q.n - Q.pl, Q.t)
            print(f"  2024–2026 {lab}: n {n} ({n / months:.1f}/мес) {m:+.2%} (t {t:+.1f}), половины {Q[Q.t < ts(cut)].n.mean():+.2%} / "
                  f"{Q[Q.t >= ts(cut)].n.mean():+.2%}, сверх плацебо {mp:+.2%} (t {tp_:+.1f})")
        if hyp == "KRW":
            R = pd.concat([X[(X.h == hyp) & (X.g == "r9")].assign(per=per) for per, X in A.items()])
            print("  разрезы (три периода): биржа " + ", ".join(f"{k} {v:+.2%}" for k, v in R.groupby("ex").n.mean().items()))


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
