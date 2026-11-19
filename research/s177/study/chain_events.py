"""s177 — перетоки денег между сетями: глубина бесплатной истории и частота событий-кандидатов. Без доходов и цен.

Данные (fetch_chains.py): стейблкоины в сети (DefiLlama, $), TVL сети ($, включает цену родной монеты — «грязный»
поток), оборот DEX сети ($), состав экосистем CoinGecko, протоколы DefiLlama. Мосты DefiLlama — платно (402).

Привязка монеты с перпом Binance к сети: (1) родная монета сети (v2/chains tokenSymbol + ручные поправки);
(2) токен протокола DefiLlama — сеть протокола (поле chain, для Multi-Chain — сеть с наибольшим TVL);
(3) CoinGecko — монета ровно в одной экосистеме из списка (не считая Ethereum). Ethereum как «экосистема»
не берётся: его токены — почти весь рынок альтов.

События по неделям (закрытие недели — воскресенье, UTC):
  W±10 / W±5 : стейблкоины сети за неделю ≥ +10% / ≤ −10% (±5%), если неделей раньше было ≥ 50 млн $;
  Wz         : недельный лог-прирост / ст. откл. за 26 прошлых недель ≤ −2 (отток) или ≥ +2 (приток);
  Q          : поперечная квинтиль — сети с ≥ 50 млн $ по приросту стейблкоинов за 4 недели; нижняя пятая часть;
  T−10, X×0,5: TVL сети за неделю ≤ −10%; оборот DEX за неделю ≤ 0,5 средней недели за прошлые 4.
«Сделок в месяц» = Σ монет-перпов, привязанных к сети события (в своём периоде).
Запуск: python3 -I chain_events.py [папка данных]
"""
import gzip
import json
import warnings
import os
import pickle
import re
import sys
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=RuntimeWarning)  # лог от нулевых рядов (сеть без стейблкоинов)
D = sys.argv[1] if len(sys.argv) > 1 else "/home/user/mc_data"
C = os.path.join(D, "s177", "chains")
RAW = os.path.join(D, "s177", "raw")
PERIODS = [("2020–2022", "2020-10-01", "2022-10-01"), ("2022–2024", "2022-10-01", "2024-10-01"),
           ("2024–2026", "2024-10-01", "2026-11-01")]
NATIVE_FIX = {"BNB": "BSC", "POL": "Polygon", "MATIC": "Polygon", "OP": "OP Mainnet", "ARB": "Arbitrum",
              "TON": "TON", "S": "Sonic", "FTM": "Fantom", "HYPE": "Hyperliquid L1", "ZK": "zkSync Era",
              "STRK": "Starknet", "MNT": "Mantle", "IP": "Story", "EGLD": "MultiversX", "KAIA": "Kaia",
              "KLAY": "Kaia", "XRP": "XRPL", "SOL": "Solana", "AVAX": "Avalanche", "TRX": "Tron", "SUI": "Sui",
              "APT": "Aptos", "SEI": "Sei", "NEAR": "Near", "ADA": "Cardano", "INJ": "Injective",
              "BERA": "Berachain", "MON": "Monad", "XPL": "Plasma", "LINEA": "Linea", "CRO": "Cronos",
              "ALGO": "Algorand", "HBAR": "Hedera", "XLM": "Stellar", "STX": "Stacks", "FLR": "Flare",
              "CELO": "Celo", "KAVA": "Kava", "BLAST": "Blast", "MANTA": "Manta", "SCR": "Scroll", "WLD": "World Chain",
              "ATOM": None, "DOT": None, "ETH": None, "BTC": None}
# не криптовалюты (акции, металлы, индексы, предIPO) — список s173/probe_freq.py
NONCRYPTO = {"XAU", "XAG", "XPT", "XPD", "COPPER", "NATGAS", "CL", "BZ", "AAPL", "MSFT", "AMD", "QQQ", "SPY", "TSM",
             "BABA", "AMC", "CVX", "DIA", "AVGO", "QCOM", "ANET", "PAXG", "USDC", "FDUSD", "TUSD", "USDP", "BTCDOM",
             "DEFI", "BLUEBIRD", "HUT", "APLD", "GPRO", "SKHY", "OPENAI", "ANTHROPIC", "SPCX", "POPMART", "UNITREE",
             "MARSCOIN", "USAR", "SLX", "ESP"}
ALIAS = {"Binance": "BSC", "Optimism": "OP Mainnet", "xDai": "Gnosis", "Klaytn": "Kaia", "zkSync Era": "ZKsync Era",
         "Ripple": "XRPL", "Pulse": "PulseChain", "RSK": "Rootstock", "OKExChain": "OKTChain", "Elrond": "MultiversX",
         "Terra": "Terra Classic", "Op_Bnb": "opBNB", "Doge": "Dogechain"}  # имена сетей API протоколов → API стейблкоинов


def canon(ch):
    return ALIAS.get(ch, ch)


def perp_sets():
    def base(s):
        m = re.match(r"^(1000000|100000|10000|1000|1M)(.+)$", s)
        return m.group(2) if m else s
    tradfi = pickle.load(open(os.path.join(D, "s12", "perp_kind.pkl"), "rb"))["tradfi"]
    out = {}
    for nm, f in (("2020–2022", "s117/fund_2020.pkl"), ("2022–2024", "s117/fund_oos.pkl"),
                  ("2024–2026", "s2/fund2y.pkl")):
        keys = pickle.load(open(os.path.join(D, f), "rb")).keys()
        out[nm] = {("POL" if base(k) == "MATIC" else base(k)) for k in keys if k not in tradfi} - NONCRYPTO
    return out


def jl(path):
    with gzip.open(path) as f:
        return json.load(f)


def series_sc(name):
    fn = os.path.join(C, "sc", name.replace("/", "_") + ".json.gz")
    if not os.path.exists(fn):
        return None
    d = jl(fn)
    if not d:
        return None
    t = pd.to_datetime([int(r["date"]) for r in d], unit="s")
    v = [sum((r.get("totalCirculatingUSD") or {}).values()) for r in d]
    return pd.Series(v, index=t).groupby(level=0).last()


def series_tvl(name):
    fn = os.path.join(C, "tvl", name.replace("/", "_") + ".json.gz")
    if not os.path.exists(fn):
        return None
    d = jl(fn)
    if not d:
        return None
    return pd.Series([r["tvl"] for r in d], index=pd.to_datetime([int(r["date"]) for r in d], unit="s"))


def series_dex(name):
    fn = os.path.join(C, "dex", name.replace("/", "_") + ".json.gz")
    if not os.path.exists(fn):
        return None
    d = jl(fn)
    ch = d.get("totalDataChart") or []
    if not ch:
        return None
    return pd.Series([x[1] for x in ch], index=pd.to_datetime([int(x[0]) for x in ch], unit="s"))


def token_chains(perps_all):
    """монета-перп → сеть (родная монета > протокол DefiLlama > единственная экосистема CoinGecko)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import fetch_chains as F
    m, how = {}, {}
    chains = json.load(open(os.path.join(C, "v2_chains.json")))
    for x in chains:
        s = (x.get("tokenSymbol") or "").upper()
        if s in perps_all and s not in m:
            m[s], how[s] = canon(x["name"]), "родная"
    for s, ch in NATIVE_FIX.items():
        if s in perps_all and ch:
            m[s], how[s] = canon(ch), "родная"
    P = json.load(open(os.path.join(RAW, "api.llama.fi_protocols.json")))
    best = {}
    for p in P:
        s = (p.get("symbol") or "").upper()
        if s in ("", "-") or s not in perps_all or p.get("category") in ("Chain", "CEX", "Bridge",
                                                                         "Canonical Bridge"):
            continue
        ch = p.get("chain")
        if ch in (None, "Multi-Chain"):
            ct = {k: v for k, v in (p.get("chainTvls") or {}).items() if "-" not in k and k not in
                  ("borrowed", "staking", "pool2", "vesting", "treasury", "offers", "doublecounted")}
            if not ct:
                continue
            ch = max(ct, key=ct.get)
        tvl = p.get("tvl") or 0
        if s not in best or tvl > best[s][1]:
            best[s] = (ch, tvl)
    for s, (ch, _) in best.items():
        if s not in m:
            m[s], how[s] = canon(ch), "протокол"
    cg = defaultdict(set)
    for cat, (ch, pages) in F.CG.items():
        for p in range(1, pages + 1):
            fn = os.path.join(C, "cg", f"{cat}_{p}.json.gz")
            if not os.path.exists(fn):
                continue
            d = jl(fn)
            if not isinstance(d, list):
                continue
            for x in d:
                s = (x.get("symbol") or "").upper()
                cid = (x.get("id") or "").lower()
                if any(k in cid for k in ("binance-peg", "bridged", "wrapped", "wormhole", "-peg-", "bsc-")):
                    continue  # обёрнутые копии чужих монет (Binance-Peg DOGE и т. п.) — не «родные» для сети
                if s in perps_all:
                    cg[s].add(canon(ch))
    for s, chs in cg.items():
        if s in m:
            continue
        ne = chs - {"Ethereum"}
        if len(ne) == 1:
            m[s], how[s] = next(iter(ne)), "CoinGecko"
        elif not ne:
            m[s], how[s] = "Ethereum", "CoinGecko"
    return m, how


def weekly(s):
    return s.resample("W-SUN").last()


def main():
    perps = perp_sets()
    allp = set().union(*perps.values())
    tc, how = token_chains(allp)
    print("Привязка монет-перпов к сетям:", len(tc), "из", len(allp), "|", dict(Counter(how.values())))
    per_chain = defaultdict(set)
    for s, ch in tc.items():
        per_chain[ch].add(s)
    print("Сети с наибольшим числом монет-перпов (2024–2026):")
    cnt = {ch: len(v & perps["2024–2026"]) for ch, v in per_chain.items()}
    print("  " + ", ".join(f"{ch} {n}" for ch, n in sorted(cnt.items(), key=lambda x: -x[1])[:25]))
    unmapped = sorted(perps["2024–2026"] - set(tc))
    print(f"  без сети: {len(unmapped)} (например: {', '.join(unmapped[:30])})")

    names = sorted(f[:-8] for f in os.listdir(os.path.join(C, "sc")))
    SC, TV, DX = {}, {}, {}
    for n in names:
        s = series_sc(n)
        if s is not None and s.max() >= 2e7:
            SC[n] = s
    for n in set(SC) | set(per_chain):
        t = series_tvl(n)
        if t is not None:
            TV[n] = t
        x = series_dex(n)
        if x is not None:
            DX[n] = x
    print(f"\nСетей со стейблкоинами ≥ 20 млн $ когда-либо: {len(SC)}; с TVL: {len(TV)}; с DEX: {len(DX)}")
    print("Глубина истории стейблкоинов (первый день > 1 млн $) у сетей с монетами-перпами:")
    rows = []
    for ch in sorted(SC, key=lambda c: -SC[c].iloc[-1]):
        s = SC[ch]
        f1 = s[s > 1e6].index.min()
        rows.append(f"{ch} {f1.date() if f1 is not pd.NaT else '-'}")
    print("  " + "; ".join(rows[:30]))

    def ntok(ch, pn):
        if ch == "Ethereum":
            return 0
        return len(per_chain.get(ch, set()) & perps[pn])

    ev = defaultdict(list)  # тип -> [(chain, week)]
    for ch, s in SC.items():
        w = weekly(s).dropna()
        prev = w.shift(1)
        g = w / prev - 1
        ok = prev >= 5e7
        lg = np.log(w / prev)
        z = lg / lg.rolling(26, min_periods=13).std().shift(1)
        for nm, m in (("W−10", ok & (g <= -0.10)), ("W+10", ok & (g >= 0.10)), ("W−5", ok & (g <= -0.05)),
                      ("W+5", ok & (g >= 0.05)), ("Wz−2", ok & (z <= -2)), ("Wz+2", ok & (z >= 2))):
            for t in g.index[m.fillna(False).values]:
                ev[nm].append((ch, t))
    # поперечная квинтиль по приросту за 4 недели
    W = pd.DataFrame({ch: weekly(s) for ch, s in SC.items()})
    g4 = W / W.shift(4) - 1
    elig = W.shift(4) >= 5e7
    for t in W.index:
        row = g4.loc[t][elig.loc[t].fillna(False)].dropna()
        if len(row) < 10:
            continue
        cut = row.quantile(0.2)
        for ch in row[row <= cut].index:
            ev["Q4н−"].append((ch, t))
    for ch, t in TV.items():
        w = weekly(t).dropna()
        g = w / w.shift(1) - 1
        for tt in g.index[((w.shift(1) >= 5e7) & (g <= -0.10)).fillna(False).values]:
            ev["T−10"].append((ch, tt))
    for ch, x in DX.items():
        w = x.resample("W-SUN").sum()
        base = w.shift(1).rolling(4).mean()
        for tt in w.index[((base >= 5e6) & (w <= 0.5 * base)).fillna(False).values]:
            ev["X×0,5"].append((ch, tt))

    print("\nСобытия в месяц: сетей-событий (без Ethereum) | сделок = монет-перпов этих сетей | доля сделок у 3 главных сетей")
    for nm in ("W−10", "W+10", "W−5", "W+5", "Wz−2", "Wz+2", "Q4н−", "T−10", "X×0,5"):
        e = pd.DataFrame(ev[nm], columns=["chain", "t"])
        parts = []
        for pn, a, z in PERIODS:
            m = (e.t >= a) & (e.t < z) & (e.chain != "Ethereum")
            months = (pd.Timestamp(z) - pd.Timestamp(a)).days / 30.44
            x = e[m]
            tr = x.chain.map(lambda c: ntok(c, pn))
            top = (x.assign(n=tr).groupby("chain").n.sum().sort_values(ascending=False))
            sh = top.head(3).sum() / max(tr.sum(), 1)
            parts.append(f"{pn}: {len(x) / months:5.2f} сетей, {tr.sum() / months:6.1f} сделок "
                         f"(3 сети {sh:.0%}: {', '.join(top.head(3).index)})")
        print(f"  {nm}\n      " + "\n      ".join(parts))
    # сколько сетей в поперечнике
    print("\nСетей со стейблкоинами ≥ 50 млн $ (медиана по неделям) и монет-перпов на них (без Ethereum):")
    for pn, a, z in PERIODS:
        x = W.loc[a:z]
        nch = (x >= 5e7).sum(axis=1).median()
        chs = [c for c in W.columns if (W.loc[a:z, c] >= 5e7).any() and c != "Ethereum"]
        nt = sum(ntok(c, pn) for c in chs)
        print(f"  {pn}: сетей {nch:.0f}, монет-перпов на них {nt}")


def clean_check():
    """Проверка данных: события W±10 по всем стейблкоинам против рядов только USDT + USDC (stablecoin/1, /2).
    Скачок от подключения нового стейблкоина к учёту в сети в чистом ряду не виден."""
    base = os.path.join(C, "coin")
    tot = defaultdict(lambda: defaultdict(float))
    for i in (1, 2):
        fn = os.path.join(base, f"sc_{i}.json")
        if not os.path.exists(fn):
            print("нет", fn)
            return
        d = json.load(open(fn))
        for ch, v in (d.get("chainBalances") or {}).items():
            for r in v.get("tokens") or []:
                tot[ch][int(r["date"])] += float((r.get("circulating") or {}).get("peggedUSD") or 0)
    ev_all, ev_cl = set(), set()
    for ch, dd in tot.items():
        cl = pd.Series(dd)
        cl.index = pd.to_datetime(cl.index, unit="s")
        cl = weekly(cl.sort_index()).dropna()
        al = series_sc(ch)
        if al is None:
            continue
        al = weekly(al).dropna()
        for nm, w, store in (("cl", cl, ev_cl), ("al", al, ev_all)):
            g = w / w.shift(1) - 1
            ok = w.shift(1) >= 5e7
            for t in g.index[(ok & (g.abs() >= 0.10)).fillna(False).values]:
                if ch != "Ethereum" and t >= pd.Timestamp("2020-10-01"):
                    store.add((ch, t, int(np.sign(g.loc[t]))))
    near = lambda e, S: any((e[0], e[1] + pd.Timedelta(weeks=k), e[2]) in S for k in (-1, 0, 1))
    a_in = sum(near(e, ev_cl) for e in ev_all)
    c_in = sum(near(e, ev_all) for e in ev_cl)
    print(f"\nПроверка данных (|прирост за неделю| ≥ 10%, сети ≥ 50 млн $, без Ethereum, с 10.2020):"
          f"\n  событий по всем стейблкоинам {len(ev_all)}, из них видны и в USDT+USDC (±1 нед.) {a_in}"
          f" ({a_in / max(len(ev_all), 1):.0%});\n  событий по USDT+USDC {len(ev_cl)}, видны и во всех {c_in}"
          f" ({c_in / max(len(ev_cl), 1):.0%})")


if __name__ == "__main__":
    main()
    clean_check()
