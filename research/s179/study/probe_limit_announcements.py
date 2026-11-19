"""s179 — объявления Binance об изменении лимитов: частота по трём периодам (только заголовки, без цен).

Запуск: python3 -I probe_limit_announcements.py <папка данных>
Архив — s10/ann.pkl (7192 заголовка разделов 48, 49, 161, 2017–22.10.2026). Разделы обслуживания кошельков и маржи
(157 и др.) в архив не входят — переводы и займы видны только через разделы 48/49/161.
Для объявлений о фандинге (интервал, потолок) из заголовка вынимаются тикеры «XXXUSDT» — монето-события.
"""
import os
import re
import sys
from collections import Counter

import numpy as np
import pandas as pd

D = sys.argv[1] if len(sys.argv) > 1 else "/home/user/mc_data"
PER = [("2020–2022", "2020-10-01", "2022-10-01"), ("2022–2024", "2022-10-01", "2024-10-01"),
       ("2024–2026", "2024-10-01", "2026-10-23")]
TYPES = [
    ("фандинг: интервал начислений", r"Funding Rate Settlement Frequency|Funding Interval|Settlement Frequency"),
    ("фандинг: потолок/пол ставки", r"Capped Funding Rate|Funding Rate Cap|Capped Funding"),
    ("фандинг: прочее (формула, металлы, акции)", r"Funding Rate"),
    ("плечо и ступени маржи перпов", r"Leverage|Margin Tiers|Maintenance Margin"),
    ("защита цены, ценовой коридор, LPP", r"Price Protect|Order Price Cap|Price Cap/Floor|Last Price Protected|Price Limit"),
    ("шаг цены (tick size)", r"Tick Size"),
    ("минимальный размер заявки", r"Minimum Order|Minimum Notional|Min(?:imum)? Notional"),
    ("лимит позиции, открытых заявок", r"Position Limit|Open Order Limit|Maximum Open Order"),
    ("займ: монету добавили в займ (Loans, borrowable)", r"Adds?.*Borrowable|Borrowable.*Adds?"),
    ("маржа: монету сняли с займа (Delist … Borrowable)", r"Delist.*Borrowable"),
    ("маржа: добавление пар и монет", r"Margin.*(?:Will Add|Adds|Add )|(?:Will Add|Adds|Add ).*Margin"),
    ("маржа: лимиты займа", r"Borrowing Limit|Borrow Limit|Max(?:imum)? Borrow"),
    ("ввод и вывод: приостановка, обслуживание сети", r"Suspend.*(?:Deposit|Withdraw)|(?:Deposit|Withdraw).*Suspen|Network Upgrade|Hard Fork|Wallet Maintenance"),
    ("приостановка торгов", r"Suspend(?:s|ed)? Trading|Trading Halt|Halt|Pause.*Trading"),
    ("метки Monitoring / Seed", r"Monitoring Tag|Seed Tag"),
    ("делистинг перпов", r"Delist.*(?:USDⓈ-M|Perpetual|Futures)|Futures Will Delist"),
]


def main():
    o = pd.read_pickle(os.path.join(D, "s10/ann.pkl"))
    df = pd.DataFrame(list(o.values()))
    df["t"] = pd.to_datetime(df.ts, unit="ms", utc=True)
    df = df.sort_values("t")
    print(f"заголовков {len(df)}, с {df.t.min().date()} по {df.t.max().date()}, разделы {dict(Counter(df.cat))}")
    rows = []
    for tname, pat in TYPES:
        hit = df.title.str.contains(pat, regex=True, flags=re.I)
        if tname.startswith("фандинг: прочее"):
            hit &= ~df.title.str.contains(TYPES[0][1] + "|" + TYPES[1][1], regex=True, flags=re.I)
        sub = df[hit]
        line = [tname]
        for pname, a, b in PER:
            ta, tb = pd.Timestamp(a, tz="UTC"), pd.Timestamp(b, tz="UTC")
            n = ((sub.t >= ta) & (sub.t < tb)).sum()
            months = (tb - ta).days / 30.44
            line.append(n / months)
        rows.append(line)
    print("\nОбъявлений в месяц:")
    print(f"  {'тип':46s} " + " ".join(f"{p:>10s}" for p, _, _ in PER))
    for r in rows:
        print(f"  {r[0]:46s} " + " ".join(f"{x:10.2f}" for x in r[1:]))
    # монето-события по фандингу
    print("\nМонето-события в объявлениях о фандинге (тикеры из заголовков, «Multiple» — без списка):")
    for tname, pat in TYPES[:2]:
        sub = df[df.title.str.contains(pat, regex=True, flags=re.I)]
        for pname, a, b in PER:
            ta, tb = pd.Timestamp(a, tz="UTC"), pd.Timestamp(b, tz="UTC")
            s = sub[(sub.t >= ta) & (sub.t < tb)]
            coins = sum(len(set(re.findall(r"\b([0-9A-Z]{2,})USDT\b", x))) for x in s.title)
            multi = s.title.str.contains("Multiple|Selected", regex=True).sum()
            months = (tb - ta).days / 30.44
            print(f"  {tname:34s} {pname}: объявлений {len(s)}, тикеров в заголовках {coins} ({coins / months:.2f} в мес.), "
                  f"объявлений «Multiple/Selected» {multi}")
    # примеры по защите цены и потолку
    for tname, pat in (TYPES[1], TYPES[4], TYPES[9], TYPES[11]):
        sub = df[df.title.str.contains(pat, regex=True, flags=re.I)]
        print(f"\n{tname} — все заголовки ({len(sub)}):")
        for _, r in sub.iterrows():
            print(f"  {r.t.date()} {r.title[:150]}")


if __name__ == "__main__":
    main()
