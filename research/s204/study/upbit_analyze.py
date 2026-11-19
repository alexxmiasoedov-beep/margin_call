#!/usr/bin/env python3
"""s204: описание истории флагов Upbit (без доходов после события).

Вход: /home/user/mc_data/s204/upbit_mer_KRW.csv (upbit_history.py),
      /home/user/mc_data/s204/raw/www_fapi_exchangeInfo.json (список перпов Binance, www.binance.com/fapi/v1/exchangeInfo).
Выход: печать в upbit_analyze.log и таблицы /home/user/mc_data/s204/upbit_days_<тип>.csv
  (монета × сутки флага: уровень, перп Binance, новый эпизод).

Обозначения: V — TRADING_VOLUME_SOARING, D — DEPOSIT_AMOUNT_SOARING, C — CONCENTRATION_OF_SMALL_ACCOUNTS,
P — PRICE_FLUCTUATIONS, G — GLOBAL_PRICE_DIFFERENCES; LEVEL_1/2/3 = 주의/경고/위험.
"""
import csv, json, collections, statistics
from datetime import datetime, timedelta

SRC = "/home/user/mc_data/s204/upbit_mer_KRW.csv"
FAPI = "/home/user/mc_data/s204/raw/www_fapi_exchangeInfo.json"
OUT = "/home/user/mc_data/s204"
SHORT = {"TRADING_VOLUME_SOARING": "V", "DEPOSIT_AMOUNT_SOARING": "D", "CONCENTRATION_OF_SMALL_ACCOUNTS": "C",
         "PRICE_FLUCTUATIONS": "P", "GLOBAL_PRICE_DIFFERENCES": "G"}
DAILY = ("V", "D", "C")
T0 = datetime(2026, 3, 24)          # первый суточный пакет 24.03 01:00 UTC
T1 = datetime(2026, 11, 19, 1, 0)   # последний суточный пакет в выгрузке


def ts(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def perps():
    """база тикера -> (символ, время запуска) для бессрочных USDT-M по монетам (TRADING или SETTLING)."""
    d = json.load(open(FAPI))
    out = {}
    for s in d["symbols"]:
        if s.get("contractType") != "PERPETUAL" or s.get("quoteAsset") != "USDT" or s.get("underlyingType") != "COIN":
            continue
        b = s["baseAsset"]
        for pre in ("1000000", "10000", "1000", "1M"):
            if b.startswith(pre) and len(b) > len(pre):
                b = b[len(pre):]
                break
        on = datetime.utcfromtimestamp(s["onboardDate"] / 1000)
        if b not in out or on < out[b][1]:
            out[b] = (s["symbol"], on, s["status"])
    return out


def main():
    R = list(csv.DictReader(open(SRC)))
    P = perps()
    print("записей", len(R), "перпов Binance (монеты, USDT)", len(P))
    for r in R:
        r["t"] = ts(r["triggerTimeUtc"])
        r["e"] = ts(r["expirationTimeUtc"]) if r["expirationTimeUtc"] else None
        r["k"] = SHORT[r["eventType"]]
        r["coin"] = r["code"].split("-", 1)[1]
    # 1. записи по месяцам и уровням
    print("\n1. Записи по месяцам (тип: L1/L2/L3)")
    c = collections.Counter((r["k"], r["triggerTimeUtc"][:7], r["warningLevel"][-1]) for r in R)
    months = sorted({r["triggerTimeUtc"][:7] for r in R})
    for k in "DVCPG":
        print(k, " ".join(f"{m[2:]}:{c[(k, m, '1')]}/{c[(k, m, '2')]}/{c[(k, m, '3')]}" for m in months))
    # 2. время срабатывания
    print("\n2. Время срабатывания (UTC, ЧЧ:ММ) — пять самых частых")
    for k in "DVCPG":
        tt = collections.Counter(r["triggerTimeUtc"][11:16] for r in R if r["k"] == k)
        sec = collections.Counter(r["triggerTimeUtc"][17:19] == "00" for r in R if r["k"] == k)
        print(k, tt.most_common(5), "доля ровных секунд", round(sec[True] / max(1, sum(sec.values())), 3))
    # 3. длительность суточных флагов
    print("\n3. Длительность суточных записей (ч)")
    for k in DAILY:
        dur = collections.Counter(round((r["e"] - r["t"]).total_seconds() / 3600, 1) for r in R if r["k"] == k and r["e"])
        print(k, dur.most_common(6))
    # 4. сутки флага: монета × день (01:00 UTC); запись 48 ч = два дня; запись 0 ч (24.03–10.05) = один день
    print("\n4. Монето-сутки суточных флагов, эпизоды, перпы")
    for k in DAILY:
        days = {}
        for r in R:
            if r["k"] != k:
                continue
            n = max(1, round((r["e"] - r["t"]).total_seconds() / 86400)) if r["e"] else 1
            for i in range(n):
                d = (r["t"] + timedelta(days=i)).date()
                lv = int(r["warningLevel"][-1])
                if (r["coin"], d) not in days or days[(r["coin"], d)] < lv:
                    days[(r["coin"], d)] = lv
        rows = []
        for (coin, d), lv in sorted(days.items(), key=lambda x: (x[0][1], x[0][0])):
            new = (coin, d - timedelta(days=1)) not in days
            p = P.get(coin)
            flag_t = datetime(d.year, d.month, d.day, 1, 0)
            has_perp = bool(p and p[1] <= flag_t - timedelta(days=1))
            rows.append((coin, d.isoformat(), lv, int(new), int(has_perp), p[0] if p else ""))
        with open(f"{OUT}/upbit_days_{k}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["coin", "day", "level", "new_episode", "binance_perp_1d", "perp_symbol"])
            w.writerows(rows)
        ndays = (T1.date() - T0.date()).days + 1
        tot = len(rows)
        new = [x for x in rows if x[3]]
        newp = [x for x in new if x[4]]
        print(f"{k}: монето-суток {tot}, суток в выгрузке {ndays}, в среднем {tot / ndays:.1f} в сутки; "
              f"новых эпизодов {len(new)} ({len(new) / ndays * 30.44:.0f} в месяц), с перпом Binance {len(newp)} "
              f"({len(newp) / ndays * 30.44:.0f} в месяц); монет {len({x[0] for x in rows})}, "
              f"с перпом {len({x[0] for x in rows if x[4]})}")
        bylv = collections.Counter(x[2] for x in newp)
        print(f"   новые с перпом по уровням: L1 {bylv[1]}, L2 {bylv[2]}, L3 {bylv[3]}")
        bym = collections.Counter(x[1][:7] for x in newp)
        bym_all = collections.Counter(x[1][:7] for x in new)
        print("   по месяцам (новые всего / с перпом):", ", ".join(f"{m}: {bym_all[m]}/{bym[m]}" for m in sorted(bym_all)))
        runs = collections.Counter()
        # длина серий подряд идущих дней
        for x in new:
            coin = x[0]
            d = datetime.fromisoformat(x[1]).date()
            L = 0
            while (coin, d + timedelta(days=L)) in days:
                L += 1
            runs[min(L, 5)] += 1
        print("   длина серии (сут, 5 = 5+):", sorted(runs.items()))
        if k == "D":
            per_day = collections.Counter(x[1] for x in rows if x[4])
            vals = [per_day.get((T0.date() + timedelta(days=i)).isoformat(), 0) for i in range(ndays)]
            print("   D с перпом в сутки: медиана", statistics.median(vals), "среднее", round(sum(vals) / ndays, 2),
                  "макс", max(vals), "суток без D с перпом", sum(1 for v in vals if v == 0))
            top = collections.Counter(x[0] for x in rows if x[4]).most_common(15)
            print("   чаще всех (монето-сутки с перпом):", top)
    # 5. совпадения D с V, C, P за те же сутки
    print("\n5. Совпадения у новых эпизодов D (монета, сутки флага)")
    dV = {(r["coin"], r["t"].date()) for r in R if r["k"] == "V"}
    dC = {(r["coin"], r["t"].date()) for r in R if r["k"] == "C"}
    # P в предыдущие 24 ч до 01:00 флага (окно, которое D и меряет)
    Pt = collections.defaultdict(list)
    for r in R:
        if r["k"] == "P":
            Pt[r["coin"]].append(r["t"])
    Gt = collections.defaultdict(list)
    for r in R:
        if r["k"] == "G":
            Gt[r["coin"]].append(r["t"])
    newD = [x for x in csv.DictReader(open(f"{OUT}/upbit_days_D.csv")) if x["new_episode"] == "1"]
    n = len(newD)
    cv = sum(1 for x in newD if (x["coin"], datetime.fromisoformat(x["day"]).date()) in dV)
    cc = sum(1 for x in newD if (x["coin"], datetime.fromisoformat(x["day"]).date()) in dC)
    def win(lst, d, h0, h1):
        t = datetime.fromisoformat(d) + timedelta(hours=1)
        return any(t - timedelta(hours=h0) <= u < t - timedelta(hours=h1) for u in lst)
    cp = sum(1 for x in newD if win(Pt[x["coin"]], x["day"], 25, 1))
    cg = sum(1 for x in newD if win(Gt[x["coin"]], x["day"], 25, 1))
    print(f"новых D {n}: с V в те же сутки {cv} ({cv / n:.0%}), с C {cc} ({cc / n:.0%}), "
          f"с P в окне 24 ч до расчёта {cp} ({cp / n:.0%}), с G {cg} ({cg / n:.0%})")
    # 6. P и G: эпизоды (склейка записей одной монеты с разрывом <= 5 мин)
    print("\n6. Внутридневные флаги P и G: эпизоды (склейка соседних записей, разрыв ≤ 5 мин)")
    for k in ("P", "G"):
        recs = sorted([r for r in R if r["k"] == k and r["e"]], key=lambda r: (r["coin"], r["t"]))
        eps = []
        for r in recs:
            if eps and eps[-1]["coin"] == r["coin"] and r["t"] <= eps[-1]["e"] + timedelta(minutes=5):
                eps[-1]["e"] = max(eps[-1]["e"], r["e"])
                eps[-1]["lv"] = max(eps[-1]["lv"], int(r["warningLevel"][-1]))
                eps[-1]["n"] += 1
            else:
                eps.append({"coin": r["coin"], "t": r["t"], "e": r["e"], "lv": int(r["warningLevel"][-1]), "n": 1})
        durm = sorted((e["e"] - e["t"]).total_seconds() / 60 for e in eps)
        q = lambda p: durm[int(p * (len(durm) - 1))]
        hours = collections.Counter(e["t"].hour for e in eps)
        print(f"{k}: эпизодов {len(eps)}, монет {len({e['coin'] for e in eps})}; длительность мин: медиана {q(.5):.0f}, "
              f"квартили {q(.25):.0f}–{q(.75):.0f}, 90% {q(.9):.0f}; уровни макс: "
              f"{collections.Counter(e['lv'] for e in eps)}; записей на эпизод в среднем {sum(e['n'] for e in eps) / len(eps):.1f}")
        print("   час начала (UTC):", [hours[h] for h in range(24)])
        with open(f"{OUT}/upbit_episodes_{k}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["coin", "start_utc", "end_utc", "max_level", "n_records", "binance_perp"])
            for e in eps:
                p = P.get(e["coin"])
                w.writerow([e["coin"], e["t"], e["e"], e["lv"], e["n"], int(bool(p and p[1] <= e["t"] - timedelta(days=1)))])


if __name__ == "__main__":
    main()
