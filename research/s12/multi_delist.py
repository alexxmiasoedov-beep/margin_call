"""Объявления «Binance Futures Will Delist Multiple … Contracts»: монеты из текста, та же сделка, что у 📢
(вход ≤ 15 мин, 7 сут, стоп +25%, без входа при фандинге < −0,1%/8 ч)."""
import sys, os, re, json, time, urllib.request
sys.path.insert(0, os.getcwd())
from s12.lib import *
import pandas as pd
arts = [a for a in A.values() if a["ts"] and a["ts"] >= 1727740800000 and re.search(r"Futures Will Delist", a["title"]) and not re.findall(r"\b([A-Z0-9]{2,20})USDT\b", a["title"])]
print("объявлений «Multiple»:", len(arts))
rows = []
for a in arts:
    u = f"https://www.binance.com/bapi/composite/v1/public/cms/article/detail/query?articleCode={a['code']}"
    try: d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=30))["data"]
    except Exception as e: print("сбой", e); continue
    syms = sorted(set(re.findall(r"\b([A-Z0-9]{2,20})USDT\b", re.sub(r"<[^>]+>", " ", str(d.get("body") or "")))))
    for c in syms:
        s = next((p + c for p in ("", "1000", "10000", "100000", "1000000") if p + c in K), None)
        if not s or s in TF: continue
        r = ann_trade(s, a["ts"] // 1000, 15, 7, 0.25)
        if r is None or (r[3] is not None and r[3] < -0.001): continue
        rows.append(dict(s=s, ts=a["ts"] // 1000, sp=r[1]))
    time.sleep(0.3)
E = pd.DataFrame(rows); hh = E.ts < CUT
print(f"сделок {len(E)} (монет {E.s.nunique()}): шорт {E.sp.mean()*100:+.2f}% (медиана {E.sp.median()*100:+.2f}, в плюсе {(E.sp > 0).mean():.0%}; "
      f"1-я {E[hh].sp.mean()*100:+.2f} / 2-я {E[~hh].sp.mean()*100:+.2f})")
