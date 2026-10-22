"""Публичные страницы Notion из постов: блоки через loadPageChunk (рекурсивно по подстраницам) → notion/<id>.txt"""
import json, subprocess, sys
def chunk(pid):
    out = {}; cur = {"stack": []}; n = 0
    while True:
        d = json.dumps({"pageId": pid, "limit": 100, "cursor": cur, "chunkNumber": n, "verticalColumns": False})
        r = subprocess.run(["curl", "-sS", "-m", "60", "-X", "POST", "https://www.notion.so/api/v3/loadPageChunk", "-H", "Content-Type: application/json", "-d", d], capture_output=True, text=True)
        try: j = json.loads(r.stdout)
        except Exception: break
        for k, v in (j.get("recordMap", {}).get("block") or {}).items():
            out[k] = v.get("value") or v
            if isinstance(out[k], dict) and "value" in out[k]: out[k] = out[k]["value"]
        cur = j.get("cursor") or {"stack": []}; n += 1
        if not cur.get("stack"): break
    return out
def title(b):
    t = (b.get("properties") or {}).get("title") or []
    s = ""
    for seg in t:
        s += seg[0]
        for f in (seg[1] if len(seg) > 1 else []):
            if f and f[0] == "a": s += f" [{f[1]}]"
    return s
seen = set()
def render(pid, B, depth, lines):
    b = B.get(pid)
    if not b or pid in seen: return
    seen.add(pid); typ = b.get("type"); t = title(b)
    pre = {"header": "# ", "sub_header": "## ", "sub_sub_header": "### ", "bulleted_list": "- ", "numbered_list": "1. ", "quote": "> ", "callout": "! ", "to_do": "[ ] ", "toggle": "▸ "}.get(typ, "")
    if typ == "image": lines.append("  " * depth + f"[IMG] {(b.get('format') or {}).get('display_source') or (b.get('properties') or {}).get('source')}")
    elif typ == "page" and depth > 0:
        lines.append("  " * depth + f"[СТРАНИЦА] {t} ({pid})"); SUB.append(pid); return
    elif t: lines.append("  " * depth + pre + t)
    for c in b.get("content") or []:
        render(c, B, depth + (1 if typ not in ("page", "column_list", "column") else 0), lines)
SUB = []
todo = sys.argv[1:]; done = set()
while todo:
    pid = todo.pop(0)
    if pid in done: continue
    done.add(pid); B = chunk(pid)
    lines = []; render(pid, B, 0, lines)
    # блоки, не попавшие в обход (если корень не загрузился целиком)
    open(f"notion/{pid}.txt", "w").write("\n".join(lines) + "\n"); print(pid, len(B), "блоков", sum(len(x) for x in lines), "симв.", "подстраниц", len(SUB))
    todo += [s for s in SUB if s not in done]; SUB.clear()
