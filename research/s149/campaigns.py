"""s149 — кампании наград на других биржах из каналов объявлений (выгрузка s137/tg_crawl.py в папке данных):
Bybit Launchpool и Token Splash, Bitget Launchpool / PoolX / CandyBomb, KuCoin GemPool и BurningDrop, OKX Jumpstart
и Flash Earn. Из поста берутся вид кампании, токен награды и размер пула, начало и конец периода (UTC; «UTC+8» —
сдвиг на 8 ч; без года — год поста; без времени у конца — конец суток). Повторы одной кампании (анонс, старт,
напоминания) сводятся по (биржа, вид, токен, конец). Итог — s149/campaigns.pkl. Запуск из папки с данными:
python3 <repo>/research/s149/campaigns.py"""
import json
import re

import pandas as pd

CH = {"Bybit_Announcements": "bybit", "Bitget_Announcements": "bitget", "Kucoin_News": "kucoin", "OKXAnnouncements": "okx"}
KIND = [("launchpool", r"launchpool"), ("token splash", r"token splash"), ("poolx", r"pool-?x"), ("candybomb", r"candy ?bomb"),
        ("gempool", r"gempool"), ("burningdrop", r"burning ?drop"), ("jumpstart", r"jumpstart"), ("flash earn", r"flash earn")]
SKIP_TOK = {"USDT", "USDC", "USD", "BGB", "MNT", "KCS", "OKB", "BTC", "ETH", "BNB", "SOL", "UTC", "APR", "VIP", "NFT", "AM", "PM",
            "BBSOL", "BTCB", "STETH", "WBTC", "TON", "XRP", "DOGE", "FDUSD", "DAI", "EUR"}
MON = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
MONRE = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
TIME = r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?"
# дата-время: «12 November 2024, 09:00», «May 7, 2024, 11AM», «Aug 13, 12:00», «14:00 on September 16, 2026»,
# «Dec 7, 2021 (06:00 UTC)», «2024-03-01 10:00», «July 31»
DT = [
    ("tmdy", re.compile(TIME + r"\s*(?:\(?utc\)?\s*)?on\s+" + MONRE + r"\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4})?", re.I)),
    ("dmy", re.compile(r"(\d{1,2})(?:st|nd|rd|th)?\s+" + MONRE + r",?\s*(\d{4})?(?:[,\s]+(?:at\s+)?" + TIME + r")?", re.I)),
    ("mdy", re.compile(MONRE + r"\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s*(\d{4}))?(?:[,\s]+\(?(?:at\s+)?" + TIME + r")?", re.I)),
    ("iso", re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[ T]+" + TIME + r")?", re.I)),
]
PERIOD = re.compile(r"(?:event|locking|promotion|mining|campaign|activity|staking|farming|subscription)\s+period\s*:?(.*)", re.I)


def _hm(h, mi, ap):
    if h is None:
        return None
    h, mi = int(h), int(mi or 0)
    if ap:
        ap = ap.lower()
        h = (h % 12) + (12 if ap == "pm" else 0)
    return (h, mi) if h < 24 and mi < 60 else None


def dates(s, year):
    """Все дата-время в строке по порядку: [(позиция, Timestamp UTC, есть ли время)]."""
    out, used = [], []
    for kind, rx in DT:
        for m in rx.finditer(s):
            if any(a < m.end() and m.start() < b for a, b in used):
                continue
            g = m.groups()
            try:
                if kind == "tmdy":
                    hm, mon, d, y = _hm(g[0], g[1], g[2]), MON[g[3][:3].lower()], int(g[4]), int(g[5] or year)
                elif kind == "dmy":
                    d, mon, y, hm = int(g[0]), MON[g[1][:3].lower()], int(g[2] or year), _hm(g[3], g[4], g[5])
                elif kind == "mdy":
                    mon, d, y, hm = MON[g[0][:3].lower()], int(g[1]), int(g[2] or year), _hm(g[3], g[4], g[5])
                else:
                    y, mon, d, hm = int(g[0]), int(g[1]), int(g[2]), _hm(g[3], g[4], g[5])
                t = pd.Timestamp(year=y, month=mon, day=d, tz="UTC")
            except (ValueError, KeyError):
                continue
            if hm:
                t += pd.Timedelta(hours=hm[0], minutes=hm[1])
            out.append((m.start(), t, bool(hm)))
            used.append((m.start(), m.end()))
    return sorted(out, key=lambda x: x[0])


def parse(ex, post_time, text):
    low = text.lower()
    kind = next((k for k, rx in KIND if re.search(rx, low)), None)
    if kind is None:
        return None
    tok = amt = None
    for rx in (r"(?:share|share of|earn a share of|farm a share of|split|get|win)\s+(?:a\s+)?(?:total\s+of\s+)?([\d][\d,\.]*\s*[kmb]?)\s*\$?([A-Z][A-Z0-9]{1,11})\b",
               r"total\s+(?:mining\s+pool|rewards?|airdrop|prize\s+pool)\s*:?\s*([\d][\d,\.]*\s*[kmb]?)\s*\$?([A-Z][A-Z0-9]{1,11})\b",
               r"prize\s+pool\s*:?\s*([\d][\d,\.]*\s*[kmb]?)\s*\$?([A-Z][A-Z0-9]{1,11})\b"):
        for m in re.finditer(rx, text, re.I):
            t = m.group(2).upper()
            if t not in SKIP_TOK:
                tok, amt = t, m.group(1)
                break
        if tok:
            break
    if not tok:
        return None
    a = amt.replace(",", "").strip().lower()
    mult = {"k": 1e3, "m": 1e6, "b": 1e9}.get(a[-1:], 1)
    try:
        amount = float(a.rstrip("kmb")) * mult
    except ValueError:
        amount = None
    year = post_time.year
    per = PERIOD.search(text)
    seg = per.group(1)[:200] if per else text
    ds = dates(seg, year)
    if len(ds) < 2:
        return None
    (_, t0, h0), (_, t1, h1) = ds[0], ds[1]
    if not h1:                                         # «Jul 22 – Aug 4»: конец — конец суток
        t1 += pd.Timedelta(days=1)
    if re.search(r"utc\s*\+\s*8", seg, re.I):
        t0 -= pd.Timedelta(hours=8); t1 -= pd.Timedelta(hours=8)
    if t1 < t0 and t1.year == year:                    # период через Новый год без года
        t1 = t1.replace(year=year + 1)
    if not (pd.Timedelta(hours=1) <= t1 - t0 <= pd.Timedelta(days=60)):
        return None
    if abs((t0 - post_time).days) > 60:
        return None
    lock_same = bool(re.search(r"(?:lock|stake)\s+[^.|\n]{0,40}\b\$?" + re.escape(tok) + r"\b", text, re.I))
    return dict(ex=ex, kind=kind, tok=tok, amount=amount, start=t0, end=t1, post=post_time, lock_same=lock_same)


def main():
    rows = []
    for ch, ex in CH.items():
        try:
            posts = json.load(open(f"s137/tg_{ch}.json"))
        except FileNotFoundError:
            continue
        for pid, ts, text in posts:
            r = parse(ex, pd.Timestamp(ts).tz_convert("UTC") if pd.Timestamp(ts).tzinfo else pd.Timestamp(ts, tz="UTC"), text)
            if r:
                rows.append(r)
    X = pd.DataFrame(rows)
    X = X.sort_values("post").drop_duplicates(["ex", "kind", "tok", "end"], keep="first").reset_index(drop=True)
    X.to_pickle("s149/campaigns.pkl") if __import__("os").makedirs("s149", exist_ok=True) is None else None
    print("кампаний", len(X), X.groupby(["ex", "kind"]).size().to_dict())
    return X


if __name__ == "__main__":
    main()
