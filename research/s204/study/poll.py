#!/usr/bin/env python3
"""s204: запись флагов осторожности Upbit и предупреждений Bithumb раз в 5 мин.

Опрашивает (User-Agent research-script/1.0, без ключей):
  Upbit   GET /v1/market/all?isDetails=true          -> market_event.warning / caution{...}
  Bithumb GET /v1/market/virtual_asset_warning        -> market, warning_type, warning_step, end_date
  Bithumb GET /v1/market/all?isDetails=true           -> market_warning (유의 종목)
Пишет в /home/user/mc_data/s204/:
  raw/<биржа>_<ГГГГММДДTЧЧММ>.json.gz   — сырые снимки,
  events.csv                             — появления, снятия и смены флагов,
  snapshots.csv                          — сводка каждого опроса (число флагов по типам).
Работает не дольше DURATION_S (по умолчанию 2 ч 55 мин); при сетевой ошибке —
пропуск опроса (без повторов вхолостую).
"""
import csv, gzip, json, os, sys, time, urllib.request
from datetime import datetime, timezone

OUT = "/home/user/mc_data/s204"
UA = "research-script/1.0"
STEP = 300
DURATION_S = int(os.environ.get("DURATION_S", str(2 * 3600 + 55 * 60)))
URLS = {
    "upbit": "https://api.upbit.com/v1/market/all?isDetails=true",
    "bithumb_warn": "https://api.bithumb.com/v1/market/virtual_asset_warning",
    "bithumb_all": "https://api.bithumb.com/v1/market/all?isDetails=true",
}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.status, dict(r.headers), r.read()


def flags_upbit(js):
    """market -> set of active flags (W = 유의, остальные — caution)."""
    out = {}
    for m in js:
        ev = m.get("market_event") or {}
        s = set()
        if ev.get("warning"):
            s.add("WARNING")
        for k, v in (ev.get("caution") or {}).items():
            if v:
                s.add(k)
        # неизвестные поля — тоже фиксируем, чтобы не пропустить новое
        for k in ev:
            if k not in ("warning", "caution"):
                s.add("EXTRA:" + k + "=" + json.dumps(ev[k], ensure_ascii=False))
        if s:
            out[m["market"]] = s
    return out


def flags_bithumb_warn(js):
    """(market, warning_type) -> (step, end_date)."""
    out = {}
    for w in js:
        out[(w.get("market"), w.get("warning_type"))] = (w.get("warning_step"), w.get("end_date"),
                                                         json.dumps({k: v for k, v in w.items() if k not in (
                                                             "market", "warning_type", "warning_step", "end_date")},
                                                             ensure_ascii=False))
    return out


def flags_bithumb_all(js):
    out = {}
    for m in js:
        mw = m.get("market_warning")
        if mw and mw != "NONE":
            out[m["market"]] = mw
    return out


def main():
    os.makedirs(OUT + "/raw", exist_ok=True)
    ev_path = OUT + "/events.csv"
    sn_path = OUT + "/snapshots.csv"
    new_ev = not os.path.exists(ev_path)
    new_sn = not os.path.exists(sn_path)
    evf = open(ev_path, "a", newline="")
    snf = open(sn_path, "a", newline="")
    ev = csv.writer(evf)
    sn = csv.writer(snf)
    if new_ev:
        ev.writerow(["time_utc", "source", "market", "flag", "action", "step", "end_date", "extra"])
    if new_sn:
        sn.writerow(["time_utc", "source", "http", "server_date", "n_items", "n_flagged", "by_flag"])
    t_end = time.time() + DURATION_S
    prev = {}
    first = True
    while time.time() < t_end:
        now = datetime.now(timezone.utc)
        stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        tag = now.strftime("%Y%m%dT%H%M")
        for src, url in URLS.items():
            try:
                code, hdr, body = get(url)
                js = json.loads(body)
            except Exception as e:  # сеть — пропуск опроса, без повторов
                print(stamp, src, "ОШИБКА", repr(e)[:200], flush=True)
                sn.writerow([stamp, src, "ERR", "", "", "", repr(e)[:120]])
                continue
            with gzip.open(f"{OUT}/raw/{src}_{tag}.json.gz", "wb") as f:
                f.write(body)
            if src == "upbit":
                cur = flags_upbit(js)
                cnt = {}
                for s in cur.values():
                    for k in s:
                        cnt[k] = cnt.get(k, 0) + 1
                old = prev.get(src)
                if old is not None:
                    for mk in set(cur) | set(old):
                        a, b = old.get(mk, set()), cur.get(mk, set())
                        for k in sorted(b - a):
                            ev.writerow([stamp, src, mk, k, "on", "", "", ""])
                        for k in sorted(a - b):
                            ev.writerow([stamp, src, mk, k, "off", "", "", ""])
                elif first:
                    for mk, s in cur.items():
                        for k in sorted(s):
                            ev.writerow([stamp, src, mk, k, "start", "", "", ""])
                n_items = len(js)
            elif src == "bithumb_warn":
                cur = flags_bithumb_warn(js)
                cnt = {}
                for (mk, wt), (stp, ed, ex) in cur.items():
                    cnt[f"{wt}/{stp}"] = cnt.get(f"{wt}/{stp}", 0) + 1
                old = prev.get(src)
                if old is not None:
                    for key in set(cur) | set(old):
                        a, b = old.get(key), cur.get(key)
                        if a is None:
                            ev.writerow([stamp, src, key[0], key[1], "on", b[0], b[1], b[2]])
                        elif b is None:
                            ev.writerow([stamp, src, key[0], key[1], "off", a[0], a[1], a[2]])
                        elif a != b:
                            ev.writerow([stamp, src, key[0], key[1], "change", f"{a[0]}->{b[0]}",
                                         f"{a[1]}->{b[1]}", b[2]])
                elif first:
                    for key, b in cur.items():
                        ev.writerow([stamp, src, key[0], key[1], "start", b[0], b[1], b[2]])
                n_items = len(js)
            else:
                cur = flags_bithumb_all(js)
                cnt = {}
                for v in cur.values():
                    cnt[v] = cnt.get(v, 0) + 1
                old = prev.get(src)
                if old is not None:
                    for mk in set(cur) | set(old):
                        a, b = old.get(mk), cur.get(mk)
                        if a != b:
                            ev.writerow([stamp, src, mk, "market_warning", "on" if a is None else (
                                "off" if b is None else "change"), f"{a}->{b}", "", ""])
                elif first:
                    for mk, v in cur.items():
                        ev.writerow([stamp, src, mk, "market_warning", "start", v, "", ""])
                n_items = len(js)
            prev[src] = cur
            sn.writerow([stamp, src, code, hdr.get("Date", ""), n_items, len(cur),
                         json.dumps(cnt, ensure_ascii=False, sort_keys=True)])
            print(stamp, src, code, "элементов", n_items, "с флагом", len(cur), flush=True)
        first = False
        evf.flush(); snf.flush()
        # до следующей отметки кратной 5 мин
        t = time.time()
        nxt = (int(t) // STEP + 1) * STEP + 20
        if nxt >= t_end:
            break
        time.sleep(max(5, nxt - t))
    print(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "готово", flush=True)


if __name__ == "__main__":
    main()
