"""s263 — объявления Binance с 01.11.2025 по сегодня (CMS API сайта, как s10/ann_fetch.py) и тексты тех, что про TradFi:
запуски TradFi-перпов, Pre-IPO, правила (фандинг, индекс, часы торгов, дивиденды, сплиты), делистинги и паузы.
Плюс тексты всех TradFi-объявлений из архива s12/ann_perp.pkl (заголовки по 21.10.2026) — для сводной таблицы.

Запуск из /home/user/mc_data: python3 -I <путь>/ann_update.py
Выход: s263/ann_tradfi.json — [{code, title, ts, cat, body}] (только TradFi), s263/ann_titles.json — все заголовки
разделов 48, 49, 161, 157, 51; печать списка с 01.10.2026."""
import datetime
import json
import os
import pickle
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cms import fetch, to_text  # noqa: E402

UA = {"User-Agent": "research-script/1.0"}
UTC = datetime.timezone.utc
T0 = int(datetime.datetime(2025, 11, 1, tzinfo=UTC).timestamp() * 1000)
T_NEW = int(datetime.datetime(2026, 10, 1, tzinfo=UTC).timestamp() * 1000)
PAT = re.compile(r"TradFi|Equity|Equities|Pre-IPO|Stock|Commodit|Dividend|Split|Quanto|USDBRL|Gold|Silver|"
                 r"XAU|XAG|Trading Hours|Price Index|Mark Price|bStocks|Tokeni[sz]ed|Securities|IPO", re.I)


def catalog(cat, page, size=50):
    """Список статей раздела (article/list/query отдаёт и время публикации; catalog/list/query его больше не отдаёт)."""
    u = f"https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&catalogId={cat}&pageNo={page}&pageSize={size}"
    for i in range(4):
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30))["data"]
            for c in d.get("catalogs") or []:
                if c.get("catalogId") == cat:
                    return c
            return None
        except Exception:
            time.sleep(3 + 3 * i)
    return None


def main():
    seen = {}
    for cat in (48, 49, 161, 157, 51):
        for page in range(1, 40):
            d = catalog(cat, page)
            time.sleep(0.4)
            if not d:
                break
            arts = d.get("articles") or []
            for a in arts:
                seen[a["code"]] = dict(cat=cat, code=a["code"], title=a["title"], ts=a.get("releaseDate"))
            if not arts or min((a.get("releaseDate") or 0) for a in arts) < T0:
                break
    new = [a for a in seen.values() if (a["ts"] or 0) >= T0 and PAT.search(a["title"])]
    json.dump(sorted(seen.values(), key=lambda x: x["ts"] or 0), open("s263/ann_titles.json", "w"), ensure_ascii=False)
    old = pickle.load(open("s12/ann_perp.pkl", "rb"))
    olds = [dict(cat=None, code=a["code"], title=a["title"], ts=a["ts"], body=a["body"]) for a in old.values()
            if PAT.search(a["title"]) or re.search(r"TradFi", a["body"][:2500])]
    have = {a["code"] for a in olds}
    for a in sorted(new, key=lambda x: x["ts"]):
        if a["code"] in have:
            continue
        j = fetch(a["code"])
        body = ((j or {}).get("data") or {}).get("body") or ""
        a["body"] = to_text(body)[0]
        olds.append(a)
        time.sleep(0.4)
    olds.sort(key=lambda x: x["ts"] or 0)
    json.dump(olds, open("s263/ann_tradfi.json", "w"), ensure_ascii=False)
    print(f"всего статей в разделах с 01.11.2025: {sum((a['ts'] or 0) >= T0 for a in seen.values())}; TradFi-объявлений: "
          f"{len(olds)} (по заголовкам с 01.11.2025: {len(new)})")
    for a in olds:
        if (a["ts"] or 0) >= T_NEW:
            print(datetime.datetime.fromtimestamp(a["ts"] / 1000, UTC).strftime("%Y-%m-%d %H:%M"), a["code"][:8],
                  a["title"][:150])


if __name__ == "__main__":
    main()
