"""s286 — насколько OI на экспирации Deribit «знает будущее»: объём сделок по истекающим опционам за последние 24 и 8 ч
до 08:00 UTC против OI на экспирации (изучение; доходы и «куда пошла цена» не считаются).

OI каждого опциона на экспирации — из записей расчёта (s157: drb_settle_<CUR>.json — delivery, drb_all_<CUR>_recent.json —
exercise). В него входят и позиции, открытые в последние часы, — это заглядывание вперёд для любого входа до 08:00.
Граница: OI(T − h) по страйку лежит в [OI(T) − V_h, OI(T) + V_h], V_h — объём сделок по этому опциону за [T − h, T]
(history.deribit.com, публично, без ключа). Считаем долю V_h / OI(T) и «max pain» на трёх вариантах OI.

Запуск: python3 -I deribit_late.py [CUR ...]  (по умолчанию BTC ETH); итог — /home/user/mc_data/s286/drb_late.csv,
сырые суммы по опционам — /dev/shm/s286/drb_late/*.json (докачка с места остановки)."""
import collections
import datetime as dt
import json
import os
import sys
import time
import urllib.request

UA = {"User-Agent": "research-script/1.0"}
S157 = "/home/user/mc_data/s157"
TMP = "/dev/shm/s286/drb_late"
OUT = os.environ.get("DRB_OUT", "/home/user/mc_data/s286/drb_late.csv")
os.makedirs(TMP, exist_ok=True)
T_FROM = "2020-10-01"


def get(url, tries=6):
    err = None
    for k in range(tries):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
        except Exception as e:
            err = e
            time.sleep(2 * (k + 1))
    raise RuntimeError(f"{url}: {err}")


def settle_oi(cur):
    """{expiry code: {(strike, C/P): OI, ...}, 't': ms, 'S': index}"""
    recs = json.load(open(f"{S157}/drb_settle_{cur}.json"))
    recs += [x for x in json.load(open(f"{S157}/drb_all_{cur}_recent.json")) if x["type"] == "exercise"]
    E = collections.defaultdict(lambda: {"oi": collections.defaultdict(float), "t": None, "S": None})
    for x in recs:
        n = x.get("instrument_name") or ""
        if n.count("-") != 3:
            continue
        c, e, k, cp = n.split("-")
        g = E[e]
        g["oi"][(float(k), cp)] += x.get("position") or 0.0
        g["t"], g["S"] = x["timestamp"], x["index_price"]
    return E


def max_pain(oi):
    ks = sorted({k for k, _ in oi})
    if not ks:
        return None

    def pay(P):
        return sum(v * (max(P - k, 0) if cp == "C" else max(k - P, 0)) for (k, cp), v in oi.items())
    return min(ks, key=pay)


def late_volume(cur, exp, t_ms, hours=24):
    """Объём по каждому опциону экспирации exp за [T − hours, T] и за [T − 8 ч, T]."""
    fn = f"{TMP}/{cur}_{exp}.json"
    if os.path.exists(fn):
        return json.load(open(fn))
    st, en = t_ms - hours * 3600_000, t_ms
    v24, v8, n_req, seen, cursor = collections.Counter(), collections.Counter(), 0, set(), st
    tag = f"-{exp}-"
    while True:
        u = (f"https://history.deribit.com/api/v2/public/get_last_trades_by_currency_and_time?currency={cur}"
             f"&kind=option&start_timestamp={cursor}&end_timestamp={en}&count=1000&sorting=asc")
        r = get(u)["result"]
        n_req += 1
        tr = r["trades"]
        new = [x for x in tr if x["trade_id"] not in seen]
        for x in new:
            seen.add(x["trade_id"])
            if tag in x["instrument_name"]:
                key = x["instrument_name"].split(tag)[1]  # "<strike>-<C|P>"
                v24[key] += x["amount"]
                if x["timestamp"] >= en - 8 * 3600_000:
                    v8[key] += x["amount"]
        if not r.get("has_more") or not tr:
            break
        last = tr[-1]["timestamp"]
        cursor = last if new else last + 1
        time.sleep(0.15)
    res = {"v24": v24, "v8": v8, "n_trades_all": len(seen), "n_req": n_req}
    json.dump(res, open(fn, "w"))
    return res


def main(curs):
    exps = json.load(open(f"{S157}/expiries.json"))
    rows = []
    if os.path.exists(OUT):
        rows = [ln.rstrip("\n").split(",") for ln in open(OUT)][1:]
    done = {(r[0], r[1]) for r in rows}
    hdr = ("cur,exp,type,t,S,oi,v24,v8,share24,share8,mp,mp_minus24,mp_plus24,mp_minus8,mp_plus8,"
           "oi_near5,v24_near5,n_trades_all")
    for cur in curs:
        E = settle_oi(cur)
        todo = [x for x in exps if x["cur"] == cur and x["t"] >= T_FROM
                and (x["type"] in ("M", "Q") or (cur == "BTC" and x["type"] == "W"))]
        todo.sort(key=lambda x: x["t"])
        t0 = time.time()
        for i, x in enumerate(todo):
            if (cur, x["exp"]) in done:
                continue
            g = E.get(x["exp"])
            if not g or not g["oi"]:
                continue
            lv = late_volume(cur, x["exp"], g["t"])
            oi = g["oi"]
            def vol(key, k, cp):
                return lv[key].get(f"{int(k) if float(k).is_integer() else k}-{cp}", 0.0)
            v24 = {kc: vol("v24", *kc) for kc in oi}
            v8 = {kc: vol("v8", *kc) for kc in oi}
            OI, V24, V8 = sum(oi.values()), sum(v24.values()), sum(v8.values())
            S = g["S"]
            near = {kc for kc in oi if abs(kc[0] / S - 1) <= 0.05}
            mp = max_pain(oi)
            mpm24 = max_pain({kc: max(0.0, v - v24[kc]) for kc, v in oi.items()})
            mpp24 = max_pain({kc: v + v24[kc] for kc, v in oi.items()})
            mpm8 = max_pain({kc: max(0.0, v - v8[kc]) for kc, v in oi.items()})
            mpp8 = max_pain({kc: v + v8[kc] for kc, v in oi.items()})
            r = [cur, x["exp"], x["type"], x["t"][:19], f"{S:.2f}", f"{OI:.1f}", f"{V24:.1f}", f"{V8:.1f}",
                 f"{V24 / OI:.4f}", f"{V8 / OI:.4f}", str(mp), str(mpm24), str(mpp24), str(mpm8), str(mpp8),
                 f"{sum(oi[k] for k in near):.1f}", f"{sum(v24[k] for k in near):.1f}", str(lv["n_trades_all"])]
            rows.append(r)
            with open(OUT, "w") as f:
                f.write(hdr + "\n")
                for rr in rows:
                    f.write(",".join(rr) + "\n")
            if i % 10 == 0:
                print(cur, i, len(todo), x["exp"], x["type"], f"V24/OI {V24 / OI:.3f}", f"{time.time() - t0:.0f}s",
                      flush=True)
    print("готово", len(rows))


if __name__ == "__main__":
    main(sys.argv[1:] or ["BTC", "ETH"])
