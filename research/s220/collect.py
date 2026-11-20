"""s220 — сбор крупных заводов токена Solana на Binance без ключа (бесплатные узлы Solana).

Устройство Binance в Solana (проба 20.11.2026, `probe.py`):
- сметание с адреса пополнения пользователя на проходной счёт Binance 1 (`5tzF…`) подписывает плательщик комиссии
  Binance `5JPA…` вместе с адресом пополнения;
- с проходного счёта идут выводы пользователям и время от времени — перекладка излишка на складские счета (Binance 2,
  3, …), у которых за всё время десятки–сотни операций;
- после взлома конца октября 2026 г. сметания идут на новый адрес (`8DfH…`).

Способ (без перебора всех операций проходного счёта — их 50–150 в сутки на токен):
1. Подписи проходного счёта токена за период (страницы по 1000).
2. Все операции складских счетов — точки остатка проходного счёта (в них есть его остаток после операции).
3. Остаток проходного счёта — выборочно, каждая STEP-я операция.
4. Где остаток между соседними известными точками вырос на ≥ порога, деление пополам до одной операции. Если это
   сметание (подписано плательщиком `5JPA…`) — событие: время, сумма, адрес пополнения.
Режим `full` — все операции подряд за окно (для сверки полноты способа).

Запуск из /home/user/mc_data/s220:
  python3 <repo>/research/s220/collect.py <фьючерс> <mint> <начало ГГГГ-ММ-ДД> <конец ГГГГ-ММ-ДД> <порог, монет> [full]
"""
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

RPC = ("https://api.mainnet-beta.solana.com", "https://api.mainnet.solana.com")   # publicnode старую историю не хранит
UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
PAYER = "5JPAWfhLNsYVk3tPpD3gHvpHbvaXDbpUpy1wUfQVYRS2"            # плательщик комиссии сметаний Binance
HOT = "5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9"               # Binance 1 — проходной счёт
STEP = 100
_n = [0]


def rpc(method, params, tries=6):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    last = None
    for i in range(tries):
        url = RPC[(_n[0] + i) % len(RPC)]; _n[0] += 1
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=UA), timeout=60) as r:
                j = json.loads(r.read())
            if "error" in j:
                raise RuntimeError(j["error"])
            time.sleep(0.25)
            return j["result"]
        except Exception as e:
            last = e; time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"{method}: {last}")


def ts(d):
    return int(time.mktime(time.strptime(d, "%Y-%m-%d"))) - time.timezone


def signatures(acc, t0, t1):
    """Подписи счёта с blockTime в [t0, t1), от новых к старым."""
    out, before = [], None
    while True:
        p = {"limit": 1000}
        if before:
            p["before"] = before
        s = rpc("getSignaturesForAddress", [acc, p])
        if not s:
            break
        for x in s:
            bt = x.get("blockTime") or 0
            if bt < t0:
                return out
            if bt < t1 and not x.get("err"):
                out.append((x["signature"], x["slot"], bt))
        before = s[-1]["signature"]
        if len(s) < 1000:
            break
    return out


def tx_info(sig, mint, hot_acc):
    """Остаток проходного счёта после операции, изменения по владельцам, подписанты."""
    tx = rpc("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
    if not tx:
        return None
    keys = tx["transaction"]["message"]["accountKeys"]
    signers = [k["pubkey"] for k in keys if k.get("signer")]
    idx = {k["pubkey"]: i for i, k in enumerate(keys)}
    pre = {b["accountIndex"]: b for b in tx["meta"]["preTokenBalances"] if b["mint"] == mint}
    post = {b["accountIndex"]: b for b in tx["meta"]["postTokenBalances"] if b["mint"] == mint}
    amt = lambda b: float(b["uiTokenAmount"]["uiAmount"] or 0) if b else 0.0
    delta = {}
    for i in set(pre) | set(post):
        o = (post.get(i) or pre.get(i))["owner"]
        delta[o] = delta.get(o, 0.0) + amt(post.get(i)) - amt(pre.get(i))
    hi = idx.get(hot_acc)
    bal = amt(post.get(hi)) if hi is not None and hi in post else (0.0 if hi is not None else None)
    return {"bal": bal, "delta": delta, "signers": signers, "t": tx.get("blockTime")}


def main():
    fs, mint, d0, d1, thr = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], float(sys.argv[5])
    full = len(sys.argv) > 6 and sys.argv[6] == "full"
    allmode = len(sys.argv) > 6 and sys.argv[6] == "all"             # весь период: шаг выборки по числу подписей
    t0, t1 = ts(d0), ts(d1)
    bina = [ln.split("\t")[0] for ln in open("cex_solana_labels.tsv") if ln.split("\t")[1] == "Binance"]
    accs = {}
    for o in bina:
        for a in rpc("getTokenAccountsByOwner", [o, {"mint": mint}, {"encoding": "jsonParsed"}])["value"]:
            accs[a["pubkey"]] = o
    hot_acc = next((a for a, o in accs.items() if o == HOT), None)
    if hot_acc is None:
        print(fs, "нет счёта у Binance 1"); return
    sigs = signatures(hot_acc, t0, t1)[::-1]                          # от старых к новым
    print(f"{fs}: подписей проходного счёта {len(sigs)} за {d0}…{d1}", flush=True)
    step = max(STEP, len(sigs) // 1500) if allmode else STEP
    calls = {"tx": 0}

    def info(i):
        calls["tx"] += 1
        return tx_info(sigs[i][0], mint, hot_acc)
    events = []
    if full:
        with ThreadPoolExecutor(3) as ex:
            res = list(ex.map(info, range(len(sigs))))
        for i, r in enumerate(res):
            if r and r["signers"] and r["signers"][0] == PAYER and r["delta"].get(HOT, 0) >= thr:
                dep = next((o for o, d in r["delta"].items() if d < 0), None)
                events.append((sigs[i][2], r["delta"][HOT], dep, sigs[i][0]))
    else:
        # точки остатка: операции складских счетов, общие с проходным, и выборка каждой STEP-й операции
        pos = {s[0]: i for i, s in enumerate(sigs)}
        known = {}
        for a, o in accs.items():
            if a == hot_acc:
                continue
            for s in signatures(a, t0, t1):
                r = tx_info(s[0], mint, hot_acc); calls["tx"] += 1
                if not r:
                    continue
                if s[0] in pos and r["bal"] is not None:
                    known[pos[s[0]]] = r["bal"]
                if r["signers"] and r["signers"][0] == PAYER and r["delta"].get(o, 0) >= thr:   # сметание прямо на склад
                    dep = next((x for x, d in r["delta"].items() if d < 0), None)
                    events.append((s[2], r["delta"][o], dep, s[0]))
        idx = list(range(0, len(sigs), step)) + [len(sigs) - 1]
        with ThreadPoolExecutor(3) as ex:
            for i, r in zip(idx, ex.map(info, idx)):
                if r and r["bal"] is not None:
                    known[i] = r["bal"]
        pts = sorted(known)

        def bisect(a, b):
            """Между точками a и b остаток вырос на ≥ порога: ищем операцию со скачком."""
            if b - a <= 1:
                r = info(b)
                if r and r["signers"] and r["signers"][0] == PAYER and r["delta"].get(HOT, 0) >= thr:
                    dep = next((o for o, d in r["delta"].items() if d < 0), None)
                    events.append((sigs[b][2], r["delta"][HOT], dep, sigs[b][0]))
                return
            m = (a + b) // 2
            r = info(m)
            if r is None or r["bal"] is None:
                return
            known[m] = r["bal"]
            if known[m] - known[a] >= thr:
                bisect(a, m)
            if known[b] - known[m] >= thr:
                bisect(m, b)
        for a, b in zip(pts, pts[1:]):
            if known[b] - known[a] >= thr:
                bisect(a, b)
    events.sort()
    os.makedirs("events", exist_ok=True)
    name = f"events/{fs}_all.json" if allmode else f"events/{fs}_{d0}_{d1}{'_full' if full else ''}.json"
    json.dump({"fs": fs, "mint": mint, "d0": d0, "d1": d1, "thr": thr, "n_sigs": len(sigs), "calls": calls["tx"],
               "full": full, "step": None if full else step, "events": events}, open(name, "w"))
    print(f"{fs}: событий ≥ {thr:,.0f}: {len(events)}; запросов getTransaction {calls['tx']}", flush=True)
    for e in events[:20]:
        print("  ", time.strftime("%Y-%m-%d %H:%M", time.gmtime(e[0])), f"{e[1]:,.0f}", (e[2] or "")[:8])


if __name__ == "__main__":
    main()
