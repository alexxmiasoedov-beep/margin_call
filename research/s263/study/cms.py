"""s263 — статьи Binance (объявления и FAQ) через открытый CMS API сайта (тот же, что в s10/s12; веб-страницы за WAF
не трогаем). Текст тела статьи (JSON-дерево) переводится в строки: абзацы, пункты списков, строки таблиц через « | ».
Ссылки на другие статьи (32 hex) собираются, FAQ обходится на глубину DEPTH, только статьи про TradFi.

Запуск из /home/user/mc_data: python3 -I <путь>/cms.py [код ...]
Выход: s263/cms/<код>.txt (заголовок, дата, текст) и s263/cms/index.json."""
import json
import os
import re
import sys
import time
import urllib.request

OUT = "s263/cms"
UA = {"User-Agent": "research-script/1.0"}
API = "https://www.binance.com/bapi/composite/v1/public/cms/article/detail/query?articleCode="
BLOCK = {"p", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "div", "br", "table", "ul", "ol"}


def fetch(code):
    for i in range(4):
        try:
            req = urllib.request.Request(API + code, headers=UA)
            return json.load(urllib.request.urlopen(req, timeout=30))
        except Exception as e:  # сеть: пауза и повтор, без холостых циклов
            print("  сбой", code, e, flush=True)
            time.sleep(3 + 4 * i)
    return None


def walk(node, out, links):
    """Обход дерева: собирает текст с разрывами на блочных тегах, ячейки таблицы — через « | »."""
    if isinstance(node, list):
        for x in node:
            walk(x, out, links)
        return
    if not isinstance(node, dict):
        return
    if node.get("node") == "text":
        out.append(node.get("text", ""))
        return
    tag = node.get("tag", "")
    attr = node.get("attr") or {}
    href = attr.get("href") if isinstance(attr, dict) else None
    if isinstance(href, str):
        for m in re.findall(r"(faq|announcement/detail)/([0-9a-f]{32})", href):
            links.add(m)
    if tag in ("td", "th"):
        out.append(" | ")
    walk(node.get("child") or [], out, links)
    if tag in BLOCK:
        out.append("\n")


def to_text(body):
    links = set()
    try:
        tree = json.loads(body)
    except Exception:
        txt = re.sub(r"<[^>]+>", " ", body)
        return re.sub(r"[ \t]+", " ", txt), links
    out = []
    walk(tree, out, links)
    txt = "".join(out).replace("\xa0", " ")
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n\s*\n+", "\n", txt)
    return txt.strip(), links


def get(code, idx):
    path = os.path.join(OUT, code + ".txt")
    if code in idx:
        return idx[code]
    j = fetch(code)
    d = (j or {}).get("data") or {}
    if not d:
        idx[code] = dict(title=None)
        return idx[code]
    txt, links = to_text(d.get("body") or "")
    rd = d.get("releaseDate") or d.get("publishDate")
    with open(path, "w") as f:
        f.write(f"{d.get('title')}\n{rd}\nhttps://www.binance.com/en/support/faq/{code}\n\n{txt}\n")
    idx[code] = dict(title=d.get("title"), date=rd, links=sorted(f"{a}:{b}" for a, b in links), chars=len(txt))
    time.sleep(0.4)
    return idx[code]


def main():
    os.makedirs(OUT, exist_ok=True)
    ip = os.path.join(OUT, "index.json")
    idx = json.load(open(ip)) if os.path.exists(ip) else {}
    seeds = sys.argv[1:] or ["fe7dcdf24f1943d98b368f5f9f744398"]
    depth = int(os.environ.get("DEPTH", "2"))
    front = list(seeds)
    for lvl in range(depth + 1):
        nxt = []
        for code in front:
            r = get(code, idx)
            print(f"[{lvl}] {code} {r.get('title')}", flush=True)
            if lvl == depth or not r.get("title"):
                continue
            for ln in r.get("links", []):
                kind, c = ln.split(":")
                if c in idx:
                    continue
                nxt.append(c)
        # дальше идём только по статьям про TradFi (заголовок узнаём после загрузки)
        front = []
        for c in dict.fromkeys(nxt):
            r = get(c, idx)
            t = (r.get("title") or "")
            if re.search(r"TradFi|Traditional|Equity|Equities|Stock|Commodit|Dividend|Pre-IPO|Index|Mark Price|Funding|"
                         r"Trading Hours|Corporate|Split|Gold|Quanto", t, re.I):
                front.append(c)
            print(f"    -> {c} {t}", flush=True)
        json.dump(idx, open(ip, "w"), ensure_ascii=False, indent=1)
    json.dump(idx, open(ip, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
