import re, sys, urllib.request, time, html, json, datetime as dt
UA={"User-Agent":"research-script/1.0"}
def page(ch, before=None):
    url=f"https://t.me/s/{ch}"+(f"?before={before}" if before else "")
    for i in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=40) as r:
                return r.read().decode('utf8','replace')
        except Exception as e:
            time.sleep(3+5*i)
    return ""
def parse(h, ch):
    out=[]
    for m in re.finditer(r'<div class="tgme_widget_message_wrap.*?(?=<div class="tgme_widget_message_wrap|\Z)', h, re.S):
        b=m.group(0)
        pid=re.search(r'data-post="[^/"]+/(\d+)"', b)
        t=re.search(r'<time datetime="([^"]+)"', b)
        txt=re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', b, re.S)
        if pid and t:
            s=re.sub(r'<br\s*/?>','\n',txt.group(1)) if txt else ''
            s=html.unescape(re.sub(r'<[^>]+>','',s))
            out.append((int(pid.group(1)), t.group(1), s))
    return out
def date_at(ch, pid):
    p=parse(page(ch, before=pid+1), ch)
    return (p[-1][1] if p else None)
def find_id(ch, target, lo, hi):
    # smallest id whose date >= target (ISO string compare)
    while hi-lo>20:
        mid=(lo+hi)//2
        d=date_at(ch, mid)
        if d is None: lo=mid; continue
        if d < target: lo=mid
        else: hi=mid
        time.sleep(0.7)
    return lo
def month(ch, start, end, last_id):
    a=find_id(ch, start, 1, last_id); b=find_id(ch, end, a, last_id)
    posts={}
    cur=b+20
    while cur>a:
        p=parse(page(ch, before=cur), ch)
        if not p: cur-=20; continue
        for x in p: posts[x[0]]=x
        cur=min(x[0] for x in p)
        time.sleep(0.8)
    res=[posts[k] for k in sorted(posts) if start<=posts[k][1]<end]
    return res
if __name__=="__main__":
    ch, start, end, last_id, out = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
    t=time.time()
    r=month(ch, start, end, last_id)
    json.dump(r, open(out,'w'), ensure_ascii=False)
    print(ch, start, len(r), f"{time.time()-t:.0f}s")
