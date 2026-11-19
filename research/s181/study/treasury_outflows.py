"""s181 — разбор переводов собственных токенов С адресов казначейств (collect_outflows.py): куда уходят токены казны
(биржа, кастоди/ММ, DEX и агрегаторы, раздача и вестинг, мосты, стейкинг и DeFi, мультисиги, другие адреса той же
казны, сжигание, неизвестные адреса), второй шаг «получатель → биржа за 7 сут» по сбору s160 (s160/raw), частота
событий в месяц по периодам и сверка недельных падений DefiLlama (treasury_events.py) с переводами в сети.
Метки: s160/sets.json (биржи), s168/work/mm_core.json (ММ), снимок меток Etherscan dawsbot/eth-labels
(s168/dl/ethl_accounts.csv). Только частоты и размеры; доходы и цены после событий не считаются."""
import csv
import glob
import gzip
import json
import os
import re
import sys
import warnings

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common181 as C  # noqa: E402

warnings.filterwarnings("ignore", category=RuntimeWarning)
DAY = 86400
CUST = re.compile(r"prime|anchorage|falconx|bitcoin suisse|copper|bitgo|fireblocks|cumberland|galaxy|wintermute|amber|"
                  r"matrixport|ceffu|hex trust|komainu|cobo|paxos|custody|gsr|jump|dwf|flowdesk|keyrock|b2c2|"
                  r"market mak|otc", re.I)
CLS = [("DEX/агрегатор", re.compile(r"uniswap|sushi|1inch|0x[: ]|0x-protocol|paraswap|cow (protocol|swap)|gpv2|balancer|"
                                    r"curve|kyber|bancor|\bdex\b|router|aggregat|matcha|odos|openocean|metamask swap|"
                                    r"pancake|dodo|zerox|lifi|li\.fi|socket|rango|swap", re.I)),
       ("раздача/вестинг", re.compile(r"sablier|hedgey|vesting|vester|llamapay|superfluid|streamflow|tokentable|"
                                       r"token table|merkle|distributor|airdrop|claim|reward|grant|payroll|disperse",
                                       re.I)),
       ("мост", re.compile(r"bridge|gateway|portal|wormhole|layerzero|polygon|optimism|arbitrum|hop protocol|across|"
                           r"stargate|multichain|celer|axelar|zksync|starknet|base:|linea|scroll|mantle|l1 escrow", re.I)),
       ("стейкинг/DeFi", re.compile(r"aave|compound|staking|stake|lock|escrow|vote|gauge|vault|morpho|maker|lido|"
                                    r"convex|yearn|pendle|eigen|symbiotic|pool|lending|money market|delegat", re.I)),
       ("мультисиг", re.compile(r"safe|multisig|multi-sig|gnosis|treasury|timelock|dao\b|foundation|team|ecosystem",
                                re.I))]


def block_time():
    bt = json.load(open(f"{C.D}/s160/cache_blocktime.json"))
    A = np.array(sorted((int(k), v) for k, v in bt.items()), float)
    last_b, last_t = A[-1]

    def f(b):
        b = np.asarray(b, float)
        t = np.interp(b, A[:, 0], A[:, 1])
        return np.where(b > last_b, last_t + (b - last_b) * 12.0, t)
    return f


def labels():
    L = {}
    with open(f"{C.D}/s168/dl/ethl_accounts.csv") as fh:
        for x in csv.DictReader(fh):
            if x["chainId"] == "1":
                a = x["address"].lower()
                L[a] = (L.get(a, "") + " " + x["label"] + " " + x["nameTag"]).strip()
    for a, n in json.load(open(f"{C.D}/s168/work/mm_core.json")).items():
        L[a.lower()] = (L.get(a.lower(), "") + " market maker " + n).strip()
    return L


def circ_table():
    ids = json.load(open(f"{C.D}/s160/cmc_ids.json"))
    out = {}
    for tok, v in ids.items():
        p = f"{C.D}/s160/circ/{v['id']}.json"
        if os.path.exists(p):
            s = pd.Series({d: c for d, c, _ in json.load(open(p)) if c})
            if len(s):
                s.index = pd.to_datetime(s.index)
                out[tok] = s.sort_index()
    return out


def frac(X, Ct):
    fr = np.full(len(X), np.nan)
    pos = {ix: k for k, ix in enumerate(X.index)}
    for tok, idx in X.groupby("tok").groups.items():
        s = Ct.get(tok)
        if s is None:
            continue
        d = pd.to_datetime(X.loc[idx, "t"], unit="s").dt.normalize().values
        k = np.searchsorted(s.index.values, d, "right") - 1
        v = np.where(k >= 0, s.values[np.clip(k, 0, None)], np.nan)
        fr[[pos[i] for i in idx]] = X.loc[idx, "amt"].values / v
    return fr


def one_per(df, key, gap):
    df = df.sort_values("t")
    keep, last = [], {}
    for r in df.itertuples():
        if r.t - last.get(getattr(r, key), -1e12) >= gap:
            keep.append(r.Index); last[getattr(r, key)] = r.t
    return df.loc[keep]


def main():
    S = json.load(open(f"{C.D}/s160/sets.json"))
    CEX, TOK = S["cex"], S["toks"]
    dla = json.load(open(f"{C.OUT}/dla_treasury.json"))
    owners = {}
    for r in dla:
        for a in r["owners"]:
            owners.setdefault(a, set()).add(r["proto"])
    ptok = {}
    for r in dla:
        ptok.setdefault(r["proto"], set()).update(r["ownTokens"])
    # протокол DefiLlama-Adapters → перп (по файлу адаптера из списка кандидатов и ряду treasury_events)
    cand = json.load(open(f"{C.OUT}/treasury_candidates.json"))
    E0 = pd.read_pickle(f"{C.OUT}/treasury_events.pkl")
    slug_perp = E0.groupby("slug").perp.first().to_dict()
    proto_perp = {}
    for x in cand:
        nm = x["file"][:-3] if x.get("file") else x["slug"]
        if x["slug"] in slug_perp:
            proto_perp[nm] = slug_perp[x["slug"]]
    perp_tok = {v["perp"]: k for k, v in TOK.items()}
    rows = []
    for p in sorted(glob.glob(f"{C.OUT}/out/b*.json.gz")):
        rows += C.jload(p)
    X = pd.DataFrame(rows, columns=["block", "tok", "frm", "to", "amt", "tx"]).drop_duplicates()
    print(f"переводов с адресов казначейств (все 261 токен): {len(X)}; отправителей {X.frm.nunique()}", flush=True)
    bt = block_time()
    X["t"] = bt(X.block.values)
    X["perp"] = X.tok.map(lambda t: TOK[t]["perp"])
    X["protos"] = X.frm.map(lambda a: owners.get(a, set()))
    X["own"] = [bool(tok in set().union(*[ptok.get(q, set()) for q in pr]) if pr else False) or
                any(proto_perp.get(q) == pp for q in pr) for tok, pr, pp in zip(X.tok, X.protos, X.perp)]
    X = X[X.own].copy()
    print(f"из них собственный токен протокола: {len(X)}; протоколов {len({q for s in X.protos for q in s})}; "
          f"токенов {X.tok.nunique()}", flush=True)
    X["frac"] = frac(X, circ_table())
    L = labels()

    def cls(a):
        if a in owners:
            return "та же казна/другая казна"
        if a in ("0x0000000000000000000000000000000000000000", "0x000000000000000000000000000000000000dead"):
            return "сжигание"
        if a in CEX:
            lab = " ".join(CEX[a])
            return "кастоди/ММ" if CUST.search(lab) else "биржа"
        lab = L.get(a, "")
        if lab and CUST.search(lab):
            return "кастоди/ММ"
        for name, rx in CLS:
            if lab and rx.search(lab):
                return name
        return "другая метка" if lab else "неизвестный адрес"
    X["dst"] = X.to.map(cls)
    X["day"] = (X.t // DAY).astype(int)
    X.to_pickle(f"{C.OUT}/treasury_out.pkl")
    # переводы одного дня от одной казны одним получателям складываются
    G = X.groupby(["tok", "perp", "frm", "to", "dst", "day"]).agg(t=("t", "min"), amt=("amt", "sum"), frac=("frac", "sum"),
                                                                 n=("amt", "size")).reset_index()
    print("\nПереводы собственного токена из казны по классам получателя (≥ 0,05% обращения, сутки сложены):")
    g = G[G.frac >= 0.0005]
    for d, y in g.groupby("dst"):
        print(f"  {d:26s} переводов {len(y):5d}; доля обращения медиана {y.frac.median():.2%}; в месяц " +
              " / ".join(f"{C.month_counts(y.t, p):5.2f}" for p in C.PER))
    print("\nСобытия «выход из казны ≥ 0,5% обращения за сутки» (без перекладки между казнами и сжигания; один на перп "
          "за 7 сут), в месяц:")
    out_ = G[~G.dst.isin(["та же казна/другая казна", "сжигание"])]
    day_sum = out_.groupby(["perp", "day"]).agg(t=("t", "min"), frac=("frac", "sum"),
                                                 dst=("dst", lambda s: ",".join(sorted(set(s))))).reset_index()
    for thr in (0.005, 0.01):
        z = one_per(day_sum[day_sum.frac >= thr], "perp", 7 * DAY)
        print(f"  ≥ {thr:.1%}: " + " / ".join(f"{C.month_counts(z.t, p):5.2f}" for p in C.PER) + f"   (всего {len(z)}, "
              f"перпов {z.perp.nunique()})")
    # второй шаг: получатель (не биржа, не казна) → биржа за 7 сут в сборе s160 (≥ 0,05% обращения)
    raw = []
    for p in sorted(glob.glob(f"{C.D}/s160/raw/b*.json.gz")):
        raw += json.load(gzip.open(p, "rt"))
    R = pd.DataFrame(raw, columns=["block", "tok", "frm", "to", "amt", "tx", "li"])
    R = R[R.to.map(lambda a: a in CEX and not CUST.search(" ".join(CEX[a])))]
    R["t"] = bt(R.block.values)
    R["exch"] = R.to.map(lambda a: CEX[a][0])
    mids = G[G.dst.isin(["неизвестный адрес", "другая метка", "мультисиг", "кастоди/ММ"]) & (G.frac >= 0.0005)]
    Rk = R[R.frm.isin(set(mids.to))]
    hops = []
    for r in mids.itertuples():
        y = Rk[(Rk.frm == r.to) & (Rk.tok == r.tok) & (Rk.t >= r.t) & (Rk.t <= r.t + 7 * DAY)]
        if len(y):
            hops.append(dict(perp=r.perp, tok=r.tok, mid=r.to, mid_cls=r.dst, t0=r.t, t1=float(y.t.min()),
                             out_frac=r.frac, dep_amt=float(y.amt.sum()), out_amt=r.amt, exch=",".join(sorted(set(y.exch))),
                             binance=bool((y.exch == "Binance").any())))
    H = pd.DataFrame(hops)
    print(f"\nВторой шаг «казна → посредник → биржа за 7 сут» (посредник получил ≥ 0,05% обращения): цепочек {len(H)} из "
          f"{len(mids)} переводов посредникам")
    if len(H):
        H["dep_frac"] = H.dep_amt / H.out_amt * H.out_frac
        H.to_pickle(f"{C.OUT}/treasury_hops.pkl")
        for thr in (0.0005, 0.005):
            z = one_per(H[H.dep_frac >= thr].rename(columns={"t1": "t"}), "perp", 2 * DAY)
            zb = one_per(H[(H.dep_frac >= thr) & H.binance].rename(columns={"t1": "t"}), "perp", 2 * DAY)
            print(f"  завод посредника ≥ {thr:.2%} обращения (1 на перп за 48 ч): " +
                  " / ".join(f"{C.month_counts(z.t, p):5.2f}" for p in C.PER) + "; на Binance " +
                  " / ".join(f"{C.month_counts(zb.t, p):5.2f}" for p in C.PER) + f"  (всего {len(z)} / {len(zb)})")
        print("  классы посредников:", H.mid_cls.value_counts().to_dict(), "; биржи:",
              H.exch.str.split(",").explode().value_counts().head(6).to_dict())
        print("  задержка перевод → завод, ч: медиана", f"{((H.t1 - H.t0) / 3600).median():.1f}",
              "; доля завода от полученного, медиана", f"{(H.dep_amt / H.out_amt).median():.0%}")
    # сверка недельных падений DefiLlama с переводами в сети (только токены Ethereum из сбора)
    E = E0[(E0.thr == 0.005) & ~E0.revert & E0.perp.isin(set(X.perp))]
    ok = 0
    det = []
    for r in E.itertuples():
        y = X[(X.perp == r.perp) & (X.day >= r.day - 7) & (X.day <= r.day) &
              ~X.dst.isin(["та же казна/другая казна"])]
        hit = y.amt.sum() >= 0.5 * r.drop
        ok += hit
        det.append(dict(slug=r.slug, perp=r.perp, day=r.day, hit=hit,
                        dst=",".join(sorted(set(y.dst))) if len(y) else ""))
    if len(E):
        D = pd.DataFrame(det)
        print(f"\nСверка: недельных падений DefiLlama ≥ 0,5% (без возврата) у токенов Ethereum из сбора — {len(E)}; "
              f"подтверждены переводами из строгого списка владельцев (≥ 50% падения): {ok} ({ok / len(E):.0%})")
        print("  классы получателей в подтверждённых:", D[D.hit].dst.str.split(",").explode().value_counts().to_dict())
        print("  по протоколам (подтверждено/всего):",
              {k: f"{int(v.hit.sum())}/{len(v)}" for k, v in D.groupby("slug")})


if __name__ == "__main__":
    main()
