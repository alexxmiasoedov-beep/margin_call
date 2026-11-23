"""s263 — снимок состава индекса (GET www.binance.com/fapi/v1/constituents) для всех TradFi-перпов. Истории у этого
эндпоинта нет — только «сейчас». Запуск из /home/user/mc_data: python3 -I <путь>/fetch_constituents.py
Выход: s263/constituents_<дата>.json — символ → список {exchange, symbol, weight}."""
import datetime
import json
import time
import urllib.request

import pandas as pd

UA = {"User-Agent": "research-script/1.0"}


def main():
    meta = pd.read_csv("s263/tf_meta.csv")
    out = {}
    for s in list(meta.symbol) + ["PAXGUSDT", "XAUTUSDT"]:
        for i in range(3):
            try:
                j = json.load(urllib.request.urlopen(urllib.request.Request(
                    f"https://www.binance.com/fapi/v1/constituents?symbol={s}", headers=UA), timeout=20))
                out[s] = j.get("constituents") if isinstance(j, dict) else j
                break
            except Exception:
                time.sleep(3 * (i + 1))
        time.sleep(0.3)
    d = datetime.date.today().strftime("%Y%m%d")
    json.dump(out, open(f"s263/constituents_{d}.json", "w"), ensure_ascii=False)
    print("символов:", len(out))


if __name__ == "__main__":
    main()
