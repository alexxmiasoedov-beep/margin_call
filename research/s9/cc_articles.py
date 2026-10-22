"""Все статьи блога teletype.in/@formulatrade (CryptoCode): список через API, затем страница каждой статьи → art/<uri>.html и art/<uri>.txt."""
import json, subprocess, time, os, re
from bs4 import BeautifulSoup
def get(u, js=False):
    for k in range(5):
        r = subprocess.run(["curl", "-sS", "-m", "60", "-A", "Mozilla/5.0"] + (["-H", "Accept: application/json"] if js else []) + [u], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout: return r.stdout
        time.sleep(2 + 3 * k)
    return None
arts, last = [], 0
while True:
    d = json.loads(get(f"https://teletype.in/api/blogs/id/3336346/articles?limit=10&last_article={last}", True))
    a = d.get("articles") or []
    if not a: break
    arts += [dict(id=x["id"], uri=x["uri"], title=x.get("title"), date=x.get("published_at") or x.get("created_at")) for x in a]
    last = a[-1]["id"]
    if len(arts) >= d.get("length", 0): break
print(len(arts), "статей")
json.dump(arts, open("art/_list.json", "w"), ensure_ascii=False, indent=1)
for x in arts:
    fn = f"art/{x['uri']}.html"
    if not os.path.exists(fn):
        h = get(f"https://teletype.in/@formulatrade/{x['uri']}")
        if h: open(fn, "w").write(h)
        time.sleep(0.3)
    h = open(fn).read(); art = BeautifulSoup(h, "html.parser").find("article")
    out = [f"# {x['title']}  ({x['date'][:10]})  https://teletype.in/@formulatrade/{x['uri']}"]
    if art:
        for el in art.find_all(["h1", "h2", "h3", "h4", "p", "li", "blockquote", "img", "figcaption", "pre", "a"]):
            if el.name == "img": out.append(f"[IMG] {el.get('src')}")
            elif el.name == "a":
                if el.get("href") and not el.find_parent(["p", "li", "h1", "h2", "h3", "h4", "blockquote"]): out.append(f"[LINK] {el.get('href')} {el.get_text(' ', strip=True)}")
            elif el.find_parent(["li", "blockquote"]) and el.name == "p": continue
            else:
                t = el.get_text(" ", strip=True)
                links = [a.get("href") for a in el.find_all("a") if a.get("href")]
                if t: out.append(("- " if el.name == "li" else "> " if el.name == "blockquote" else "## " if el.name in ("h1", "h2", "h3", "h4") else "") + t + (f"  [ссылки: {' '.join(links)}]" if links else ""))
    open(f"art/{x['uri']}.txt", "w").write("\n".join(out) + "\n")
print("готово")
