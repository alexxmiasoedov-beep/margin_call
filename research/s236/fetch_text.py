"""s236 — тексты объявлений Binance об экосистеме Alpha / Wallet: Booster, (Pre-)TGE, эйрдропы и очки Alpha, Alpha Box,
соревнования Alpha, удаление из Alpha. Список статей — архивы заголовков s10/ann.pkl, s124/ann.pkl, s24/act.pkl (разделы
48, 49, 93, 161), тело — CMS detail (без ключей, пауза 0,4 с). Уже скачанные в s24/act_text.pkl берутся оттуда.
Итог — s236/texts.pkl: {код: {code, title, ts, cat, body}}. Запуск из /home/user/mc_data."""
import json
import os
import pickle
import re
import time
import urllib.request

UA = {"User-Agent": "research-script/1.0"}
PAT = (r"booster|\bTGE\b|token generation|alpha points|alpha box|alpha.*airdrop|airdrop.*alpha|binance alpha|"
       r"binance wallet|alpha trading competition|alpha will remove")
PATH = "s236/texts.pkl"


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
    A = {}
    for p in ("s10/ann.pkl", "s124/ann.pkl", "s24/act.pkl"):
        for k, v in pickle.load(open(p, "rb")).items():
            v = dict(v); v.setdefault("code", k); A[k] = v
    sel = sorted([a for a in A.values() if a.get("ts") and a["ts"] >= 1733011200000 and re.search(PAT, a["title"], re.I)],
                 key=lambda a: a["ts"])
    D = pickle.load(open(PATH, "rb")) if os.path.exists(PATH) else {}
    old = pickle.load(open("s24/act_text.pkl", "rb"))
    for a in sel:
        if a["code"] not in D and a["code"] in old:
            D[a["code"]] = old[a["code"]]
    print(f"статей {len(sel)}, уже с текстом {sum(a['code'] in D for a in sel)}", flush=True)
    for n, a in enumerate(sel):
        if a["code"] in D:
            continue
        u = f"https://www.binance.com/bapi/composite/v1/public/cms/article/detail/query?articleCode={a['code']}"
        j = None
        for i in range(4):
            try:
                with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30) as r:
                    j = json.load(r)
                break
            except Exception:
                time.sleep(2 + 3 * i)
        if not j:
            continue
        body = (j.get("data") or {}).get("body") or ""
        try:
            body = text(json.loads(body))
        except Exception:
            body = re.sub(r"<[^>]+>", " ", body)
        D[a["code"]] = dict(a, body=re.sub(r"\s+", " ", body))
        if n % 40 == 0:
            pickle.dump(D, open(PATH, "wb"))
            print(f"  {n}/{len(sel)}", flush=True)
        time.sleep(0.4)
    pickle.dump(D, open(PATH, "wb"))
    print("с текстом:", sum(a["code"] in D for a in sel))


if __name__ == "__main__":
    main()
