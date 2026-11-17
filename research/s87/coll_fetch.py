"""s87 — объявления Binance об изменении залоговых коэффициентов (Portfolio Margin / Cross Margin / VIP Loan) с 10.2024:
тексты по коду статьи (CMS API сайта, без ключа), разбор таблицы «монета | до | после» и времени вступления.
Итог — s87/coll.pkl: DataFrame [объявлено, вступает, монета, до, после, заголовок]. Запуск из папки с данными."""
import datetime
import json
import pickle
import re
import time
import urllib.request

import pandas as pd

UTC = datetime.timezone.utc


def text(code):
    u = f"https://www.binance.com/bapi/composite/v1/public/cms/article/detail/query?articleCode={code}"
    for k in range(4):
        try:
            j = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=30))
            body = j["data"]["body"]
            out = []

            def walk(n):
                if isinstance(n, dict):
                    if n.get("node") == "text":
                        out.append(n.get("text", ""))
                    for v in n.values():
                        walk(v)
                elif isinstance(n, list):
                    for v in n:
                        walk(v)
            try:
                walk(json.loads(body))
            except Exception:
                out = [re.sub(r"<[^>]+>", " ", body)]
            return [x.replace("\xa0", " ").strip() for x in out if x.strip()]
        except Exception:
            time.sleep(2 + 3 * k)
    return None


def parse(parts):
    """Тройки «монета | до% | после%» из таблицы Portfolio Margin / Cross Margin (до раздела PM Pro) и время вступления."""
    s = " | ".join(parts)
    m = re.search(r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s*\(UTC\)", s)
    eff = datetime.datetime.strptime(m.group(1) + " " + m.group(2), "%Y-%m-%d %H:%M").replace(tzinfo=UTC).timestamp() if m else None
    rows = []
    i = 0
    while i < len(parts) - 2:
        if re.fullmatch(r"Asset.*\(PM Pro\).*|Asset \(PM Pro\)", parts[i]):
            break
        a, b, c = parts[i], parts[i + 1], parts[i + 2]
        if re.fullmatch(r"[A-Z0-9]{2,15}", a) and re.fullmatch(r"\d+(\.\d+)?%", b) and re.fullmatch(r"\d+(\.\d+)?%", c):
            rows.append((a, float(b[:-1]), float(c[:-1]))); i += 3
        else:
            i += 1
    return eff, rows


def main():
    A = pickle.load(open("s10/ann.pkl", "rb"))
    arts = sorted((a["ts"] / 1000, a["code"], a["title"]) for a in A.values() if a.get("ts") and a["ts"] / 1000 >= 1727740800
                  and re.search(r"collateral ratio|collateral rate|collateral tier", a["title"], re.I))
    out = []
    for t, code, title in arts:
        parts = text(code)
        if not parts:
            print("нет текста:", title); continue
        eff, rows = parse(parts)
        for coin, b, a in rows:
            out.append(dict(ann=t, eff=eff, coin=coin, before=b, after=a, title=title))
        time.sleep(0.4)
    X = pd.DataFrame(out)
    pickle.dump(X, open("s87/coll.pkl", "wb"))
    print(f"объявлений {len(arts)}, строк {len(X)}; без времени вступления: {X.eff.isna().sum()}")


if __name__ == "__main__":
    main()
