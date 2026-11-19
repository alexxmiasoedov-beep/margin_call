#!/usr/bin/env python3
"""s209: описание найденных рядов — глубина, охват, частота событий-кандидатов. Доходы и цены после событий НЕ считаются.

1. Премия Upbit по дням (upbit_premium.py): usdt_real = премия монеты сверх премии USDT, п. п.
   Дневная запись дня D = последнее часовое значение дня D (сверено с часовыми), то есть известна в 24:00 UTC.
2. Hyperliquid по дням (hl_stats.py): HLP-позиция к OI, ликвидации к OI, число уникальных трейдеров монеты.
3. Bithumb, снимок (bithumb_indicators.py): доля 10 крупнейших держателей/трейдеров, держатели, внутренний запас,
   нетто-ввод за 24 ч к запасу.
Окно частот — 10.2024–09.2026 (как «2024–2026» в журналах), для Hyperliquid — 10.2024–03.2026 (ряд кончается 03.04.2026).
"""
import collections, csv, glob, gzip, json, os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common209 import perp_bases

D = "/home/user/mc_data/s209"


def months(a, b):
    y, m = int(a[:4]), int(a[5:7])
    n = 0
    while f"{y:04d}-{m:02d}" <= b:
        n += 1
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return n


def first_in(series, cond, gap_days=7):
    """series: список (дата, значение) по возрастанию; новое событие — cond и не было cond за gap_days."""
    out, last = [], None
    from datetime import date
    for d, v in series:
        if v is None:
            continue
        if cond(v):
            dd = date.fromisoformat(d[:10])
            if last is None or (dd - last).days > gap_days:
                out.append(d[:10])
            last = dd
    return out


def pct(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, int(q * len(v)))] if v else None


def upbit_premium():
    print("== 1. Премия Upbit (дни)")
    rows = collections.defaultdict(list)
    with gzip.open(f"{D}/upbit_premium_DAYS_1.csv.gz", "rt") as f:
        for r in csv.DictReader(f):
            if r["usdt_real"] in ("", "None"):
                continue
            rows[r["market"]].append((r["time_utc"], float(r["usdt_real"]), float(r["disparity"]),
                                      float(r["usdt_disparity"])))
    allv = [x[1] for L in rows.values() for x in L if "2024-10" <= x[0][:7] <= "2026-09"]
    print("монет", len(rows), "монето-суток 10.2024–09.2026:", len(allv))
    print("usdt_real: медиана %.2f, p5 %.2f, p95 %.2f, p99 %.2f" % (statistics.median(allv), pct(allv, .05),
                                                                     pct(allv, .95), pct(allv, .99)))
    usdt = sorted({(x[0], x[3]) for L in rows.values() for x in L})
    uv = [v for d, v in usdt if "2024-10" <= d[:7] <= "2026-09"]
    print("премия USDT (общая): медиана %.2f%%, мин %.2f, макс %.2f" % (statistics.median(uv), min(uv), max(uv)))
    nm = months("2024-10", "2026-09")
    for thr in (3, 5, 10):
        ev = sum(len([d for d in first_in(sorted((x[0], x[1]) for x in L), lambda v: v >= thr)
                      if "2024-10" <= d[:7] <= "2026-09"]) for L in rows.values())
        evn = sum(len([d for d in first_in(sorted((x[0], x[1]) for x in L), lambda v: v <= -thr)
                       if "2024-10" <= d[:7] <= "2026-09"]) for L in rows.values())
        print(f"  новые эпизоды usdt_real ≥ +{thr} п. п.: {ev} ({ev/nm:.1f} в мес.); ≤ −{thr}: {evn} ({evn/nm:.1f} в мес.)")


def load_hl(name):
    return json.load(gzip.open(f"{D}/hl/{name}.json.gz"))["chart_data"]


def hyperliquid():
    print("== 2. Hyperliquid (дни)")
    perps = perp_bases()
    oi = {(r["coin"], r["time"][:10]): r["open_interest"] for r in load_hl("open_interest")}
    hp = {(r["coin"], r["time"][:10]): r["daily_ntl"] for r in load_hl("hlp_positions")}
    lq = {(r["coin"], r["time"][:10]): r["daily_notional_liquidated"] for r in load_hl("daily_notional_liquidated_by_coin")}
    uu = {(r["coin"], r["time"][:10]): r["daily_unique_users"] for r in load_hl("daily_unique_users_by_coin")}
    coins = sorted({c for c, d in oi if c in perps or c.lstrip("k") in perps})
    print("монет с перпом Binance:", len(coins))
    w0, w1 = "2024-10", "2026-03"
    nm = months(w0, w1)
    days = sorted({d for c, d in oi})
    print("даты", days[0], "…", days[-1])
    # покрытие: монеты с OI ≥ 1 млн $ в среднем по окну
    ok = []
    for c in coins:
        v = [oi.get((c, d)) for d in days if w0 <= d[:7] <= w1 and oi.get((c, d))]
        if v and statistics.median(v) >= 1e6:
            ok.append(c)
    print("из них с медианным OI ≥ 1 млн $ в 10.2024–03.2026:", len(ok))
    ratios = []
    for c in ok:
        for d in days:
            o, h = oi.get((c, d)), hp.get((c, d))
            if o and h is not None and w0 <= d[:7] <= w1 and o > 0:
                ratios.append(h / o)
    print("HLP/OI: медиана |x| %.4f, p90 %.4f, p99 %.4f" % (pct([abs(x) for x in ratios], .5),
                                                            pct([abs(x) for x in ratios], .9),
                                                            pct([abs(x) for x in ratios], .99)))
    for thr in (0.02, 0.05, 0.10):
        evs = evl = 0
        for c in ok:
            s = sorted((d, (hp.get((c, d)) or 0) / oi[(c, d)]) for d in days
                       if oi.get((c, d)) and w0 <= d[:7] <= w1)
            evs += len(first_in(s, lambda v: v <= -thr))
            evl += len(first_in(s, lambda v: v >= thr))
        print(f"  HLP в шорте ≥ {thr:.0%} OI (толпа в лонге): {evs} ({evs/nm:.1f} в мес.); "
              f"HLP в лонге ≥ {thr:.0%}: {evl} ({evl/nm:.1f} в мес.)")
    for thr in (0.05, 0.10, 0.20):
        ev = 0
        for c in ok:
            s = sorted((d, (lq.get((c, d)) or 0) / oi[(c, d)]) for d in days if oi.get((c, d)) and w0 <= d[:7] <= w1)
            ev += len(first_in(s, lambda v: v >= thr))
        print(f"  ликвидации за сутки ≥ {thr:.0%} OI: {ev} ({ev/nm:.1f} в мес.)")
    for k in (3, 5):
        ev = 0
        for c in ok:
            s = []
            hist = []
            for d in days:
                u = uu.get((c, d))
                if u is None:
                    continue
                base = statistics.median(hist[-7:]) if len(hist) >= 7 else None
                if w0 <= d[:7] <= w1 and base:
                    s.append((d, u / base if u >= 100 else 0))
                hist.append(u)
            ev += len(first_in(s, lambda v: v >= k))
        print(f"  всплеск трейдеров монеты ×{k} к медиане 7 сут (≥ 100 трейдеров): {ev} ({ev/nm:.1f} в мес.)")


def bithumb():
    print("== 3. Bithumb, снимок")
    fs = sorted(glob.glob(f"{D}/bithumb/snap_*.json.gz"))
    if not fs:
        print("нет снимка")
        return
    s = json.load(gzip.open(fs[-1], "rt"))
    print("файл", os.path.basename(fs[-1]), "время", s["utc"], "монет", len(s["coins"]))
    th, tt, ho, nd = [], [], [], []
    for ct, d in s["coins"].items():
        try:
            th.append(float(d["top_hold"]["holdingPercentage"]))
        except Exception:
            pass
        try:
            tt.append(float(d["top_trade"]["tradingPercentage"]))
        except Exception:
            pass
        try:
            ho.append(int(d["holders"]["numberOfHolders"]))
        except Exception:
            pass
        try:
            sup = float(d["supply"]["accumulationDepositAmt"])
            net = float(d["netdep"]["purityDeposit"])
            if sup > 0:
                nd.append(net / sup)
        except Exception:
            pass
    for name, v in (("доля 10 держателей, %", th), ("доля 10 трейдеров, %", tt), ("держателей", ho),
                    ("нетто-ввод 24 ч / запас", nd)):
        if v:
            print(f"  {name}: n {len(v)}, медиана {statistics.median(v):.4g}, p10 {pct(v, .1):.4g}, p90 {pct(v, .9):.4g}")
    w7 = [d["wealthy"] for d in s["coins"].values() if isinstance(d.get("wealthy"), dict)]
    lens = collections.Counter(len(x.get("investList") or []) for x in w7)
    print("  wealthy/stat: длина ряда investList", dict(lens))


def hl_halves():
    """Частоты Г1 и Г2 по половинам 10.2024–06.2025 и 07.2025–03.2026, плюс проверка знака HLP
    по ценовому ходу ТОГО ЖЕ дня (описание, не доход после события)."""
    print("== 2б. Hyperliquid: частоты по половинам и знак ряда HLP")
    perps = perp_bases()
    oi = {(r["coin"], r["time"][:10]): r["open_interest"] for r in load_hl("open_interest")}
    hp = {(r["coin"], r["time"][:10]): r["daily_ntl"] for r in load_hl("hlp_positions")}
    uu = {(r["coin"], r["time"][:10]): r["daily_unique_users"] for r in load_hl("daily_unique_users_by_coin")}
    ac = {(r["coin"], r["time"][:10]): r for r in load_hl("asset_ctxs")}
    days = sorted({x for c, x in oi})
    coins = sorted({c for c, x in oi if c in perps or c.lstrip("k") in perps})
    ok = [c for c in coins if (lambda v: v and statistics.median(v) >= 1e6)(
        [oi[(c, x)] for x in days if "2024-10" <= x[:7] <= "2026-03" and oi.get((c, x))])]
    halves = (("2024-10", "2025-06"), ("2025-07", "2026-03"))
    for thr in (0.01, 0.015, 0.02):
        out = []
        for w0, w1 in halves:
            n = 0
            for c in ok:
                s = sorted((x, (hp.get((c, x)) or 0) / oi[(c, x)]) for x in days if oi.get((c, x)) and w0 <= x[:7] <= w1)
                n += len(first_in(s, lambda v: v <= -thr))
            out.append(f"{w0}…{w1}: {n} ({n/months(w0, w1):.1f} в мес.)")
        print(f"  Г1 HLP в шорте ≥ {thr:.1%} OI: " + "; ".join(out))
    for k in (2.5, 3):
        out = []
        for w0, w1 in halves:
            n = 0
            for c in ok:
                hist, s = [], []
                for x in days:
                    u = uu.get((c, x))
                    if u is None:
                        continue
                    base = statistics.median(hist[-7:]) if len(hist) >= 7 else None
                    if w0 <= x[:7] <= w1 and base:
                        s.append((x, u / base if u >= 100 else 0))
                    hist.append(u)
                n += len(first_in(s, lambda v: v >= k))
            out.append(f"{w0}…{w1}: {n} ({n/months(w0, w1):.1f} в мес.)")
        print(f"  Г2 трейдеров ×{k} к медиане 7 сут: " + "; ".join(out))
    xs, ys = [], []
    for key, v in hp.items():
        a, o = ac.get(key), oi.get(key)
        if not a or not o or o < 1e6 or not a.get("first_oracle_px") or key[1] < "2024-10":
            continue
        xs.append(v / o)
        ys.append(a["last_oracle_px"] / a["first_oracle_px"] - 1)
    up = [x for x, y in zip(xs, ys) if y > 0.10]
    dn = [x for x, y in zip(xs, ys) if y < -0.10]
    print(f"  знак: дней с ходом цены дня > +10%: {len(up)}, из них HLP < 0 — {sum(1 for x in up if x < 0)/len(up):.0%}; "
          f"дней < −10%: {len(dn)}, HLP < 0 — {sum(1 for x in dn if x < 0)/len(dn):.0%}; "
          f"всех монето-суток HLP < 0 — {sum(1 for x in xs if x < 0)/len(xs):.0%}")
    for coin, dd in (("ETH", "2025-03-12"), ("POPCAT", "2025-11-12"), ("JELLY", "2025-03-26")):
        print(f"  эпизод {coin} {dd}: HLP {hp.get((coin, dd))}, OI {oi.get((coin, dd))}")


if __name__ == "__main__":
    upbit_premium()
    hyperliquid()
    hl_halves()
    bithumb()
