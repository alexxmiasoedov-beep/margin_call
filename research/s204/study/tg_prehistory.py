#!/usr/bin/env python3
"""s204: предыстория — уведомления Bithumb «… 시세 급변동으로 인한 거래 유의 안내» (до системы 경보제)
и упоминания системы предупреждений в архивах Telegram s26 (bithumb_notice с 2022 г., upbit_news с 05.2025).
Только перечень событий; доходы не считаются.
"""
import json, re, collections

B = json.load(open("/home/user/mc_data/s26/tg_bithumb_notice.json"))
U = json.load(open("/home/user/mc_data/s26/tg_upbit_news.json"))
ev = []
for i, t, x in B:
    if "급변동" in x and "유의 안내" in x:
        m = re.findall(r"\(([A-Z0-9]{2,12})\)", x)
        ev.append((t[:16], m or ["(группа ERC-20/общее)"], x[:90]))
print("Bithumb: уведомлений «시세 급변동 … 거래 유의 안내»", len(ev))
by_m = collections.Counter(t[:7] for t, _, _ in ev)
print("по месяцам:", dict(sorted(by_m.items())))
coins = collections.Counter(c for _, cs, _ in ev for c in cs)
print("монет:", len(coins), coins.most_common(12))
print("первое:", ev[0][:2], "последнее:", ev[-1][:2])
print("\nУведомления о самой системе предупреждений:")
for src, arr in (("bithumb", B), ("upbit", U)):
    for i, t, x in arr:
        if any(k in x for k in ("경보제", "경보 세분화", "유의 안내 방식 변경", "시장 경보", "시장경보")):
            print(src, t[:16], x[:110].replace("\n", " "))
