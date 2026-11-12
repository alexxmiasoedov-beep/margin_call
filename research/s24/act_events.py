"""Таблица событий кампаний Binance (s24/act_text.pkl) → s24/events.pkl: вид, объявление, начало и конец (самое раннее
начало и самый поздний конец периодов «… (UTC) to … (UTC)» в тексте), токены, токен награды, размер награды в $ (если
указан), фьючерс Binance USDT. Запуск из папки с данными."""
import pickle
import re
import sys
import numpy as np, pandas as pd
sys.path.insert(0, "/home/user/margin_call/research/s23")
from common23 import K, TRADFI, live                              # noqa: E402

D = pickle.load(open("s24/act_text.pkl", "rb"))
PER = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})(?::\d{2})? ?\(UTC\) (?:to|-|–) (\d{4}-\d{2}-\d{2} \d{2}:\d{2})(?::\d{2})? ?\(UTC\)")


def kind(t):
    return ("alpha" if re.search(r"Alpha.*(Competition|Tournament)", t, re.I) else
            "spot_season" if re.search(r"Spot Trading Tournament", t, re.I) else
            "token_tourn" if re.search(r"Trading (Tournament|Competition)|Trade .* and Share|Trade to Share", t, re.I) else
            "hold" if re.search(r"\bHold\b", t) else "other")


def fut(tok):
    for p in ("", "1000", "1000000"):
        if p + tok in K and p + tok not in TRADFI:
            return p + tok
    return None


def usd(t, b):
    m = re.search(r"\$\s?([\d.,]+)\s?([KkMm])\b", t) or re.search(r"\$\s?([\d.,]+)\s?([KkMm])\b", b[:3000])
    if m:
        return float(m.group(1).replace(",", "")) * (1e3 if m.group(2).lower() == "k" else 1e6)
    m = re.search(r"([\d,]+(?:\.\d+)?)\s?(USDT|USDC|FDUSD)\b", t)
    return float(m.group(1).replace(",", "")) if m else np.nan


rows = []
for a in D.values():
    t, b = a["title"], a["body"]
    k = kind(t)
    if k == "other":
        continue
    per = [(pd.Timestamp(s, tz="UTC").timestamp(), pd.Timestamp(e, tz="UTC").timestamp()) for s, e in PER.findall(b)]
    if not per:
        continue
    start, end = min(s for s, _ in per), max(e for _, e in per)
    toks = re.findall(r"\(([A-Z0-9]{1,15})\)", t)
    m = re.match(r"^([A-Z0-9]{2,15}) Trading (?:Tournament|Competition)", t)
    if m:
        toks.append(m.group(1))
    pairs = re.search(r"Trading pair\(s\):\s*([A-Z0-9/ ,]+?)(?: How| Eligib| Total|$)", b)
    if pairs:
        toks += [p.split("/")[0].strip() for p in pairs.group(1).split(",") if "/" in p]
    toks = [x for x in dict.fromkeys(toks) if x not in ("UTC", "USDT", "USDC", "BNB", "BTC", "ETH", "FDUSD")]
    rt = re.search(r"([\d,.]+\s?[MK]?)\s+([A-Z0-9]{2,15})\s+Token Vouchers", t)
    rtok = rt.group(2) if rt else (re.search(r"share [\d,.]+ ([A-Z0-9]{2,15}) tokens", b) or [None, None])[1]
    for x in toks:
        s = fut(x)
        if not s:
            continue
        lo, hi = live(s)
        rows.append(dict(code=a["code"], kind=k, title=t, tok=x, s=s, ts=a["ts"] / 1000, start=start, end=end, dur_d=(end - start) / 86400,
                         nper=len(per), reward_tok=rtok, reward_in_tok=(rtok == x), reward_usd=usd(t, b),
                         age_d=(start - lo) / 86400 if np.isfinite(lo) else np.nan, live_ok=bool(lo <= start - 86400 and hi >= end + 7 * 86400)))
E = pd.DataFrame(rows).sort_values("start").reset_index(drop=True)
E.to_pickle("s24/events.pkl")
print(f"событий с фьючерсом: {len(E)} (монет {E.s.nunique()}); с живым фьючерсом за сутки до начала и 7 суток после конца: {E.live_ok.sum()}")
print(E.groupby("kind").agg(n=("s", "size"), live=("live_ok", "sum"), dur=("dur_d", "median"), in_tok=("reward_in_tok", "sum")))
print(E[["kind", "tok", "s", "dur_d", "reward_tok", "reward_usd", "age_d", "live_ok"]].tail(12).to_string())
