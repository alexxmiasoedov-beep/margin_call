"""s201: можно ли без ключа собрать историю переводов BEP20 на адреса Binance (независимая выборка для 🐋 вне Ethereum)?
Публичные узлы BNB Chain: getLogs без адреса токена запрещён или ограничен, с адресом — окно ≤ 50 000 блоков, а логи старше
~1 сут не отдаются (пусто или 403). Только описание доступа, без ключей."""
import json
import time
import urllib.error
import urllib.request

TR = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
HOT = "0x8894e0a0c962cb723c1976a4421c95949be2d4e3"     # горячий кошелёк Binance в BNB Chain
CAKE = "0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82"


def rpc(ep, method, params):
    req = urllib.request.Request(ep, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "research-script/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}"}
    except Exception as e:
        return {"error": str(e)[:100]}


for ep in ("https://bsc-rpc.publicnode.com", "https://bsc-dataseed.bnbchain.org"):
    bn = rpc(ep, "eth_blockNumber", [])
    if "result" not in bn:
        print(ep, "нет ответа:", bn.get("error"))
        continue
    bn = int(bn["result"], 16)
    to_topic = "0x" + "0" * 24 + HOT[2:]
    js = rpc(ep, "eth_getLogs", [{"fromBlock": hex(bn - 2000), "toBlock": hex(bn), "topics": [TR, None, to_topic]}])
    print(ep, f"блок {bn}; все токены → горячий Binance, 2000 блоков:",
          len(js["result"]) if isinstance(js.get("result"), list) else js.get("error"))
    for back in (0, 20000, 100000, 1000000):
        js = rpc(ep, "eth_getLogs", [{"address": CAKE, "fromBlock": hex(bn - back - 2000), "toBlock": hex(bn - back),
                                      "topics": [TR]}])
        print(f"   переводы CAKE, 2000 блоков, {back} блоков назад (~{back*0.75/3600:.0f} ч):",
              len(js["result"]) if isinstance(js.get("result"), list) else js.get("error"))
        time.sleep(0.5)
