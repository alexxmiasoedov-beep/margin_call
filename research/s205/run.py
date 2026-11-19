"""s205 — корейский «всплеск депозитов»: флаг D Bithumb (основной) и Upbit → шорт перпа Binance 24 ч, стоп 25%, спокойный
рынок ±5%. Запись до расчёта — ВЫВОДЫ.md.

Запуск из /home/user/mc_data:
  python3 run.py candles                                         — суточные свечи монет на биржах (кэш s205/candles)
  python3 run.py 2024–2026
  MC_K=s117/k_oos.pkl MC_F=s117/fund_oos.pkl python3 run.py 2022–2024
  python3 run.py report
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s187"))
sys.path.insert(0, os.path.join(HERE, "..", "s182"))

DAY, OUT = 86400, "/home/user/mc_data"
S204, S205 = f"{OUT}/s204", f"{OUT}/s205"
UA = {"User-Agent": "research-script/1.0"}
PRE = ("", "1000", "10000", "1000000", "1M")
WIN = 25 * 3600


def load_flags():
    """Новые эпизоды D и V: биржа, монета, время срабатывания (UTC, с)."""
    rows = []
    for typ in ("D", "V"):
        b = pd.read_csv(f"{S204}/bithumb_events_{typ}.csv")
        b = b[b.new_episode == 1]
        for r in b.itertuples():
            rows.append(("bithumb", typ, r.coin, int(pd.Timestamp(r.start_utc, tz="UTC").timestamp()), int(r.step)))
        u = pd.read_csv(f"{S204}/upbit_days_{typ}.csv")
        u = u[u.new_episode == 1]
        for r in u.itertuples():
            rows.append(("upbit", typ, r.coin, int(pd.Timestamp(r.day, tz="UTC").timestamp()) + 3600, int(r.level)))
    F = pd.DataFrame(rows, columns=["ex", "typ", "coin", "ts", "step"])
    return F.sort_values("ts").reset_index(drop=True)


def get(url, tries=5):
    for k in range(tries):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read())
        except Exception:
            time.sleep(1 + 2 * k)
    return None


def candles():
    """Суточные свечи монеты на своей бирже за 06.2023–10.2026 (для проверки тикера)."""
    os.makedirs(f"{S205}/candles", exist_ok=True)
    F = load_flags()
    base = {"bithumb": "https://api.bithumb.com/v1/candles/days", "upbit": "https://api.upbit.com/v1/candles/days"}
    keys = set()
    for f in ("keys_s2_k2y.pkl.json", "keys_s117_k_oos.pkl.json"):
        keys |= set(json.load(open(f"{S205}/{f}")))
    todo = sorted({(e, c) for e, c in zip(F.ex, F.coin) if any(p + c in keys for p in PRE)})   # только монеты с перпом
    t0 = time.time()

    def one(item):
        ex, coin = item
        p = f"{S205}/candles/{ex}_{coin}.json"
        if os.path.exists(p):
            return
        out, to = [], "2026-10-20 00:00:00"
        start = "2026-03-01" if ex == "upbit" else "2023-06-01"
        for _ in range(8):
            q = urllib.parse.urlencode({"market": f"KRW-{coin}", "count": 200, "to": to})
            d = get(f"{base[ex]}?{q}")
            if not d or not isinstance(d, list):
                break
            out += [(x["candle_date_time_utc"], x["trade_price"]) for x in d]
            last = d[-1]["candle_date_time_utc"]
            if len(d) < 200 or last[:10] < start:
                break
            to = last.replace("T", " ")
            time.sleep(0.2)
        json.dump(out, open(p, "w"))

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(4) as pool:
        for i, _ in enumerate(pool.map(one, todo)):
            if i % 100 == 0:
                print(f"{i}/{len(todo)} за {time.time() - t0:.0f} с", flush=True)
    print("готово", len(todo), flush=True)


def perp_key(K, coin):
    for p in PRE:
        if p + coin in K:
            return p + coin
    return None


def corr_check(K, ex, coin, s):
    """ρ суточных доходностей монеты на бирже и перпа; None — проверить нельзя."""
    p = f"{S205}/candles/{ex}_{coin}.json"
    if not os.path.exists(p):
        return None
    c = json.load(open(p))
    if len(c) < 20:
        return None
    t = np.array([int(pd.Timestamp(x, tz="UTC").timestamp()) for x, _ in c]) + DAY      # конец суточной свечи
    px = np.array([v for _, v in c], float)
    o = np.argsort(t)
    t, px = t[o], px[o]
    kt = K[s]["t"].astype(np.int64) + 900
    kc = K[s]["c"].astype(float)
    j = np.searchsorted(kt, t, "right") - 1
    ok = (j >= 0) & (kt[np.maximum(j, 0)] > t - 3600)
    if ok.sum() < 20:
        return None
    a, b = np.log(px[ok]), np.log(kc[j[ok]])
    ra, rb = np.diff(a), np.diff(b)
    if len(ra) < 15 or np.std(ra) == 0 or np.std(rb) == 0:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])


def run(per):
    import fastbt as FB  # noqa: E402
    import common182 as C  # noqa: E402
    K = FB.K
    t0, t1 = C.ts(C.PER[per][0]), C.ts(C.PER[per][1])
    F = load_flags()
    F = F[(F.ts >= t0 - 2 * DAY) & (F.ts < t1)].copy()
    F["perp"] = [perp_key(K, c) for c in F.coin]
    F = F[F.perp.notna()].copy()
    rho = {}
    for ex, coin, s in set(zip(F.ex, F.coin, F.perp)):
        rho[(ex, coin)] = corr_check(K, ex, coin, s)
    F["rho"] = [rho[(e, c)] for e, c in zip(F.ex, F.coin)]
    # D и V у той же монеты на той же бирже в ±25 ч
    for typ, other in (("D", "V"), ("V", "D")):
        col = "has" + other
        F[col] = False
        for (ex, coin), g in F.groupby(["ex", "coin"]):
            o = np.sort(g[g.typ == other].ts.values)
            m = g.typ == typ
            if not len(o):
                continue
            ts_ = g[m].ts.values
            j = np.searchsorted(o, ts_ - WIN, "left")
            hit = (j < len(o)) & (o[np.minimum(j, len(o) - 1)] <= ts_ + WIN)
            F.loc[g[m].index, col] = hit
    # у Upbit: D Bithumb в предыдущие 12 ч
    bD = F[(F.ex == "bithumb") & (F.typ == "D")]
    bt = {c: np.sort(g.ts.values) for c, g in bD.groupby("coin")}
    F["bth12"] = [bool(len(bt.get(c, [])) and np.any((bt[c] < ts_) & (bt[c] >= ts_ - 12 * 3600)))
                  if ex == "upbit" else False for ex, c, ts_ in zip(F.ex, F.coin, F.ts)]
    F["entry"] = (np.ceil((F.ts + 900) / 900) * 900).astype(np.int64)
    F = F[(F.entry >= t0) & (F.entry < t1)]
    res = []
    for (ex, typ, s), g in F.groupby(["ex", "typ", "perp"]):
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
        g["r24"] = c[I] / c[I - 96] - 1
        for hold, sl, suf in ((24, 0.25, ""), (48, 0.25, "48")):
            okt, net, stp, bars, tend = FB.trades(s, I, sl, hold, -1)
            g["net" + suf] = np.where(okt, net, np.nan)
            g["stop" + suf] = np.where(okt, stp, False)
            g["tend" + suf] = tend
            g["hed" + suf] = g["net" + suf].values + FB.alt_mv(t[I] + 900, tend)
            g["pl" + suf] = FB.placebo(s, I, sl, hold, -1)
        g["t"] = g.entry
        res.append(g)
    R = pd.concat(res, ignore_index=True)
    R["per"] = per
    R.to_pickle(f"{S205}/trades_{per}.pkl")
    print(per, R[R.net.notna()].groupby(["ex", "typ"]).size().to_dict(),
          "| ρ < 0,5:", int((R.rho < 0.5).sum()), "без проверки:", int(R.rho.isna().sum()), flush=True)


def one_per_coin(x, suf=""):
    """Новая сделка по монете — только после закрытия прошлой (внутри своего набора)."""
    keep = []
    for s, g in x.sort_values("t").groupby("perp"):
        last = -1
        for i, r in zip(g.index, g.itertuples()):
            if r.t >= last:
                keep.append(i)
                last = getattr(r, "tend" + suf)
    return x.loc[keep]


def view(R, mask, suf=""):
    x = R[mask].copy()
    x = x[x["net" + suf].notna()]
    x = one_per_coin(x, suf)
    x["net"], x["hed"], x["pl"], x["stop"] = x["net" + suf], x["hed" + suf], x["pl" + suf], x["stop" + suf]
    x["why"] = np.where(x.stop.astype(bool), "стоп", "время")
    return x


def line(C, x, per, months):
    if len(x) < 5:
        return f"n={len(x)}"
    m, t, n = C.ct(x.net, x.t)
    mh, th, _ = C.ct(x.hed, x.t)
    md, td, _ = C.ct(x.net - x.pl, x.t)
    cut = C.ts(C.PER[per][2])
    return (f"n={n:4d} ({n / months:5.1f}/мес) {m:+.2%} (t {t:+.1f}) | половины {x[x.t < cut].net.mean():+.2%} / "
            f"{x[x.t >= cut].net.mean():+.2%} | с хеджем {mh:+.2%} (t {th:+.1f}) | сверх плацебо {md:+.2%} (t {td:+.1f}) | "
            f"стопов {(x.why == 'стоп').mean():.0%}")


def report():
    import common182 as C  # noqa: E402
    print("s205 — корейский «всплеск депозитов» → шорт перпа Binance 24 ч, стоп 25%, спокойный рынок ±5%\n")
    win = {"2022–2024": ("2023-07-04", "2024-10-01"), "2024–2026": ("2024-10-01", "2026-10-19")}
    pn, ph, pdl = [], [], []
    for per in ("2022–2024", "2024–2026"):
        R = pd.read_pickle(f"{S205}/trades_{per}.pkl")
        R = R[~(R.rho < 0.5)]                                   # ρ < 0,5 — другой токен с тем же тикером
        mo = (C.ts(win[per][1]) - C.ts(win[per][0])) / (30.4 * DAY)
        calm = R.r24.abs() <= 0.05
        bD = (R.ex == "bithumb") & (R.typ == "D")
        bV = (R.ex == "bithumb") & (R.typ == "V") & ~R.hasD
        print(f"== {per} (окно Bithumb {win[per][0]} — {win[per][1]}, {mo:.1f} мес) ==")
        x = view(R, bD & calm)
        print(f"  основной: Bithumb D, спокойный рынок: {line(C, x, per, mo)}")
        print(f"  контроль: Bithumb V без D: {line(C, view(R, bV & calm), per, mo)}")
        print(f"  D без V: {line(C, view(R, bD & calm & ~R.hasV), per, mo)}")
        print(f"  D вместе с V: {line(C, view(R, bD & calm & R.hasV), per, mo)}")
        print(f"  ступень 위험 (30): {line(C, view(R, bD & calm & (R.step == 30)), per, mo)}")
        print(f"  без фильтра рынка: {line(C, view(R, bD & R.r24.notna()), per, mo)}")
        print(f"  48 ч: {line(C, view(R, bD & calm, '48'), per, mo)}")
        y = pd.concat([x.assign(g=1), view(R, bV & calm).assign(g=0)])
        d, se = C.diff(y.net, y.g == 1, y.t)
        pdl.append((d, se, len(y)))
        print(f"  Δ D − V без D: {d:+.2%} (t {d / se:+.1f})")
        m, t, n = C.ct(x.net, x.t)
        mh, th, _ = C.ct(x.hed, x.t)
        pn.append((m, abs(m / t) if t else np.nan, n))
        ph.append((mh, abs(mh / th) if th else np.nan, n))
        if per == "2024–2026":
            cut = C.ts(C.PER[per][2])
            h1, h2 = x[x.t < cut].net.mean(), x[x.t >= cut].net.mean()
            crit = [("≥ 20 в месяц", n / mo >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
                    ("сверх плацебо > 0", (x.net - x.pl).mean() > 0), ("с хеджем > 0", mh > 0)]
            print("  правило владельца: " + "; ".join(f"{k} — {'да' if ok else 'нет'}" for k, ok in crit))
            uD = (R.ex == "upbit") & (R.typ == "D")
            uV = (R.ex == "upbit") & (R.typ == "V") & ~R.hasD
            umo = (C.ts("2026-10-19") - C.ts("2026-03-24")) / (30.4 * DAY)
            print(f"\n  Upbit (24.03–19.10.2026, {umo:.1f} мес; половины — до и после 01.12.2025 не годятся, см. ниже):")
            for nm, msk in (("Upbit D, спокойный рынок", uD & calm), ("Upbit V без D", uV & calm),
                            ("Upbit D без V", uD & calm & ~R.hasV), ("Upbit D после D Bithumb за 12 ч", uD & calm & R.bth12),
                            ("Upbit D без фильтра рынка", uD & R.r24.notna())):
                z = view(R, msk)
                m_, t_, n_ = C.ct(z.net, z.t)
                mh_, th_, _ = C.ct(z.hed, z.t)
                cut2 = C.ts("2026-07-01")
                print(f"    {nm}: n={n_} ({n_ / umo:.1f}/мес) {m_:+.2%} (t {t_:+.1f}) | 03–06 / 07–10: "
                      f"{z[z.t < cut2].net.mean():+.2%} / {z[z.t >= cut2].net.mean():+.2%} | с хеджем {mh_:+.2%} (t {th_:+.1f}) | "
                      f"сверх плацебо {(z.net - z.pl).mean():+.2%}")
        print()
    m, t = C.combine(pn)
    mh, th = C.combine(ph)
    print(f"Два окна, основной: {m:+.2%} (t {t:+.1f}); с хеджем {mh:+.2%} (t {th:+.1f})")
    print("  по окнам: " + " / ".join(f"{a:+.2%}" for a, _, _ in pn) + "; с хеджем " + " / ".join(f"{a:+.2%}" for a, _, _ in ph))
    d, t = C.combine(pdl)
    print(f"Δ D − V без D вместе: {d:+.2%} (t {t:+.1f})")


if __name__ == "__main__":
    if sys.argv[1] == "report":
        report()
    elif sys.argv[1] == "candles":
        candles()
    else:
        run(sys.argv[1])
