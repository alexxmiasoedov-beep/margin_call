"""s139 — расписания разлоков DefiLlama без ключа: список проектов (defillama-datasets.llama.fi/emissionsProtocolsList),
файл проекта (…/emissions/<slug>: события cliff / linear с категорией получателей, накопленный разлок по дням), справочники
символов — api.llama.fi/protocols, api.llama.fi/v2/chains, CoinGecko /coins/list. Кэш — s139/ll/ в папке данных, пауза 1 с,
прерванная загрузка продолжается. Запуск из /home/user/mc_data: python3 <repo>/research/s139/ll_fetch.py"""
import json
import os
import time
import urllib.request

UA = {"User-Agent": "research-script/1.0"}
D = "s139/ll"
SRC = {"protocols.json": "https://api.llama.fi/protocols", "chains.json": "https://api.llama.fi/v2/chains",
       "cg_coins.json": "https://api.coingecko.com/api/v3/coins/list",
       "list.json": "https://defillama-datasets.llama.fi/emissionsProtocolsList"}


def get(url):
    for i in range(4):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90).read()
        except Exception as e:
            print(url, "ошибка", type(e).__name__, flush=True)
            time.sleep(10 * (i + 1))
    return None


def main():
    os.makedirs(D, exist_ok=True)
    for f, u in SRC.items():
        if not os.path.exists(f"{D}/{f}"):
            raw = get(u)
            if raw:
                open(f"{D}/{f}", "wb").write(raw)
            time.sleep(1)
    slugs = json.load(open(f"{D}/list.json"))
    for k, s in enumerate(slugs):
        p = f"{D}/e_{s}.json"
        if os.path.exists(p):
            continue
        raw = get(f"https://defillama-datasets.llama.fi/emissions/{s}")
        if raw:
            open(p, "wb").write(raw)
        if k % 50 == 0:
            print(k, s, flush=True)
        time.sleep(1)
    print("готово", flush=True)


if __name__ == "__main__":
    main()
