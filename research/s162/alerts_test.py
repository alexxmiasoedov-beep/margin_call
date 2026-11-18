"""s162 — шорт после алерта BlockBeats или Odaily о заводе альткоина на биржу (гипотеза — ВЫВОДЫ.md, записана до расчёта).
Посты — s137/tg_theblockbeats__*.json и s137/tg_Odaily_News__*.json в папке данных. Событие: слово завода + биржа + тикер
с перпом Binance (первый после «枚» или «$», без стейблкоинов и мейджоров), по монете раз в 48 ч. Шорт на закрытии первой
15-мин свечи не раньше чем через 5 мин после поста: 24 ч, стоп 25%; для отчёта 48 ч, хедж, плацебо, «инсайдеры».
Запуск в папке периода с MC_K/MC_F: python3 <repo>/research/s162/alerts_test.py <период>; сводка: python3 … report"""
import glob
import json
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s141"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
OUT, DAY = "/home/user/mc_data", 86400
PER = {"2022–2024": ("2023-03-01", "2024-10-01", "2023-12-01"), "2024–2026": ("2024-10-01", "2026-10-17", "2025-12-01")}
EX = re.compile(r"(币安|Binance|OKX|欧易|Bybit|Coinbase|Bitget|Gate|KuCoin|HTX|火币|MEXC|Kraken|Upbit|Bithumb|交易所|CEX)", re.I)
DEP = re.compile(r"(存入|转入|充值|充入|转至|转移至|deposit)", re.I)
MM = re.compile(r"(做市商|Wintermute|DWF|GSR|Amber|Flowdesk|Galaxy|Cumberland|Jump|FalconX|B2C2|Auros|Selini|Presto|Abraxas|Gotbit|Laser)", re.I)
VC = re.compile(r"(机构|投资机构|风投|VC|投资方|早期投资者|私募|Polychain|Paradigm|a16z|Multicoin|Pantera|Maven|Spartan|Hashed|Delphi|"
                r"Mechanism|Arrington|Fenbushi|Animoca|Coinbase Ventures|Binance Labs|YZi)", re.I)
TEAM = re.compile(r"(团队|项目方|基金会|国库|开发者|多签|部署|生态|金库|Treasury|Foundation|Team)", re.I)
UNL = re.compile(r"解锁")
WHALE = re.compile(r"(巨鲸|鲸鱼|whale)", re.I)
STABLE = {"USDT", "USDC", "DAI", "USDE", "FDUSD", "PYUSD", "USD1", "USDS", "TUSD", "BUSD", "RLUSD", "USDG", "EURC", "ETF", "CEX", "DEX",
          "USD", "AI", "RWA", "TVL", "DAO", "NFT", "SEC", "CEO", "API", "APP", "UTC", "OTC", "PNL"}
BIG = {"BTC", "ETH", "WBTC", "WETH", "STETH", "WSTETH", "CBBTC", "SOL", "BNB", "XRP", "TRX"}


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def posts():
    out = {}
    for p in glob.glob(f"{OUT}/s137/tg_theblockbeats*.json") + glob.glob(f"{OUT}/s137/tg_Odaily_News*.json"):
        src = "bb" if "blockbeats" in p else "od"
        for pid, t, s in json.load(open(p)):
            out[(src, int(pid))] = (t, s)
    rows = []
    for (src, pid), (t, s) in out.items():
        if not DEP.search(s) or not EX.search(s):
            continue
        syms = [x.upper() for x in re.findall(r"枚\s*\$?([A-Za-z][A-Za-z0-9]{1,11})", s) + re.findall(r"\$([A-Za-z][A-Za-z0-9]{1,11})", s)]
        alts = [x for x in syms if x not in STABLE and x not in BIG]
        if not alts:
            continue
        cat = "MM" if MM.search(s) else "VC" if VC.search(s) else "team" if TEAM.search(s) else "unlock" if UNL.search(s) \
            else "whale" if WHALE.search(s) else "other"
        rows.append(dict(src=src, pid=pid, t=int(pd.Timestamp(t).timestamp()), sym=alts[0], cat=cat, text=s[:160]))
    return pd.DataFrame(rows)


def run(per):
    from common import K, fut_of, live, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    from flow_test import alt_index  # noqa: E402
    t0, t1 = ts(PER[per][0]), ts(PER[per][1])
    T_, I_ = alt_index(K)

    def mv(a, b):
        i = int(np.searchsorted(T_, a - 900, "right")) - 1; j = int(np.searchsorted(T_, b - 900, "right")) - 1
        return I_[j] / I_[i] - 1 if 0 <= i <= j < len(I_) else np.nan

    P = posts().sort_values("t")
    P["perp"] = P.sym.map(lambda x: fut_of(x)[0])
    P = P.dropna(subset=["perp"])
    rows, last = [], {}
    for r in P.itertuples():
        if not (t0 <= r.t < t1) or r.t - last.get(r.perp, -10 ** 12) < 48 * 3600:
            continue
        lo, hi = live(r.perp)
        te = int(-(-(r.t + 300) // 900) * 900)
        if not np.isfinite(lo) or te < lo + DAY:
            continue
        i = idx_at(r.perp, te)
        if i is None or int(K[r.perp]["t"][i]) + 900 != te:
            continue
        x = trade(r.perp, i, tp=None, sl=0.25, hold_h=24, side=-1)
        if not x:
            continue
        last[r.perp] = r.t
        y = trade(r.perp, i, tp=None, sl=0.25, hold_h=48, side=-1)
        t_end = int(K[r.perp]["t"][i]) + 900 + int(x["bars"]) * 900
        pl = [w["net"] for w in (trade(r.perp, j, tp=None, sl=0.25, hold_h=24, side=-1) for j in
                                 (idx_at(r.perp, te - b * DAY) for b in (45, 90, 135)) if j is not None) if w]
        rows.append(dict(s=r.perp, t=te, cat=r.cat, src=r.src, net=x["net"], why=x["why"], n48=y["net"] if y else np.nan,
                         hed=x["net"] + mv(te, t_end), pl=np.mean(pl) if pl else np.nan))
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/s162_{per}.pkl")
    print(per, "событий", len(X), X.cat.value_counts().to_dict() if len(X) else {}, flush=True)


def report():
    from oi_test import ct  # noqa: E402
    for per, (a, b, cut) in PER.items():
        X = pd.read_pickle(f"{OUT}/s162_{per}.pkl"); months = (ts(b) - ts(a)) / (30.4 * DAY); c = ts(cut)
        print(f"\n{per}:")
        for name, x in (("все алерты (основная)", X), ("инсайдеры: маркетмейкер, фонд, команда", X[X.cat.isin(["MM", "VC", "team"])]),
                        ("киты", X[X.cat == "whale"]), ("прочие", X[X.cat == "other"])):
            if len(x) < 8:
                print(f"  {name}: n={len(x)}"); continue
            m, t, n = ct(x.net, x.t); mh, th, _ = ct(x.hed.dropna(), x.t[x.hed.notna()]); m48, t48, _ = ct(x.n48.dropna(), x.t[x.n48.notna()])
            dp = (x.net - x.pl).dropna(); md, td, _ = ct(dp, x.t[(x.net - x.pl).notna()])
            print(f"  {name:38s} n={n:4d} ({n / months:4.1f}/мес) 24 ч {m:+.2%} (t {t:+.1f}) | половины {x[x.t < c].net.mean():+.2%} / "
                  f"{x[x.t >= c].net.mean():+.2%} | с хеджем {mh:+.2%} | 48 ч {m48:+.2%} (t {t48:+.1f}) | сверх плацебо {md:+.2%} (t {td:+.1f})")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
