import re, sys, urllib.request, time, html
UA={"User-Agent":"research-script/1.0"}
def page(ch, before=None):
    url=f"https://t.me/s/{ch}"+(f"?before={before}" if before else "")
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=40) as r:
            return r.read().decode('utf8','replace')
    except Exception as e:
        return "ERR "+str(e)
for ch in sys.argv[1:]:
    h=page(ch)
    if h.startswith("ERR"): print(ch, h[:100]); continue
    ids=[int(x) for x in re.findall(r'data-post="[^/"]+/(\d+)"', h)]
    dates=re.findall(r'<time datetime="([^"]+)"', h)
    title=re.search(r'<meta property="og:title" content="([^"]*)"', h)
    subs=re.search(r'<div class="tgme_header_counter">([^<]*)</div>', h)
    cnt=re.findall(r'<span class="counter_value">([^<]*)</span>\s*<span class="counter_type">([^<]*)</span>', h)
    if not ids: print(ch, 'no posts / not public', title.group(1) if title else ''); continue
    # probe early history: before=ids[-1] - big step
    old=page(ch, before=max(2, min(ids)//20))
    od=re.findall(r'<time datetime="([^"]+)"', old)
    print(f"{ch:28s} title={title.group(1)[:30] if title else ''!r} last_id={max(ids)} last={dates[-1][:10] if dates else ''} cnt={cnt[:2]} early_page_dates={od[:1]} ")
    time.sleep(1.5)
