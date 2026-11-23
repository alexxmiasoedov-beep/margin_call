"""Сбор постов ончейн-аналитиков (t.me/s, без ключа) с упоминанием ММ: адреса EVM/Solana и ссылки Arkham рядом с именем ММ.
Выход: tg/mm_posts.jsonl"""
import urllib.request, urllib.parse, re, html, json, time, sys
UA = {"User-Agent": "research-script/1.0"}
CH = ["lookonchainchannel", "spotonchain", "ai_9684xtpa", "OnchainLens"]
Q = ["wintermute", "gsr", "dwf", "amber group", "flowdesk", "galaxy digital", "jump trading", "cumberland", "b2c2", "auros", "selini",
     "keyrock", "kairon", "gotbit", "web3port", "falconx", "abraxas", "flow traders", "market maker", "做市商", "OTC"]
def get(u):
    for i in range(4):
        try:
            return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40).read().decode("utf-8", "ignore")
        except Exception as e:
            time.sleep(3 + 5 * i)
    return ""
out = open("tg/mm_posts.jsonl", "a")
seen = set()
for ch in CH:
    for q in Q:
        before = None; pages = 0; n = 0
        while pages < 40:
            u = f"https://t.me/s/{ch}?q=" + urllib.parse.quote(q) + (f"&before={before}" if before else "")
            s = get(u); pages += 1
            blocks = re.split(r'<div class="tgme_widget_message_wrap', s)[1:]
            if not blocks: break
            for b in blocks:
                pid = re.search(r'data-post="([^"]+)"', b)
                if not pid: continue
                pid = pid.group(1)
                txt = re.search(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', b, re.S)
                t = re.search(r'<time datetime="([^"]+)"', b)
                hrefs = re.findall(r'href="([^"]+)"', b)
                raw = html.unescape(re.sub(r"<br\s*/?>", "\n", txt.group(1))) if txt else ""
                text = re.sub(r"<[^>]+>", " ", raw)
                rec = {"ch": ch, "q": q, "id": pid, "t": t.group(1) if t else None, "text": text,
                       "links": [h for h in hrefs if re.search(r"arkm\.com|etherscan|solscan|bscscan|debank|basescan|arbiscan|hypurrscan|tonviewer|mintscan", h)]}
                if pid not in seen:
                    seen.add(pid); out.write(json.dumps(rec, ensure_ascii=False) + "\n"); n += 1
            m = re.search(r'tme_messages_more[^>]*data-before="(\d+)"', s)
            if not m: break
            before = m.group(1); time.sleep(1.0)
        print(ch, q, "pages", pages, "new posts", n, flush=True)
        time.sleep(1.0)
