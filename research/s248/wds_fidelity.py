"""s248 — сверка классификатора 🐋⁺ (scanner._wds_check) с событиями бэктеста s221 на настоящих операциях Solana:
выборка сметаний из сбора s220 (≥ 0,5% монет в обращении CMC за день до, первые у монеты за 48 ч — как в s221) и выводов
с проходного счёта Binance 1. Операции — публичный узел Solana (getTransaction с паузами). Горячий кошелёк того времени —
Binance 1 (5tzF…), плательщик сметаний — тот же, что сейчас (5JPA…).
Ожидание: каждое сметание — событие с той же суммой и долей; вывод — не событие.
Запуск из /home/user/mc_data: python3 <repo>/research/s248/wds_fidelity.py [число событий, по умолчанию 40]"""
import glob
import json
import os
import random
import sys
import tempfile
import time
import urllib.error
import urllib.request

import pandas as pd

os.environ.setdefault("STATE_FILE", os.path.join(tempfile.mkdtemp(), "state.json"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "bot"))
import scanner  # noqa: E402

LOG = []
scanner.log = lambda *a: LOG.append(" ".join(str(x) for x in a))
HOT_OLD = "5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9"
UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
RPC = scanner.WDS_RPC


def rpc(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    for k in range(10):
        try:
            req = urllib.request.Request(RPC[k % len(RPC)], data=body, headers=UA)
            j = json.loads(urllib.request.urlopen(req, timeout=60).read())
            if "result" in j:
                return j["result"]
        except urllib.error.HTTPError:
            pass
        except Exception:
            pass
        time.sleep(3 + 2 * k)
    return None


def main():
    n_ev = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    C = json.load(open("s220/sol_circ.json"))
    rows = []
    for p in glob.glob("s220/events/*_all.json"):
        E = json.load(open(p)); fs = E["fs"]
        if fs not in C:
            continue
        days = {d: c for d, c, _ in C[fs]["days"]}
        dd = sorted(days)
        last = -10 ** 12
        for t, amt, dep, sig in sorted(E["events"]):
            d = pd.Timestamp(int(t) - 86400, unit="s").strftime("%Y-%m-%d")
            i = sum(1 for x in dd if x <= d) - 1
            circ = days[dd[i]] if i >= 0 else 0
            if circ and amt / circ >= scanner.WD_MIN and t - last >= scanner.WD_GAP_H * 3600:
                rows.append((fs, E["mint"], int(t), float(amt), dep, sig, circ)); last = t
    random.seed(7)
    sample = random.sample(rows, min(n_ev, len(rows)))
    ok = bad = miss = 0
    for fs, mint, t, amt, dep, sig, circ in sample:
        tx = rpc("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
        time.sleep(1.5)
        if not tx:
            miss += 1; continue
        s = {"hot": HOT_OLD, "tok": {mint: [fs, fs, circ, 0]}}
        LOG.clear()
        scanner._wds_check(s, mint, sig, tx)
        p = (s.get("pend") or {}).get(fs)
        good = p is not None and abs(p["n"] / amt - 1) < 1e-6 and abs(p["share"] / 100 - amt / circ) < 1e-4 and p["t"] == t \
            and (dep or "")[:8] in p["what"]
        ok += good; bad += not good
        if not good:
            print("РАСХОЖДЕНИЕ", fs, sig[:12], t, amt, circ, p, LOG[-1:] if LOG else "")
    print(f"сметания s221: проверено {ok + bad} (не отдал узел {miss}), совпало {ok}, расхождений {bad}")
    # выводы с Binance 1 — не события
    hot_acc = {}
    neg = ng = 0
    for fs, mint, *_ in random.sample(rows, min(8, len(rows))):
        if mint in hot_acc:
            continue
        r = rpc("getTokenAccountsByOwner", [HOT_OLD, {"mint": mint}, {"encoding": "jsonParsed"}])
        accs = [a["pubkey"] for a in (r or {}).get("value") or []]
        hot_acc[mint] = accs[0] if accs else None
        if not accs:
            continue
        sig = rpc("getSignaturesForAddress", [accs[0], {"limit": 30}]) or []
        for x in sig[:6]:
            tx = rpc("getTransaction", [x["signature"], {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
            time.sleep(1.5)
            if not tx:
                continue
            r = scanner._wds_tx(tx, mint)
            if not r or r[0].get(HOT_OLD, 0) >= 0:
                continue                                     # только операции, где остаток кошелька уменьшился (выводы)
            s = {"hot": HOT_OLD, "tok": {mint: [fs, fs, 1.0, 0]}}   # обращение 1 — любой приток был бы событием
            scanner._wds_check(s, mint, x["signature"], tx)
            neg += 1; ng += bool(s.get("pend"))
    print(f"выводы с Binance 1: проверено {neg}, ошибочно признано событием {ng}")


if __name__ == "__main__":
    main()
