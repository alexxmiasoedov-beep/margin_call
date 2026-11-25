"""s288: разведка форматов постов — шаблоны текста (числа и метки заменены) по сырым страницам.
python3 -I peek.py <папка сырья> [канал] [макс. страниц]"""
import collections, glob, gzip, html, os, re, sys

d = sys.argv[1]; chan = sys.argv[2] if len(sys.argv) > 2 else "whale_alert_io"
mx = int(sys.argv[3]) if len(sys.argv) > 3 else 10 ** 9
files = sorted(glob.glob(os.path.join(d, "p_*.html.gz")))[:mx]
tpl = collections.Counter(); ex = {}
hrefs = collections.Counter()
for f in files:
    s = gzip.open(f, "rt", encoding="utf-8", errors="replace").read()
    for p in s.split('<div class="tgme_widget_message_wrap')[1:]:
        m = re.search(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', p, re.S)
        if not m:
            tpl["<нет текста>"] += 1; continue
        body = m.group(1)
        for h in re.findall(r'href="([^"]+)"', body):
            hh = re.sub(r'[0-9a-fA-F]{16,}', 'HASH', h)
            hh = re.sub(r'\?q=%23\w+', '?q=TAG', hh)
            hrefs[re.sub(r'/stories/.*', '/stories/…', hh)] += 1
        t = re.sub(r'<br\s*/?>', ' ', body)
        t = re.sub(r'<[^>]+>', '', t)
        t = html.unescape(t)
        t = re.sub(r'[^\x00-\x7F]+', ' ', t)
        t = re.sub(r'\s+', ' ', t).strip()
        k = re.sub(r'[\d][\d,\.]*', 'N', t)
        k = re.sub(r'[#$]\w+', 'TAG', k)
        k = re.sub(r'\b(Details|Read Analysis)\b.*$', r'\1', k)
        k = k[:140]
        tpl[k] += 1
        ex.setdefault(k, t[:200])
print(len(files), "страниц")
for k, n in tpl.most_common(60):
    print(n, "|", k, "||", ex[k][:160])
print("--- ссылки")
for k, n in hrefs.most_common(40):
    print(n, k)
