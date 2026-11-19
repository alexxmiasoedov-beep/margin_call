"""s202 — «дроблёный завод на Binance» (Г1 s201): сумма заводов монеты на Binance за скользящие 60 мин ≥ 0,5% обращения
без одиночного перевода ≥ 0,5%, без 🐋-завода и такого же события за 48 ч, спокойный рынок ±5% → шорт перпа 24 ч, стоп 25%.
Контроль — одиночные 🐋-заводы на тех же данных. Запись до расчёта — ВЫВОДЫ.md (коммит b0e4ee4).

Запуск из /home/user/mc_data (свечи старых периодов — MC_K / MC_F, как в s117):
  python3 run.py deposits                     — сбор s167 ≥ 0,05% из raw → s202_dep_s167.pkl (один раз)
  python3 run.py 2024–2026 main
  MC_K=s117/k_oos.pkl MC_F=s117/fund_oos.pkl python3 run.py 2022–2024 main     (и s167)
  MC_K=s117/k_2020.pkl MC_F=s117/fund_2020.pkl python3 run.py 2020–2022 main   (и s167)
  python3 run.py report
"""
import glob
import gzip
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s187"))
sys.path.insert(0, os.path.join(HERE, "..", "s182"))

DAY, OUT = 86400, "/home/user/mc_data"
WIN, GAP, BIG, SMALL = 3600, 48 * 3600, 0.005, 0.0005


def build_s167():
    """Переводы на Binance от не-бирж ≥ 0,05% обращения у токенов s167 (метки и фильтры — как в s167/test.py)."""
    sys.path.insert(0, os.path.join(HERE, "..", "s167"))
    import test as S  # noqa: E402
    E6 = S.ev_module()
    CEX = E6.CEX
    TK = json.load(open(f"{OUT}/s167/toks.json"))
    rows = []
    for p in sorted(glob.glob(f"{OUT}/s167/raw/b*.json.gz")):
        rows += json.load(gzip.open(p, "rt"))
    X = pd.DataFrame(rows, columns=["block", "tok", "frm", "to", "amt", "tx", "li"])
    lab = {a: " ".join(v) for a, v in CEX.items()}
    X = X[~X.to.map(lambda a: bool(E6.CUST.search(lab.get(a, ""))))]
    X = X[~X.frm.isin(CEX.keys()) & (X.frm != "0x" + "0" * 40)].copy()
    X["exch"] = X.to.map(lambda a: CEX[a][0])
    X = X[X.exch == "Binance"].copy()
    bt = json.load(open(f"{OUT}/s160/cache_blocktime.json"))
    A = np.array(sorted((int(k), v) for k, v in bt.items()), float)
    X["t"] = np.interp(X.block, A[:, 0], A[:, 1]).astype(np.int64)
    C = S.circ_table(TK)
    fr = np.full(len(X), np.nan)
    for tok, idx in X.groupby("tok").groups.items():
        s = C.get(tok)
        if s is None:
            continue
        d = pd.to_datetime(X.loc[idx, "t"], unit="s").dt.normalize().values
        k = s.index.values.searchsorted(d, "right") - 1
        c = np.where(k >= 0, s.values[np.maximum(k, 0)], np.nan)
        fr[X.index.get_indexer(idx)] = X.loc[idx, "amt"].values / np.where(c > 0, c, np.nan)
    X["frac"] = fr
    X["perp"] = X.tok.map(lambda t: TK[t]["perp"])
    X = X[(X.frac >= SMALL) & X.perp.notna()]
    X = X[["perp", "t", "frm", "frac", "block", "li"]].reset_index(drop=True)
    X.to_pickle(f"{OUT}/s202_dep_s167.pkl")
    print("s167: переводов на Binance ≥ 0,05%:", len(X), "монет", X.perp.nunique(), flush=True)


def deposits(src):
    if src == "main":
        X = pd.read_pickle(f"{OUT}/s195_deposits.pkl")
        X = X[(X.exch == "Binance") & X.perp.notna()]
        X = X[["perp", "t", "frm", "frac", "block", "li"]].copy()
    else:
        X = pd.read_pickle(f"{OUT}/s202_dep_s167.pkl")
    X["t"] = X.t.astype(np.int64)
    return X[X.frac >= SMALL].sort_values(["t", "block", "li"]).reset_index(drop=True)


def events(X):
    """Дробь (сумма за 60 мин ≥ 0,5% без одиночного ≥ 0,5%) и одиночные 🐋 (≥ 0,5%, первый за 48 ч)."""
    out = []
    for perp, g in X.groupby("perp"):
        tt, ff, fr = g.t.values, g.frac.values, g.frm.values
        big_t = tt[ff >= BIG]
        last_split = last_single = -10 ** 12
        for i in range(len(g)):
            t = tt[i]
            jb = np.searchsorted(big_t, t, "left")                  # одиночные ≥ 0,5% строго раньше t
            prev_big = big_t[jb - 1] if jb > 0 else -10 ** 12
            if ff[i] >= BIG:
                if t - prev_big >= GAP and t - last_single >= GAP:
                    out.append((perp, int(t), "single", float(ff[i]), 1))
                    last_single = t
                continue
            j0 = np.searchsorted(tt, t - WIN, "right")
            w = ff[j0:i + 1]
            if w.sum() >= BIG and (w < BIG).all() and t - prev_big >= GAP and t - last_split >= GAP:
                out.append((perp, int(t), "split", float(w.sum()), len(set(fr[j0:i + 1]))))
                last_split = t
    return pd.DataFrame(out, columns=["perp", "tb", "kind", "sum", "nsend"])


def run(per, src):
    import fastbt as FB  # noqa: E402
    import common182 as C  # noqa: E402
    K = FB.K
    t0, t1 = C.ts(C.PER[per][0]), C.ts(C.PER[per][1])
    E = events(deposits(src))
    E["entry"] = (np.ceil((E.tb + 900) / 900) * 900).astype(np.int64)
    E = E[(E.entry >= t0) & (E.entry < t1)]
    res = []
    for s, g in E.groupby("perp"):
        if s not in K:
            continue
        t = K[s]["t"].astype(np.int64)
        c = K[s]["c"].astype(float)
        lo, _ = FB.live(s)
        g = g.sort_values("entry").copy()
        st = g.entry.values - 900
        I = np.searchsorted(t, st)
        ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == st) & (I >= 96)
        ok &= t[np.minimum(I, len(t) - 1)] >= lo + DAY
        g, I = g[ok].copy(), I[ok]
        if not len(g):
            continue
        for hold, sl, suf in ((24, 0.25, ""), (168, 0.50, "7")):
            okt, net, stp, bars, tend = FB.trades(s, I, sl, hold, -1)
            g["net" + suf] = np.where(okt, net, np.nan)
            g["stop" + suf] = np.where(okt, stp, False)
            g["hed" + suf] = g["net" + suf].values + FB.alt_mv(t[I] + 900, tend)
            g["pl" + suf] = FB.placebo(s, I, sl, hold, -1)
        g["pl_7d"] = FB.placebo(s, I, 0.25, 24, -1, days=(7,))
        g["r24"] = c[I] / c[I - 96] - 1
        g["t"] = g.entry
        res.append(g)
    R = pd.concat(res, ignore_index=True)
    R["per"] = per
    R.to_pickle(f"{OUT}/s202_{src}_{per}.pkl")
    calm = R.net.notna() & (R.r24.abs() <= 0.05)
    print(per, src, R[calm].groupby("kind").size().to_dict(), "| без фильтра рынка",
          R[R.net.notna()].groupby("kind").size().to_dict(), flush=True)


def view(R, mask, suf=""):
    x = R[mask].copy()
    x["net"], x["hed"], x["pl"], x["stop"] = x["net" + suf], x["hed" + suf], x["pl" + suf], x["stop" + suf]
    x = x[x.net.notna()]
    x["why"] = np.where(x.stop.astype(bool), "стоп", "время")
    return x


def report():
    import common182 as C  # noqa: E402
    print("s202 — «дроблёный завод на Binance»: сумма за 60 мин ≥ 0,5% без одиночного ≥ 0,5%, спокойный рынок ±5% → "
          "шорт перпа 24 ч, стоп 25%\n")
    pn, ph, pdl = [], [], []
    for per in C.PER:
        R = pd.read_pickle(f"{OUT}/s202_main_{per}.pkl")
        calm = R.r24.abs() <= 0.05
        sp, si = R.kind == "split", R.kind == "single"
        x = view(R, sp & calm)
        print(f"== {per} ==")
        print(f"  основной: дробь, спокойный рынок: {C.line(x, per)}")
        print(f"     сверх плацебо 7 сут: {(x.net - x.pl_7d).mean():+.2%}")
        print(f"  дробь, один отправитель: {C.line(view(R, sp & calm & (R.nsend == 1)), per)}")
        print(f"  дробь, несколько отправителей: {C.line(view(R, sp & calm & (R.nsend > 1)), per)}")
        print(f"  дробь без фильтра рынка: {C.line(view(R, sp & R.r24.notna()), per)}")
        print(f"  дробь, 7 сут, стоп 50%: {C.line(view(R, sp & calm, '7'), per)}")
        print(f"  контроль: одиночный 🐋, спокойный рынок: {C.line(view(R, si & calm), per)}")
        y = pd.concat([x, view(R, si & calm)])
        d, se = C.diff(y.net, y.kind == "split", y.t)
        pdl.append((d, se, len(y)))
        print(f"  Δ дробь − одиночный: {d:+.2%} (t {d / se:+.1f})")
        m, t, n = C.ct(x.net, x.t)
        mh, th, _ = C.ct(x.hed, x.t)
        pn.append((m, abs(m / t) if t else np.nan, n))
        ph.append((mh, abs(mh / th) if th else np.nan, n))
        if per == "2024–2026":
            cut = C.ts(C.PER[per][2])
            h1, h2 = x[x.t < cut].net.mean(), x[x.t >= cut].net.mean()
            crit = [("≥ 20 в месяц", n / C.months(per) >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
                    ("сверх плацебо > 0", (x.net - x.pl).mean() > 0), ("с хеджем > 0", mh > 0)]
            print("  правило владельца: " + "; ".join(f"{k} — {'да' if ok else 'нет'}" for k, ok in crit))
        print()
    m, t = C.combine(pn)
    mh, th = C.combine(ph)
    print(f"Три периода, основной: {m:+.2%} (t {t:+.1f}); с хеджем {mh:+.2%} (t {th:+.1f})")
    print("  по периодам: " + " / ".join(f"{a:+.2%}" for a, _, _ in pn) + "; с хеджем " +
          " / ".join(f"{a:+.2%}" for a, _, _ in ph))
    d, t = C.combine(pdl)
    print(f"Δ дробь − одиночный вместе: {d:+.2%} (t {t:+.1f})")
    print("\nНезависимые токены s167:")
    ps = []
    for per in ("2020–2022", "2022–2024"):
        p = f"{OUT}/s202_s167_{per}.pkl"
        if not os.path.exists(p):
            continue
        R = pd.read_pickle(p)
        calm = R.r24.abs() <= 0.05
        x = view(R, (R.kind == "split") & calm)
        print(f"  {per} дробь: {C.line(x, per)}")
        print(f"  {per} одиночный 🐋: {C.line(view(R, (R.kind == 'single') & calm), per)}")
        m, t, n = C.ct(x.net, x.t)
        ps.append((m, abs(m / t) if t else np.nan, n))
    if ps:
        m, t = C.combine(ps)
        print(f"  вместе (дробь): {m:+.2%} (t {t:+.1f})")


if __name__ == "__main__":
    if sys.argv[1] == "report":
        report()
    elif sys.argv[1] == "deposits":
        build_s167()
    else:
        run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "main")
