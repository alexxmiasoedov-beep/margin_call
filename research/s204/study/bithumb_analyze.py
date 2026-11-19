#!/usr/bin/env python3
"""s204: описание истории «경보제» Bithumb (без доходов после события).

Вход: /home/user/mc_data/s204/bithumb_hist.csv (bithumb_history.py; время KST),
      /home/user/mc_data/s204/web/bithumb_site/intro.json (coinType -> тикер, в т.ч. снятые монеты),
      /home/user/mc_data/s204/raw/www_fapi_exchangeInfo.json (перпы Binance),
      /home/user/mc_data/s204/upbit_days_D.csv (для сравнения с Upbit).
Выход: печать (bithumb_analyze.log), /home/user/mc_data/s204/bithumb_events_<тип>.csv
Коды: 01 цена (P), 02 объём (V), 03 депозиты (D), 04 разница с CMC (G), 05 концентрация счетов (C);
шаг 10/20/30 — 주의/경고/위험 (для цены — рост, для G — выше CMC), 11/21/31 — падение / ниже CMC.
"""
import csv, json, collections, statistics
from datetime import datetime, timedelta

OUT = "/home/user/mc_data/s204"
NAME = {"01": "P", "02": "V", "03": "D", "04": "G", "05": "C"}


def perps():
    d = json.load(open(OUT + "/raw/www_fapi_exchangeInfo.json"))
    out = {}
    for s in d["symbols"]:
        if s.get("contractType") != "PERPETUAL" or s.get("quoteAsset") != "USDT" or s.get("underlyingType") != "COIN":
            continue
        b = s["baseAsset"]
        for pre in ("1000000", "10000", "1000", "1M"):
            if b.startswith(pre) and len(b) > len(pre):
                b = b[len(pre):]
                break
        on = datetime(1970, 1, 1) + timedelta(milliseconds=s["onboardDate"])
        if b not in out or on < out[b][1]:
            out[b] = (s["symbol"], on)
    return out


def main():
    sym = {c["coinType"]: c["coinSymbol"] for c in json.load(open(OUT + "/web/bithumb_site/intro.json"))["data"]["coinList"]}
    P = perps()
    R, seen = [], set()
    for fn in ("bithumb_hist.csv", "bithumb_hist_L2.csv", "bithumb_hist_L3.csv"):   # уровни 1, 2, 3
        try:
            for r in csv.DictReader(open(f"{OUT}/{fn}")):
                key = (r["coinType"], r["warningType"], r["warningStep"], r["startDateTime"])
                if key not in seen:
                    seen.add(key)
                    R.append(r)
        except FileNotFoundError:
            print("нет файла", fn)
    for r in R:
        r["s"] = datetime.strptime(r["startDateTime"], "%Y-%m-%d %H:%M:%S") - timedelta(hours=9)   # UTC
        # у ещё действующих предупреждений конца нет — считаем сутки
        r["e"] = (datetime.strptime(r["endDateTime"], "%Y-%m-%d %H:%M:%S") - timedelta(hours=9)
                  if r["endDateTime"] else r["s"] + timedelta(hours=24))
        r["k"] = NAME.get(r["warningType"], r["warningType"])
        r["coin"] = sym.get(r["coinType"], "?" + r["coinType"])
    print("записей", len(R), "без тикера", sum(1 for r in R if r["coin"].startswith("?")),
          "период", min(r["s"] for r in R), "—", max(r["s"] for r in R), "(UTC)")
    months = sorted({r["s"].strftime("%Y-%m") for r in R})
    print("\n1. Записи по месяцам (тип: всего [шаги])")
    for k in "DVCPG":
        c = collections.Counter(r["s"].strftime("%Y-%m") for r in R if r["k"] == k)
        if not c:
            continue
        print(k, " ".join(f"{m[2:]}:{c[m]}" for m in months if c[m]))
        st = collections.Counter(r["warningStep"] for r in R if r["k"] == k)
        print("   шаги:", dict(sorted(st.items())))
    print("\n2. Время начала суточных флагов (UTC) по кварталам")
    for k in "DVC":
        q = collections.defaultdict(collections.Counter)
        for r in R:
            if r["k"] == k:
                q[f"{r['s'].year}Q{(r['s'].month - 1) // 3 + 1}"][r["s"].strftime("%H:%M")] += 1
        for kk in sorted(q):
            print(k, kk, q[kk].most_common(3))
    # смена расписания: первая и последняя дата каждого времени начала
    for k in "DV":
        first = {}
        last = {}
        for r in sorted((r for r in R if r["k"] == k), key=lambda r: r["s"]):
            hm = r["s"].strftime("%H:%M")
            first.setdefault(hm, r["s"])
            last[hm] = r["s"]
        print(k, "время начала: первое/последнее появление",
              {hm: (first[hm].strftime("%Y-%m-%d"), last[hm].strftime("%Y-%m-%d"), ) for hm in sorted(first, key=lambda h: first[h])})
        steps_first = {}
        for r in sorted((r for r in R if r["k"] == k), key=lambda r: r["s"]):
            steps_first.setdefault(r["warningStep"], r["s"].strftime("%Y-%m-%d"))
        print(k, "первое появление шага", steps_first)
    print("\n3. Длительность (ч)")
    for k in "DVCPG":
        dur = [(r["e"] - r["s"]).total_seconds() / 3600 for r in R if r["k"] == k]
        if dur:
            print(k, "медиана", round(statistics.median(dur), 2), collections.Counter(round(x, 1) for x in dur).most_common(5))
    print("\n4. Суточные флаги: эпизоды и перпы Binance")
    for k in "DVC":
        best = {}
        for r in R:
            if r["k"] != k:
                continue
            key = (r["coin"], r["s"])
            if key not in best or r["warningStep"] > best[key]["warningStep"]:
                best[key] = r
        evs = sorted(best.values(), key=lambda r: (r["coin"], r["s"]))
        rows = []
        prev = {}
        for r in evs:
            p = prev.get(r["coin"])
            new = p is None or (r["s"] - p) > timedelta(hours=25)
            prev[r["coin"]] = r["s"]
            pp = P.get(r["coin"])
            perp = bool(pp and pp[1] <= r["s"] - timedelta(days=1))
            rows.append((r["coin"], r["s"].strftime("%Y-%m-%d %H:%M"), r["e"].strftime("%Y-%m-%d %H:%M"),
                         r["warningStep"], int(new), int(perp), pp[0] if pp else ""))
        rows.sort(key=lambda x: x[1])
        if not rows:
            print(k, "записей нет")
            continue
        with open(f"{OUT}/bithumb_events_{k}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["coin", "start_utc", "end_utc", "step", "new_episode", "binance_perp_1d", "perp_symbol"])
            w.writerows(rows)
        new = [x for x in rows if x[4]]
        newp = [x for x in new if x[5]]
        bym = collections.Counter(x[1][:7] for x in new)
        bymp = collections.Counter(x[1][:7] for x in newp)
        span_days = (datetime.strptime(rows[-1][1], "%Y-%m-%d %H:%M") - datetime.strptime(rows[0][1], "%Y-%m-%d %H:%M")).days + 1
        print(f"{k}: записей {len(rows)}, новых эпизодов {len(new)}, с перпом {len(newp)}; монет {len({x[0] for x in rows})}, "
              f"с перпом {len({x[0] for x in rows if x[5]})}; в среднем новых с перпом {len(newp) / span_days * 30.44:.0f} в месяц")
        print("   по месяцам (новые / с перпом):", ", ".join(f"{m[2:]}:{bym[m]}/{bymp[m]}" for m in sorted(bym)))
        if k == "D":
            st = collections.Counter((x[1][:4], x[3]) for x in newp)
            print("   новые с перпом по годам и шагам:", dict(sorted(st.items())))
    # 5. совпадение с Upbit D (24.03–19.11.2026)
    print("\n5. Upbit D против Bithumb D (новые эпизоды, 24.03–19.11.2026)")
    U = [x for x in csv.DictReader(open(OUT + "/upbit_days_D.csv")) if x["new_episode"] == "1"]
    B = collections.defaultdict(list)
    for x in csv.DictReader(open(f"{OUT}/bithumb_events_D.csv")):
        B[x["coin"]].append(datetime.strptime(x["start_utc"], "%Y-%m-%d %H:%M"))
    bins = collections.Counter()
    nU = 0
    for x in U:
        tU = datetime.fromisoformat(x["day"]) + timedelta(hours=1)
        nU += 1
        lag = [(tB - tU).total_seconds() / 3600 for tB in B.get(x["coin"], []) if abs((tB - tU).total_seconds()) <= 48 * 3600]
        if not lag:
            bins["нет в ±48 ч"] += 1
        else:
            l = min(lag, key=abs)
            bins["Bithumb раньше" if l < 0 else "Bithumb позже/одновременно"] += 1
            bins[f"разница {int(l // 8) * 8:+d}…{int(l // 8) * 8 + 8:+d} ч"] += 1
    print("Upbit D новых:", nU, dict(sorted(bins.items())))
    bth = [(c, t) for c, ts in B.items() for t in ts if datetime(2026, 3, 24) <= t <= datetime(2026, 11, 19)]
    Uday = collections.defaultdict(list)
    for x in csv.DictReader(open(OUT + "/upbit_days_D.csv")):
        Uday[x["coin"]].append(datetime.fromisoformat(x["day"]) + timedelta(hours=1))
    hit = sum(1 for c, t in bth if any(abs((u - t).total_seconds()) <= 48 * 3600 for u in Uday.get(c, [])))
    print(f"Bithumb D (все записи) за тот же период: {len(bth)}, из них с Upbit D в ±48 ч: {hit} ({hit / max(1, len(bth)):.0%})")


if __name__ == "__main__":
    main()
