"""s137 — разбор постов каналов сигналов (кэш s137/tg_<канал>.json, tg_crawl.py) в таблицу событий:
канал, id, время, монета, направление (+1 купить / −1 шорт), цена входа, вид (фьючерсы / спот / памп), тип (призыв / отчёт).
Призыв — монета, направление и уровни (вход, цели или стоп), без признаков отчёта; обновления и разборы («update»,
«analysis») не считаются. Направление без слов long / short / buy — по первой цели против входа. Отчёт — признаки
достигнутой цели (✅, achieved, «Target 1 hit», …) и монета; в шаблоне призыва Cornix «✅» — украшение. Запуск из папки с данными: python3 <repo>/research/s137/calls.py → s137/calls.pkl"""
import glob
import json
import os
import re

import pandas as pd

RES = re.compile(r"✅|✔|☑|achiev|destroyed|booked|(?:target|tp)s?\s*\d*\s*(?:is\s+)?(?:almost\s+)?reached"
                 r"|reached\s+(?:our|its|tp|target|first|second|third|all|\d)|(?:target|tp)s?\s*\d*\s*(?:has\s+been\s+|got\s+|was\s+|is\s+)?hit\b"
                 r"|\bhit\s+(?:our|tp|target|first|second|third|all|\d)|(?<!take-)(?<!take )(?<!take)profit\s*:|%\s*profits?\b"
                 r"|targets?\s+done|all\s+targets|take-?profit\s+target\s*\d|stop-?loss\s+(?:was\s+|got\s+)?hit"
                 r"|\bclosed\s+(?:in|at|with|manually|our|the\s+trade|position|trade)", re.I)
UPD = re.compile(r"\bupdate\b|\banalysis\b", re.I)
STOP = {"USDT", "USDC", "BUSD", "USD", "VIP", "CRYPTO", "BINANCE", "BITCOIN", "SIGNAL", "SIGNALS", "UPDATE", "NEWS",
        "ALTCOIN", "ALTCOINS", "ALTS", "TA", "SPOT", "FUTURES", "LONG", "SHORT", "BUY", "SELL", "TP", "SL", "DCA", "NFA", "DYOR",
        "CRYPTONEWS", "BREAKING", "FED", "CPI", "FOMC", "SP500", "DXY", "GOLD", "USDTD", "BTCD", "TOTAL", "TOTAL2", "TOTAL3",
        "OTHERS", "CRYPTOMCAP", "MARKET", "ANALYSIS", "GEM", "PUMP", "AMA", "GIVEAWAY", "AIRDROP", "FREE", "TRADE", "TRADING",
        "PROFIT", "TARGET", "TARGETS", "ENTRY", "LEVERAGE", "STOPLOSS", "BYBIT", "MEXC", "KUCOIN", "OKX", "GATE", "BITGET", "WEEX",
        "BINGX", "HTX", "HUOBI", "ETF", "SEC", "USA", "US", "UK", "EU", "AI", "NFT", "DEFI", "MEME", "MEMES", "L1", "L2"}
TICK = [re.compile(r"[#$]\s?([A-Za-z0-9]{2,15})\s?/\s?(USDT|BTC|BUSD|USDC|USD)\b"),
        re.compile(r"[#$]?\b([A-Z0-9]{2,15})(USDT|BUSD)\b"),
        re.compile(r"\b([A-Z0-9]{2,15})\s?/\s?(USDT|BTC|BUSD)\b"),
        re.compile(r"[#$]([A-Za-z0-9]{2,15})\b")]
NOTERM = r"(?![\s-]*(?:term|mid|-?mid|squeeze|liquidat|interest|ratio|seller|accumulat|position\s+(?:is|are)))"
LONG_X = [r"direction\s*:?\s*(?:📈\s*)?long", r"\blong\s*set-?up", r"\blonging\b", r"\blong\s*\(\s*\d", r"\blong\s+position",
          r"\bopen\s+long", r"\bbuy\s+(?:setup|signal)", r"\bbuy\b[^.\n]{0,40}\bspot\b", r"\bbought\b", r"\blong\s*-\s",
          r"\bbuying\s+(?:more\s+)?[#$]", r"\bbuy\s+[#$]"]
SHORT_X = [r"direction\s*:?\s*(?:📉\s*)?short", r"\bshort\s*set-?up", r"\bshorting\b", r"\bshort\s*\(\s*\d", r"\bshort\s+position",
           r"\bopen\s+short", r"\bshort\s+signal\b", r"\bshort\s*-\s"]
LEVEL = re.compile(r"entry|enter\b|buy\s+(?:below|between|zone|around|at|here|it|now)|open\s+at|bids?\s+around|\bat\s+\$?\d"
                   r"|buying\s+zone|accumulat|\b(?:between|below|around)\s+\$?\d", re.I)
TGT = re.compile(r"target|\btp\b|take.?profit", re.I)
STP = re.compile(r"stop|\bsl\b|invalidat", re.I)
PRICE = re.compile(r"(?:entry(?:\s*zone)?|enter|buy\s+(?:below|between|zone|around|at)|open\s+at|bids?\s+around"
                   r"|(?:here|price|spot|bought\s+\w+)\s+at|\bbetween|\bbelow|\baround)\s*(?:\d\s*[-–:)]\s*)?[:\-–]?\s*(?:cmp\s*)?"
                   r"\$?\s*([0-9][0-9,]*\.?[0-9]*)", re.I)
TGTPX = re.compile(r"(?:targets?|tp\s*1?)\s*(?:1\s*)?[:\-–]?\s*\$?\s*([0-9][0-9,]*\.?[0-9]*)", re.I)
PUMP = re.compile(r"(?i:coin\s+we\s+(?:have\s+picked\s+to\s+pump|are\s+pumping|picked)\s+today\s+is)\s*:?\s*[#$]?([A-Z0-9]{2,12})\b")
TERSE_NO = re.compile(r"\bplan\b|running|winners?\b|\bout\b|closed?\b|update|look(?:ing)?\s+to|\bwill\b|\bif\b|\bwait|"
                      r"\bnot\b|\bnice\b|profit|\bup\s+\d|\bdown\s+\d", re.I)


def ticker(txt):
    for rx in TICK:
        for m in rx.finditer(txt):
            b = m.group(1).upper()
            if rx.groups == 1:
                b = re.sub(r"(?<=.)(USDT|BUSD|USDC|PERP)$", "", b)
            if b not in STOP and not b.isdigit() and not re.fullmatch(r"\d+[KMBX]?", b):
                return b, (m.group(2).upper() if rx.groups > 1 else "")
    return None, ""


def direction(txt):
    lo = sum(bool(re.search(p, txt, re.I)) for p in LONG_X)
    sh = sum(bool(re.search(p, txt, re.I)) for p in SHORT_X)
    if lo and not sh:
        return 1
    if sh and not lo:
        return -1
    if lo or sh:
        return 0
    lw = len(re.findall(r"\blong\b" + NOTERM, txt, re.I)) + len(re.findall(r"\bbuy\b", txt, re.I))
    sw = len(re.findall(r"\bshort\b" + NOTERM, txt, re.I))
    return 1 if lw and not sw else -1 if sw and not lw else 0


def num(s):
    s = s.replace(",", "") if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", s) else s.replace(",", ".")
    try:
        v = float(s.rstrip("."))
    except ValueError:
        return None
    return v if v > 0 else None


def price(txt):
    m = PRICE.search(txt)
    return num(m.group(1)) if m else None


def parse(ch, pid, ts, txt):
    if not txt:
        return None
    pm = PUMP.search(txt) if ch == "mega_pump_group" else None
    if pm and not RES.search(txt):
        b = pm.group(1).upper()
        return dict(ch=ch, id=pid, t=ts, coin=b, quote="", d=1, px=None, kind="памп", typ="призыв") if b not in STOP else None
    b, quote = ticker(txt)
    if not b:
        return None
    cornix = bool(re.search(r"signal\s*type\s*:", txt, re.I) and re.search(r"entry\s*targe?ts?\s*:", txt, re.I))
    res = bool(RES.search(txt)) and not cornix               # в шаблоне призыва Cornix «✅» бывает украшением
    d = direction(txt)
    spot = bool(re.search(r"\bspot\b|satoshi|\bsats?\b", txt, re.I)) or quote == "BTC"
    kind = "спот" if spot else "фьючерсы"
    if res:
        return dict(ch=ch, id=pid, t=ts, coin=b, quote=quote, d=d, px=None, kind=kind, typ="отчёт")
    if UPD.search(txt):
        return None
    if not (LEVEL.search(txt) or TGT.search(txt) or STP.search(txt) or re.search(r"at\s+market|market\s+price", txt, re.I)):
        words = re.sub(r"https?://\S+", " ", txt).split()
        if not (len(words) <= 12 and d != 0 and not TERSE_NO.search(txt)):   # короткий призыв по рынку: «XXXUSDT SWING LONG»
            return None
    px = None if (quote == "BTC" or re.search(r"satoshi|\bsats?\b", txt, re.I)) else price(txt)
    if d == 0:                                               # слов направления нет — по первой цели против входа
        m = TGTPX.search(txt)
        tg = num(m.group(1)) if m else None
        if not (px and tg) or tg == px:
            return None
        d = 1 if tg > px else -1
    return dict(ch=ch, id=pid, t=ts, coin=b, quote=quote, d=d, px=px, kind=kind, typ="призыв")


def main():
    rows, seen = [], set()
    for f in sorted(glob.glob("s137/tg_*.json")):
        ch = os.path.basename(f)[3:-5].split("__")[0]           # части одного канала — tg_<канал>__<до id>.json
        for pid, ts, txt in json.load(open(f)):
            if (ch, pid) in seen:
                continue
            seen.add((ch, pid))
            r = parse(ch, pid, ts, txt)
            if r:
                rows.append(r)
    X = pd.DataFrame(rows)
    X["t"] = (pd.to_datetime(X.t, utc=True) - pd.Timestamp("1970-01-01", tz="UTC")) // pd.Timedelta(seconds=1)
    X = X.sort_values("t").reset_index(drop=True)
    X.to_pickle("s137/calls.pkl")
    print(X.groupby(["ch", "typ"]).size().unstack(fill_value=0))
    print(X[X.typ == "призыв"].groupby(["kind", "d"]).size())


if __name__ == "__main__":
    main()
