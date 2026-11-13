"""События корейских бирж из Telegram-уведомлений (s25/upbit_news.json — официальный канал Upbit с 05.2025;
s26/tg_bithumb_notice.json — неофициальное зеркало ленты Bithumb, без пачки повторов 03–04.05.2026).
Виды: «촉구» — призыв к осторожности (резкие колебания цены, взлом; часто за часы–сутки до предупреждения);
«предупреждение» — назначение «유의 종목» (投资注意: через 2–4 недели снятие или делистинг); «продление»; «снятие»;
«делистинг» — объявление о прекращении торгов (с датой окончания, обычно через ~месяц). Вид определяется для каждой монеты
по ближайшему ключевому слову после её тикера («만트라(MANTRA) … 지정 연장, 질리카(ZIL) 거래지원 종료» — два события).
Монета → фьючерс Binance USDT (s2/k2y.pkl). Время — время поста (UTC). Итог — s26/events.pkl. Запуск из папки с данными."""
import json
import os
import re
import sys
import pandas as pd
sys.path.insert(0, "/home/user/margin_call/research/s23")
from common23 import K, TRADFI                                    # noqa: E402

SKIP = {"USDT", "USDC", "BTC", "ETH", "KRW", "AI", "NFT", "DAO", "DEX", "LP"}
KEYS = [("снятие", r"지정\s?해제|촉구\s?해제"),
        ("продление", r"지정\s?(기간\s?)?연장"),
        ("предупреждение", r"유의\s?(종목\s?)?지정(?!\s?(해제|기간|연장|정책))"),
        ("촉구", r"유의\s?촉구(?!\s?해제)|거래\s?유의\s?안내"),
        ("делистинг", r"거래지원\s?종료|상장\s?폐지")]
NOT_EVENT = r"연기|철회|취소|변경|통합|리브랜딩|일정 안내|예정일"


def fut(tok):
    for p in ("", "1000", "1000000"):
        if p + tok in K and p + tok not in TRADFI:
            return p + tok
    return None


def kinds(head):
    """[(тикер, вид)] — вид по ближайшему ключевому слову после тикера."""
    if re.search(NOT_EVENT, head):
        return []
    marks = []
    for k, rx in KEYS:
        for m in re.finditer(rx, head):
            marks.append((m.start(), k))
    marks.sort()
    out = []
    # списком после ключевого слова: «지정 해제(APM, VELO) 및 거래지원 종료(BCD, WTC)»
    for k, rx in KEYS:
        for m in re.finditer(f"(?:{rx})\\s?\\((?P<lst>[A-Z0-9]+(?:,\\s?[A-Z0-9]+)+|[A-Z0-9]{{2,15}})\\)", head):
            out += [(x.strip(), k) for x in m.group("lst").split(",")]
    for m in re.finditer(r"\(([A-Z0-9]{1,15})\)", head):
        tok = m.group(1)
        if tok in SKIP or tok.isdigit():
            continue
        if any(tok == x for x, _ in out):
            continue
        nxt = [k for pos, k in marks if pos > m.end()]
        if nxt:
            out.append((tok, nxt[0]))
    return [(x, k) for x, k in out if x not in SKIP and not x.isdigit()]


rows = []
# выгрузка s25; та же лента — tg_crawl.py upbit_news 2025-05-01 (s26/tg_upbit_news.json, отличается только пробелами)
UPB = "s25/upbit_news.json" if os.path.exists("s25/upbit_news.json") else "s26/tg_upbit_news.json"
src = [("upbit", json.load(open(UPB)))]
if os.path.exists("s26/tg_bithumb_notice.json"):
    src.append(("bithumb", [p for p in json.load(open("s26/tg_bithumb_notice.json")) if not 3090 <= p[0] <= 25277]))
for ex, posts in src:
    for pid, t, text in posts:
        head = re.split(r"https?://|🔗", text)[0]
        if ex == "upbit" and not head.startswith("[거래]"):
            continue
        ts = pd.Timestamp(t).tz_convert("UTC").timestamp()
        for tok, k in kinds(head):
            end = None
            m = re.search(r"\((\d{1,2})/(\d{1,2}) (\d{1,2}):(\d{2})\)", head)
            if k == "делистинг" and m:
                d0 = pd.Timestamp(ts, unit="s")
                y = d0.year + (1 if int(m.group(1)) < d0.month else 0)
                end = pd.Timestamp(year=y, month=int(m.group(1)), day=int(m.group(2)), hour=int(m.group(3)),
                                   minute=int(m.group(4)), tz="Asia/Seoul").timestamp()
            rows.append(dict(ex=ex, kind=k, tok=tok, s=fut(tok), ts=ts, end=end, pid=pid, text=head.strip()[:160]))
E = pd.DataFrame(rows).sort_values("ts")
# повторы одного поста (зеркало иногда публикует уведомление дважды) — первое появление за 3 суток
keep, last = [], {}
for i, r in E.iterrows():
    key = (r.ex, r.kind, r.tok)
    if key in last and r.ts - last[key] < 3 * 86400:
        continue
    last[key] = r.ts
    keep.append(i)
E = E.loc[keep].reset_index(drop=True)
E.to_pickle("s26/events.pkl")
print(f"событий {len(E)}; с фьючерсом Binance {E.s.notna().sum()}")
print(E.groupby(["ex", "kind"]).agg(n=("tok", "size"), fut=("s", lambda x: x.notna().sum()),
                                    first=("ts", lambda x: pd.Timestamp(x.min(), unit="s").strftime("%Y-%m-%d"))).to_string())
