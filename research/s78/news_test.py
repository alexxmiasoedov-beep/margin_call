"""s78 — внимание корейской розницы по ленте Coinness (гипотеза — ВЫВОДЫ.md, записана до скачивания). Заголовок — текст
в первых квадратных скобках поста; монета — тикер фьючерса Binance в заголовке (в скобках или отдельным словом), без
лидеров 🔝, BNB, TRX, стейблкоинов, тикеров из 1–2 букв и частых английских сокращений. Событие — первое за 7 сут
упоминание монеты в заголовке без слов о листинге, делистинге, предупреждениях и вводе-выводе; фьючерс ≥ 30 сут.
Шорт на закрытии 15-мин свечи, в которую вышел пост; 10/25/48 (основной) и 7 сут со стопом 50%; плацебо — та же монета
за 45/90/135 сут. Запуск из папки с данными."""
import json
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, fut_of, live, trade  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402

MAJ = {"XRP", "BTC", "ETH", "DOGE", "SOL", "SUI", "ONDO", "ADA", "WLD", "SHIB", "1000SHIB", "BNB", "TRX", "USDT", "USDC",
       "USDE", "USD1", "FDUSD", "DAI"}
STOP = {"ATH", "ETF", "SEC", "CEO", "CFO", "CTO", "IPO", "FOMC", "CPI", "PPI", "PCE", "GDP", "USD", "KRW", "JPY", "EUR",
        "NFT", "OTC", "API", "TVL", "RWA", "DEX", "CEX", "DAO", "ONE", "MOVE", "ACT", "SUN", "GAS", "NEW", "TOP", "BIG", "WIN",
        "MAX", "SAFE", "REAL", "OPEN", "HIGH", "LOW", "BANK", "PEOPLE", "CAT", "DOG", "BOND", "FUN", "GOOD", "HOT", "KEY",
        "THE", "AND", "FOR", "ALL", "NOT", "CFTC", "FBI", "DOJ", "IRS", "FSC", "FSS", "BOJ", "ECB", "FED", "SNS", "APP",
        "LLM", "GPU", "AGI", "ESG", "IMF", "OECD", "NYSE", "CME", "SPY", "QQQ", "NVDA", "TSLA", "MSTR", "COIN", "HOOD",
        "CRCL", "AAPL", "META", "MSFT", "AMZN", "GOOGL", "INTC", "AMD", "PLTR", "USA", "UAE", "UK", "EU", "ID", "TV", "PR"}
SKIP_WORDS = ("상장", "거래지원", "거래 지원", "유의", "입출금", "입금", "출금", "원화마켓", "원화 마켓", "마켓 추가")
TOK = re.compile(r"(?<![A-Za-z0-9])([A-Z][A-Z0-9]{2,11})(?![A-Za-z0-9])")


def posts():
    rows = []
    for line in open("s78/coinness.jsonl"):
        n, ts, txt = json.loads(line)
        m = re.match(r"\s*\[([^\]]+)\]", txt)
        if not m:
            continue
        rows.append((pd.Timestamp(ts).timestamp(), m.group(1)))
    return sorted(rows)


def mentions(P):
    sym_of = {}
    out = []
    for t, h in P:
        if any(w in h for w in SKIP_WORDS):
            continue
        seen = set()
        for tok in TOK.findall(h):
            if tok in STOP or tok in MAJ:
                continue
            if tok not in sym_of:
                s, _ = fut_of(tok)
                sym_of[tok] = s if s in K else None
            s = sym_of[tok]
            if s and s not in MAJ and s not in seen:
                seen.add(s); out.append((t, s, h))
    return out


def main():
    P = posts()
    M = mentions(P)
    print(f"Постов с заголовком: {len(P)} ({pd.Timestamp(P[0][0], unit='s'):%d.%m.%Y} … {pd.Timestamp(P[-1][0], unit='s'):%d.%m.%Y});"
          f" упоминаний монет с фьючерсом: {len(M)}")
    S65 = pd.read_pickle("s65/trades.pkl"); S49 = pd.read_pickle("s49/trades.pkl"); S49 = S49[S49.share >= 0.259]
    S20 = pd.read_pickle("s20/trades.pkl"); S20 = S20[S20.journal == "🇰🇷"]
    other = {}
    for s, t in list(zip(S65.s, S65.t)) + list(zip(S49.s, S49.t)) + list(zip(S20.s, S20.te)):
        other.setdefault(s, []).append(t)
    other = {s: np.array(v) for s, v in other.items()}
    EX = {"S_10_25": dict(tp=0.10, sl=0.25, hold_h=48), "S_7d": dict(tp=None, sl=0.50, hold_h=168)}
    rows, last = [], {}
    for T, s, h in M:
        prev = last.get(s, -1e18); last[s] = T
        if T - prev < 7 * DAY:
            continue
        lo, hi = live(s)
        if T < lo + 30 * DAY or T + 7 * DAY > hi:
            continue
        t = K[s]["t"]; i = int(np.searchsorted(t, T, "right")) - 1
        if i < 96 or t[i] + 900 <= T or K[s]["qv"][i] <= 0:
            continue
        c = K[s]["c"]; o = other.get(s, np.zeros(0))
        d = dict(s=s, t=T, head=h, r24=float(c[i] / c[i - 96] - 1), ov=bool(((o < T) & (o >= T - DAY)).any()))
        for nm, kw in EX.items():
            x = trade(s, i, side=-1, **kw)
            d[nm] = x["net"] if x else np.nan
            p = []
            for dd in (45, 90, 135):
                T2 = T - dd * DAY; j = int(np.searchsorted(t, T2, "right")) - 1
                if j >= 96 and T2 >= lo and (y := trade(s, j, side=-1, **kw)):
                    p.append(y["net"])
            d["pl_" + nm] = np.mean(p) if p else np.nan
        rows.append(d)
    X = pd.DataFrame(rows)
    X.to_pickle("s78/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"Событий: {len(X)} ({len(X) / months:.1f} в месяц); после роста ≥ 10% за 24 ч: {(X.r24 >= 0.10).mean():.0%};"
          f" с 🔝 🛒 🇰🇷 за 24 ч: {X.ov.mean():.0%}")
    for lab, x0 in (("все (основная)", X), ("после роста ≥ 10%", X[X.r24 >= 0.10]), ("остальные", X[X.r24 < 0.10]),
                    ("без 🔝 🛒 🇰🇷", X[~X.ov])):
        for col in EX:
            x = x0[x0[col].notna()]
            if len(x) < 8:
                continue
            m, t_, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
            h1, h2 = x[x.t < CUT], x[x.t >= CUT]
            (m1, t1, _), (m2, t2, _) = ct(h1[col], h1.t), ct(h2[col], h2.t)
            print(f"  {lab:18s} {col:8s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t_:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
                  f" половины {m1:+6.2%} (t {t1:+4.1f}) / {m2:+6.2%} (t {t2:+4.1f}) | плацебо {x['pl_' + col].mean():+6.2%},"
                  f" разница {dp:+6.2%} (t {tp:+4.1f})")
    print("\nПримеры заголовков:")
    for h in X.sample(min(12, len(X)), random_state=1)["head"].values:
        print("  ", h[:110])


if __name__ == "__main__":
    main()
