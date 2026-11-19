"""s196 — промо «Locked Staking» Binance (2020–2026): дата погашения известна заранее (дата подписки + 15/30/60/90 сут),
монеты возвращаются на спот Binance. Заголовки — архив объявлений s10/ann.pkl; тексты — CMS API сайта (без ключа,
User-Agent research-script/1.0); из текста — сроки и лимит пула (Total/Pool Cap). Только размер и частота, без доходов.
Итог — /home/user/mc_data/s196/binance_locked.json и лог."""
import collections
import json
import os
import pickle
import re
import time
from common196 import http, OUT, D

PAT = re.compile(r"(Binance Staking Launches|Staking Special|Locked Staking|Adds .* (on|to) (Simple Earn )?Locked|"
                 r"Locked Savings|Locked Products|High-Yield|Staking Exclusive)", re.I)
SKIP = re.compile(r"Distributed|Distribution|Delist|Concludes|Completed|Upgrade|Loans|Dual|Pool Launches|NFT", re.I)


def text(node):
    if isinstance(node, dict):
        out = node.get("text", "") if isinstance(node.get("text"), str) else ""
        for v in node.values():
            if isinstance(v, (list, dict)):
                out += " " + text(v)
        return out
    if isinstance(node, list):
        return " ".join(text(x) for x in node)
    return ""


def main():
    A = pickle.load(open(f"{D}/s10/ann.pkl", "rb"))
    sel = sorted([a for a in A.values() if a["ts"] and PAT.search(a["title"]) and not SKIP.search(a["title"])],
                 key=lambda a: a["ts"])
    p = f"{OUT}/binance_locked.json"
    out = json.load(open(p)) if os.path.exists(p) else {}
    print("объявлений-кандидатов:", len(sel), flush=True)
    for a in sel:
        if a["code"] in out:
            continue
        d = http(f"https://www.binance.com/bapi/composite/v1/public/cms/article/detail/query?articleCode={a['code']}",
                 timeout=40, tries=3)
        body = ((d or {}).get("data") or {}).get("body") or ""
        try:
            body = text(json.loads(body))
        except Exception:
            body = re.sub(r"<[^>]+>", " ", body)
        body = re.sub(r"\s+", " ", body)
        days = sorted(set(int(x) for x in re.findall(r"(\d{1,3})[- ]day", body, re.I) if 5 <= int(x) <= 365))
        caps = re.findall(r"(?:Total (?:Pool )?(?:Cap|Quota|Limit)|Pool Cap|Total Amount)[^0-9]{0,40}([\d,\.]+)\s*([A-Z0-9]{2,10})",
                          body, re.I)
        out[a["code"]] = dict(ts=a["ts"], title=a["title"], days=days, caps=caps[:6], n=len(body))
        time.sleep(0.4)
    json.dump(out, open(p, "w"))
    yrs = collections.Counter(time.strftime("%Y", time.gmtime(v["ts"] / 1000)) for v in out.values())
    print("по годам:", sorted(yrs.items()))
    withcap = [v for v in out.values() if v["caps"]]
    print("с лимитом пула в тексте:", len(withcap), "из", len(out))
    for v in sorted(withcap, key=lambda v: v["ts"]):
        print(" ", time.strftime("%Y-%m-%d", time.gmtime(v["ts"] / 1000)), v["title"][:70], "| сроки", v["days"],
              "| лимит", v["caps"][:3])


if __name__ == "__main__":
    main()
