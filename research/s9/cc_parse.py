"""raw/p_*.html → posts.pkl / posts.jsonl: id, время, текст, ссылки, картинки, превью ссылок, пересылки, ответы, просмотры."""
import glob, re, json, pickle
from bs4 import BeautifulSoup
P = {}
def txt(el):
    if el is None: return ""
    for br in el.find_all("br"): br.replace_with("\n")
    for e in el.find_all("i", class_="emoji"): e.replace_with(e.get_text())
    return el.get_text()
for fn in sorted(glob.glob("raw/p_*.html")) + ["raw/first.html"]:
    soup = BeautifulSoup(open(fn).read(), "html.parser")
    for m in soup.find_all("div", class_="tgme_widget_message"):
        dp = m.get("data-post", "")
        if not dp.startswith("cryptocoddee/"): continue
        i = int(dp.split("/")[1])
        if i in P: continue
        t = m.find("time"); te = m.find("div", class_="tgme_widget_message_text")
        links = [a.get("href") for a in te.find_all("a")] if te else []
        text = txt(te)
        photos = [re.search(r"url\('([^']+)'\)", a.get("style", "")).group(1) for a in m.find_all("a", class_="tgme_widget_message_photo_wrap") if "url('" in a.get("style", "")]
        vids = [re.search(r"url\('([^']+)'\)", v.get("style", "")).group(1) for v in m.find_all("i", class_="tgme_widget_message_video_thumb") if "url('" in v.get("style", "")]
        lp = m.find("a", class_="tgme_widget_message_link_preview")
        prev = None
        if lp:
            g = lambda c: txt(lp.find("div", class_=c)) if lp.find("div", class_=c) else ""
            prev = dict(href=lp.get("href"), site=g("link_preview_site_name"), title=g("link_preview_title"), desc=g("link_preview_description"))
        fw = m.find(class_="tgme_widget_message_forwarded_from_name")
        rp = m.find("a", class_="tgme_widget_message_reply")
        docs = [txt(d) for d in m.find_all("div", class_="tgme_widget_message_document_title")]
        v = m.find("span", class_="tgme_widget_message_views")
        P[i] = dict(id=i, dt=t.get("datetime") if t else None, text=text, links=links, photos=photos, videos=vids, preview=prev,
                    fwd=(fw.get_text() if fw else None), fwd_href=(fw.get("href") if fw and fw.name == "a" else None),
                    reply=(rp.get("href") if rp else None), reply_text=(txt(rp.find("div", class_="tgme_widget_message_text")) if rp else ""),
                    docs=docs, views=(v.get_text() if v else None))
L = [P[k] for k in sorted(P)]
pickle.dump(L, open("posts.pkl", "wb"))
with open("posts.jsonl", "w") as f:
    for p in L: f.write(json.dumps(p, ensure_ascii=False) + "\n")
print(len(L), "постов", L[0]["dt"], "→", L[-1]["dt"])
