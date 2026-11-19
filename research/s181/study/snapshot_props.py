"""s181 — предложения Snapshot пространств, связанных с перпами (snapshot_spaces.py): продажа или диверсификация казны,
OTC, маркетмейкер, гранты и бюджеты в токене, выкуп. Частота в месяц по периодам (перп жив на дату создания), доля
принятых, есть ли в тексте дата или график исполнения. Кэш предложений — /home/user/mc_data/s181/snapshot/<id>.json.gz.
Только частоты; доходы и цены не считаются."""
import json
import os
import re
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common181 as C  # noqa: E402

URL = "https://hub.snapshot.org/graphql"
CACHE = f"{C.OUT}/snapshot"
os.makedirs(CACHE, exist_ok=True)
F = "id title body created start end state choices scores scores_total quorum type discussion author"

SALE = re.compile(r"\b(sell|sells|selling|sold|sale|divest\w*|diversif\w*|otc|over[- ]the[- ]counter|"
                  r"(convert|swap|exchang)\w*\s+(\S+\s+){0,5}(to|into|for)\s+(usdc|usdt|dai|usds|stable\w*|eth|weth|steth))\b")
TREAS = re.compile(r"treasur\w*\s+(management|diversif\w*|strategy|allocation|rebalanc\w*|reserve|runway)|"
                   r"(diversif\w*|manage\w*)\s+(\S+\s+){0,3}treasur\w*|runway", re.I)
MM = re.compile(r"market[- ]?mak", re.I)
GRANT = re.compile(r"\b(grant|budget|funding|fund request|compensation|incentive program|liquidity (mining|program|incentive))",
                   re.I)
BUY = re.compile(r"buy[- ]?back", re.I)
DATE = re.compile(r"\b(20\d\d-\d\d-\d\d|\d{1,2}(st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*|"
                  r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(st|nd|rd|th)?\b|q[1-4]\s*20\d\d)",
                  re.I)
SCHED = re.compile(r"over (the next |a period of |a |the )?\d+\s*(days|weeks|months)|\btwap\b|tranche|per (day|week|month)|"
                   r"\b(daily|weekly|monthly)\b|vesting|linear", re.I)
YES = re.compile(r"^\s*(for|yes|yae|yay|approve|accept|in favou?r|support|execute|adopt|ratify|agree)", re.I)


def gql(q):
    code, raw = C.get(URL, data=json.dumps({"query": q}).encode(), headers={"Content-Type": "application/json"})
    if code != 200 or not raw:
        return None
    return json.loads(raw).get("data")


def props(space):
    fn = f"{CACHE}/{space}.json.gz"
    if os.path.exists(fn):
        return C.jload(fn)
    out, skip = [], 0
    while True:
        d = gql('query { proposals(first: 1000, skip: %d, where: {space: %s}, orderBy: "created", orderDirection: asc) '
                '{ %s } }' % (skip, json.dumps(space), F))
        it = (d or {}).get("proposals")
        if it is None:
            time.sleep(10)
            d = gql('query { proposals(first: 1000, skip: %d, where: {space: %s}, orderBy: "created", orderDirection: asc) '
                    '{ %s } }' % (skip, json.dumps(space), F))
            it = (d or {}).get("proposals") or []
        out += it
        if len(it) < 1000 or skip >= 5000:
            break
        skip += 1000
        time.sleep(0.8)
    C.jsave(out, fn)
    time.sleep(0.8)
    return out


def passed(p):
    sc, ch = p.get("scores") or [], p.get("choices") or []
    if p.get("state") != "closed" or not sc or not ch or not any(sc):
        return None
    w = int(np.argmax(sc))
    q = p.get("quorum") or 0
    if q and (p.get("scores_total") or 0) < q:
        return False
    return bool(YES.match(str(ch[w]))) or (w == 0 and not re.match(r"^\s*(against|no|nay|reject|abstain)", str(ch[0]), re.I))


def main():
    SP = json.load(open(f"{C.OUT}/snap_spaces.json"))
    SP = {k: v for k, v in SP.items() if v["n"] >= 5}
    P = C.perps()
    rows = []
    for i, (sid, v) in enumerate(sorted(SP.items())):
        L = props(sid)
        syms = {C.base(p).lower() for p in v["perps"]} | {str(v.get("symbol") or "").lower().lstrip("v")}
        for p in L:
            title = str(p.get("title") or "")
            body = str(p.get("body") or "")[:20000]
            tl, bl = title.lower(), body.lower()
            own = any(re.search(r"\b" + re.escape(s) + r"\b", tl + " " + bl) for s in syms if s) or \
                bool(re.search(r"(native|governance|protocol|dao)[- ]token|treasur", tl + " " + bl))
            sale_t = bool(SALE.search(tl)) and not BUY.search(tl)
            sale_b = bool(SALE.search(bl)) and bool(re.search(r"treasur", bl)) and own and not BUY.search(tl)
            treas_t = bool(TREAS.search(tl))
            for perp in v["perps"]:
                rows.append(dict(space=sid, perp=perp, t=p.get("created") or 0, end=p.get("end") or 0, title=title[:140],
                                 sale_t=sale_t, sale_b=sale_b, treas_t=treas_t, mm=bool(MM.search(tl)),
                                 grant_t=bool(GRANT.search(tl)), buy_t=bool(BUY.search(tl)), own=own,
                                 passed=passed(p), date=bool(DATE.search(bl)), sched=bool(SCHED.search(bl)),
                                 alive=C.alive(P[perp], p.get("created") or 0) if perp in P else False))
        if i % 20 == 0:
            print(f"  {i + 1}/{len(SP)} {sid}: предложений {len(L)}", flush=True)
    X = pd.DataFrame(rows)
    X.to_pickle(f"{C.OUT}/snapshot_props.pkl")
    print(f"\nпредложений (пространство × перп): {len(X)}; пространств {X.space.nunique()}; перпов {X.perp.nunique()}")
    A = X[X.alive]
    print(f"при живом перпе: {len(A)}")
    print("\nВ месяц по периодам (при живом перпе):")
    cls = [("все предложения", A),
           ("продажа/диверсификация/OTC — в заголовке", A[A.sale_t]),
           ("  …и принято", A[A.sale_t & (A.passed == True)]),  # noqa: E712
           ("  …принято и есть дата или график", A[A.sale_t & (A.passed == True) & (A.date | A.sched)]),  # noqa: E712
           ("управление казной/runway — в заголовке", A[A.treas_t]),
           ("продажа или казна — в заголовке", A[A.sale_t | A.treas_t]),
           ("  …и принято", A[(A.sale_t | A.treas_t) & (A.passed == True)]),  # noqa: E712
           ("продажа в тексте + казна + свой токен", A[A.sale_b]),
           ("маркетмейкер — в заголовке", A[A.mm]),
           ("гранты/бюджеты/программы — в заголовке", A[A.grant_t]),
           ("выкуп (buyback) — в заголовке", A[A.buy_t])]
    for lab, y in cls:
        print(f"  {lab:48s} " + " / ".join(f"{C.month_counts(y.t, p):6.2f}" for p in C.PER) + f"   (всего {len(y)}, "
              f"перпов {y.perp.nunique()})")
    s = A[A.sale_t]
    print("\nпродажа в заголовке — пространства:", s.groupby("space").size().sort_values(ascending=False).head(15).to_dict())
    print("доля принятых:", f"{(s.passed == True).mean():.0%}", "с датой или графиком:", f"{(s.date | s.sched).mean():.0%}")  # noqa: E712
    print("\nпримеры заголовков (продажа/диверсификация, принято):")
    for r in s[s.passed == True].sort_values("t").itertuples():  # noqa: E712
        print(f"  {pd.Timestamp(r.t, unit='s').date()} {r.space:28s} {r.perp:8s} {r.title}")


if __name__ == "__main__":
    main()
