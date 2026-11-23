"""s252 — свежие заводы токенов группы H на биржи и шаг назад (кто завёл), публичный узел bsc-rpc.publicnode.com (логи
последних ~2 сут; адрес контракта обязателен, до 10 адресов в запросе). Без SQD.
1) Переводы токенов группы H (выпуск в BNB Chain ≥ 50% обращения) на главные адреса сметания бирж за последние 100 тыс.
   блоков (~12,5 ч); отбор — ≥ 0,25% монет в обращении (CMC, последний день).
2) Шаг назад: притоки этого токена на адрес пополнения за 60 тыс. блоков (~7 ч) до сметания; крупнейший источник —
   биржа (перекладка), пул DEX (DexScreener s252/dex_pairs.json) или прочий адрес; для прочего — ещё шаг: откуда он сам
   получил токены за те же ~7 ч (пул DEX = купил и завёл — арбитраж; биржа = вывел и завёл; пусто = держал дольше).
Только описание потоков, без цены. Итог — /home/user/mc_data/s252/recent_hop.json.
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s252/study/recent_hop.py"""
import collections
import json
import time
import urllib.request

U = "https://bsc-rpc.publicnode.com"
HDR = {"Content-Type": "application/json", "User-Agent": "research-script/1.0"}
T = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
SWEEP = {"0x0d0707963952f2fba59dd06f2b425ace40b492fe": "Gate.io", "0x4982085c9e2f89f2ecb8131eca71afad896e89cb": "MEXC",
         "0x2e8f79ad740de90dc5f5a9f0d8d9661a60725e64": "MEXC", "0x53f78a071d04224b8e254e243fffc6d9f2f3fa23": "KuCoin",
         "0x1ab4973a48dc892cd9971ece8e01dcc7688f8f23": "Bitget", "0xed9ab5bc05a0152b9dc2f7902e8369af7bc18771": "Bitget",
         "0xf89d7b9c864f589bbf53a82105107622b35eaa40": "Bybit", "0xef3aeff9a5f61c6dda33069c58c1434006e13b20": "Bybit",
         "0xc3121c4ca7402922e025e62e9bb4d5b244303878": "Bybit", "0x124d9bf2fecbc16b54ec4accdb14d44c2144f012": "LBank",
         "0x32e3e876aa0c1732ed9efcf9d8615de7afaef59f": "CoinEx", "0x2b3bf74b29f59fb8dda41cf3d6a8da28cf8e7921": "BingX",
         "0xdb3ded7731c781224ec292e2163d9554c094fd7c": "XT.com", "0x52854a35cf896a57b3a861ba7fbd2171f2445ef2": "Binance",
         "0x8894e0a0c962cb723c1976a4421c95949be2d4e3": "Binance"}
LABELS = "/home/user/mc_main/bot/cex_labels.tsv"
CONS2EX = {"gateio": "Gate.io", "mexc": "MEXC", "bitget": "Bitget", "bybit": "Bybit", "okex": "OKX", "kucoin": "KuCoin",
           "coinbase": "Coinbase"}


def rpc(m, p, tries=5):
    err = None
    for i in range(tries):
        try:
            r = urllib.request.urlopen(urllib.request.Request(U, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": m,
                                                                                  "params": p}).encode(), headers=HDR), timeout=90)
            d = json.loads(r.read())
            if "error" in d:
                raise RuntimeError(d["error"])
            return d["result"]
        except Exception as e:  # noqa: BLE001
            err = e
            time.sleep(3 + 3 * i)
    raise RuntimeError(str(err))


def pad(a):
    return "0x" + "0" * 24 + a[2:]


def inflows(tok, addr, b, back=60000):
    L = []
    for a in range(b - back, b, 10000):                  # по 10 тыс. блоков: узел быстрее отвечает на узкие диапазоны
        try:
            L += rpc("eth_getLogs", [{"fromBlock": hex(a), "toBlock": hex(min(b - 1, a + 9999)), "address": tok,
                                      "topics": [T, None, pad(addr)]}], tries=3)
        except RuntimeError:
            return None
    tot = collections.Counter()
    for lg in L:
        tot["0x" + lg["topics"][1][-40:]] += int(lg["data"], 16) if lg["data"] not in ("0x", "") else 0
    return tot


def main():
    TK = json.load(open("s252/tokens.json"))
    TB = json.load(open("s252/bsc_tokens.json"))
    NS = json.load(open("s252/nospot.json"))
    DP = json.load(open("s252/dex_pairs.json"))
    lab = {}
    for line in open(LABELS, encoding="utf-8"):
        if not line.startswith("#") and line.strip():
            p = line.split("\t")
            lab[p[0].strip().lower()] = p[1].strip()
    lab.update(SWEEP)
    pools = {p["pair"].lower() for v in DP.values() for p in v}
    H = {}
    for s, v in TB.items():
        if TK[s].get("alpha_chain") == "bsc" and TK[s]["bsc_native"] and v.get("days") and v["bsc_supply"] \
                and v["bsc_supply"] >= 0.5 * v["days"][-1][1]:
            H[v["contract"]] = (s, v["days"][-1][1], v["decimals"] or 18)
    h = int(rpc("eth_blockNumber", []), 16)
    lo = h - 100000                                    # ~12,5 ч (оборот токенов Alpha огромен: 240 тыс. блоков — ~50 мин загрузки)
    toks = sorted(H)
    big = []

    def get(tg, a, b):
        """Все Transfer токенов tg в [a, b] без фильтра получателя (с ним узел отвечает ~50 с); много логов — делим пополам."""
        try:
            return rpc("eth_getLogs", [{"fromBlock": hex(a), "toBlock": hex(b), "address": tg, "topics": [T]}], tries=3)
        except RuntimeError as e:
            if b - a > 300:
                m = (a + b) // 2
                return get(tg, a, m) + get(tg, m + 1, b)
            print("сбой", a, e, flush=True)
            return []

    for g in range(0, len(toks), 10):
        n0 = 0
        for a in range(lo, h, 2500):
            L = get(toks[g:g + 10], a, min(h, a + 2499))
            n0 += len(L)
            for lg in L:
                if len(lg["topics"]) < 3 or "0x" + lg["topics"][2][-40:] not in SWEEP:
                    continue
                tok = lg["address"].lower()
                s, circ, dec = H[tok]
                amt = int(lg["data"], 16) / 10 ** dec if lg["data"] not in ("0x", "") else 0
                fr = "0x" + lg["topics"][1][-40:]
                if fr in lab or amt / circ < 0.0025:
                    continue
                big.append({"perp": s, "tok": tok, "b": int(lg["blockNumber"], 16), "fr": fr, "to": SWEEP["0x" + lg["topics"][2][-40:]],
                            "frac": amt / circ})
        print("токенов", min(g + 10, len(toks)), "из", len(toks), "переводов всего", n0, "крупных на биржи", len(big), flush=True)
    for e in big:
        cons = {CONS2EX.get(c["exchange"], c["exchange"]) for c in NS[e["perp"]]["cons"]}
        e["cls"] = "а" if e["to"] in cons else ("г" if e["to"] == "Binance" else "б")
        f1 = inflows(e["tok"], e["fr"], e["b"])
        if not f1:
            e["src"], e["src_kind"] = None, "нет притока за ~7 ч" if f1 is not None else "сбой"
            continue
        src, amt1 = f1.most_common(1)[0]
        e["src"] = src
        if src in lab:
            e["src_kind"] = "биржа"
        elif src in pools:
            e["src_kind"] = "пул DEX"
        else:
            f2 = inflows(e["tok"], src, e["b"])
            if f2 is None:
                e["src_kind"] = "кошелёк (сбой шага 2)"
            elif not f2:
                e["src_kind"] = "кошелёк: держал ≥ 7 ч"
            else:
                s2 = f2.most_common(1)[0][0]
                e["src_kind"] = ("кошелёк ← биржа" if s2 in lab else "кошелёк ← пул DEX" if s2 in pools else "кошелёк ← кошелёк")
        print(e["perp"], e["to"], e["cls"], f"{e['frac']:.2%}", e["src_kind"], flush=True)
    json.dump({"blocks": [lo, h], "events": big}, open("s252/recent_hop.json", "w"), indent=0)
    c = collections.Counter((e["cls"], e["src_kind"]) for e in big)
    print("итог:", len(big), "переводов ≥ 0,25%;", dict(c))


if __name__ == "__main__":
    main()
