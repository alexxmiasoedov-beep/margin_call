"""s220 — проба: сколько переводов проходит через кошельки Binance в Solana по токенам перпов и сколько запросов к бесплатным
узлам (без ключа) нужно на два года истории. Метки — Dune spellbook `cex_solana_addresses` (15 адресов Binance).
Запуск из /home/user/mc_data/s220: python3 <repo>/research/s220/probe.py"""
import json
import time
import urllib.request

RPC = ("https://api.mainnet-beta.solana.com", "https://solana-rpc.publicnode.com", "https://api.mainnet.solana.com")
UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
TOKEN_PROGRAMS = ("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA", "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb")
MINTS = {"JTO": "jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL", "KMNO": "KMNo3nJsBXfcpJTVhZcXLW7RmTwTt4GVFE7suUBo9sS",
         "WIF": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm", "TNSR": "TNSRxcUxoT9xBG3de7PiJyTDYu7kskLqcpddxnEJAS6",
         "DRIFT": "DriFtupJYLTosbwoN8koMbEYSx54aFAVLddWsbksjwg7"}
STAT = {"calls": 0, "err": 0}


def rpc(method, params, url=RPC[0], tries=4):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    for i in range(tries):
        try:
            STAT["calls"] += 1
            with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=UA), timeout=60) as r:
                j = json.loads(r.read())
            if "error" in j:
                raise RuntimeError(j["error"])
            time.sleep(0.35)
            return j["result"]
        except Exception as e:
            STAT["err"] += 1
            time.sleep(2 + 3 * i)
            last = e
    raise RuntimeError(f"{method}: {last}")


def main():
    bina = [ln.split("\t")[0] for ln in open("cex_solana_labels.tsv") if ln.split("\t")[1] == "Binance"]
    out = {}
    for sym, mint in MINTS.items():
        accs = []
        for o in bina:
            r = rpc("getTokenAccountsByOwner", [o, {"mint": mint}, {"encoding": "jsonParsed"}])
            for a in r["value"]:
                amt = float(a["account"]["data"]["parsed"]["info"]["tokenAmount"]["uiAmount"] or 0)
                accs.append((o, a["pubkey"], amt))
        rows = []
        for o, acc, amt in accs:
            sig = rpc("getSignaturesForAddress", [acc, {"limit": 1000}])
            if not sig:
                rows.append((o, acc, amt, 0, None, None)); continue
            t1, t0 = sig[0].get("blockTime"), sig[-1].get("blockTime")
            per_day = len(sig) / max((t1 - t0) / 86400, 1e-3) if t1 and t0 else None
            rows.append((o, acc, amt, len(sig), per_day, t0))
        out[sym] = rows
        print(sym, "счетов токена у адресов Binance:", len(accs))
        for o, acc, amt, n, pdy, t0 in rows:
            print(f"   {o[:6]}… счёт {acc[:6]}… остаток {amt:,.0f}; подписей в последней 1000: {n}, в сутки ≈ "
                  f"{pdy:,.0f}" if pdy else f"   {o[:6]}… счёт {acc[:6]}… остаток {amt:,.0f}; подписей {n}")
    json.dump(out, open("probe_rates.json", "w"))
    print("запросов", STAT["calls"], "ошибок", STAT["err"])
    # проба getTransaction: время и содержимое одного перевода
    sym = "JTO"; acc = max(out[sym], key=lambda r: r[3])[1]
    sig = rpc("getSignaturesForAddress", [acc, {"limit": 5}])
    t0 = time.time()
    tx = rpc("getTransaction", [sig[0]["signature"], {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
    print("getTransaction:", round(time.time() - t0, 2), "с; pre/post по счёту:",
          [(b["owner"][:6], b["uiTokenAmount"]["uiAmount"]) for b in tx["meta"]["postTokenBalances"]][:4])
    # глубина истории: самая старая подпись у счёта (страницы по 1000 назад, не больше 30 страниц)
    before, n = None, 0
    for _ in range(30):
        p = {"limit": 1000}
        if before:
            p["before"] = before
        s = rpc("getSignaturesForAddress", [acc, p])
        if not s:
            break
        n += len(s); before = s[-1]["signature"]
        if len(s) < 1000:
            break
    print(f"{sym} счёт {acc[:6]}…: подписей за {n // 1000} страниц: {n}, самая старая — {time.strftime('%Y-%m-%d', time.gmtime(s[-1]['blockTime'] if s else 0))}")


if __name__ == "__main__":
    main()
