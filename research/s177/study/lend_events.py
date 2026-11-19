"""s177 — займы альткоинов в DeFi-кредитовании как ончейн-аналог шорт-интереса: охват данных и частота событий.

Доходы, цены после событий и сделки НЕ считаются. Только: сколько займа, у каких монет с перпом Binance,
и сколько событий-кандидатов в месяц по годам и трём периодам.

Данные — история протоколов DefiLlama (бесплатно, api.llama.fi/protocol/<slug>, скачана fetch_lend.py):
по дням и сетям «<Сеть>» (лежит в пуле, ед. токена) и «<Сеть>-borrowed» (выдано в займ). Предложение пула
s = лежит + выдано, загрузка U = выдано / s. Платная история ставок (yields chartLendBorrow) закрыта — ставка займа
в моделях с изломом есть монотонная функция U, поэтому «ставка ↑» здесь = «U ↑».

События (монета = сумма по всем протоколам и сетям; одна монета — не чаще раза в 7 сут):
  D  «сдвиг спроса» (Cohen–Diether–Malloy): займ в ед. токена за 3 сут ≥ ×1,3 и U выросла; займ ≥ 1 млн $
     (и ≥ 0,5 млн $ тремя сутками раньше — против скачков 0 → X из-за смены ключей в данных);
  Dp «чистый спрос»: как D, и предложение в ед. токена за 3 сут в пределах ±10%;
  S  «сдвиг предложения»: займ ≥ ×1,3, а U не выросла (предложение росло быстрее);
  C  «закрытие шортов»: займ за 3 сут ≤ ×0,7, займ трое суток назад ≥ 1 млн $;
  U90 (пул протокол-сеть-монета, только пулы общего типа): загрузка пересекла 90% снизу, первый раз за 30 сут,
     займ пула ≥ 1 млн $.
Запуск: python3 -I lend_events.py [папка данных]
"""
import gzip
import json
import os
import pickle
import re
import sys
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

D = sys.argv[1] if len(sys.argv) > 1 else "/home/user/mc_data"
PROTO = os.path.join(D, "s177", "proto")
CACHE = os.path.join(D, "s177", "lend_panel.pkl")

# Пулы общего типа: «лежит в пуле» = доступная к займу ликвидность (как Aave / Compound).
POOLED = {
    "aave-v1", "aave-v2", "aave-v3", "compound-v1", "compound-v2", "cream-lending", "iron-bank", "venus-core-pool",
    "venus-isolated-pools", "radiant-v1", "radiant-v2", "geist-finance", "granary-finance", "hundred-finance",
    "euler-v1", "strike", "dforce-lending", "inverse-finance-frontier", "save", "larix", "port-finance",
    "apricot-finance", "jet-v1", "marginfi-lending", "kamino-lend", "jupiter-lend", "benqi-lending", "justlend-v1",
    "tectonic", "scream", "wepiggy", "liqee", "lendhub", "channels-finance", "qubit", "annex", "green-planet",
    "apeswap-lending", "fortress-loans", "agave", "sonne-finance", "lodestar-v1", "seamless-v1", "zerolend-lending",
    "lendle-pooled-markets", "mendi-finance", "moonwell-lending", "moonwell-apollo", "navi-lending", "suilend",
    "scallop-lend", "echelon-market", "aries-markets", "joule-finance", "sparklend", "kinza-finance", "layerbank",
    "takara-lend", "yeilend", "hyperlend-pooled", "folks-finance-lending", "hatom-lending", "liqwid", "mars-lend",
    "umee", "ooki", "rhea-lend", "nostra-money-market", "zklend", "orbit-protocol", "klap", "kava-lend",
    "moola-market",
}
SKIP = {"tarot"}  # займ под LP-фарминг, не шорт

STABLE = {"USDC", "USDT", "DAI", "BUSD", "TUSD", "USDP", "PAX", "GUSD", "SUSD", "FEI", "FRAX", "UST", "USTC", "LUSD",
          "MIM", "USDD", "USDJ", "FDUSD", "PYUSD", "USDE", "USDS", "GHO", "CRVUSD", "RLUSD", "USD1", "USDG", "EURC",
          "EURS", "AGEUR", "JEUR", "USDB", "USDBC", "USDT0", "USD₮0", "DOLA", "RAI", "UXD", "USDH", "USDM", "USDY",
          "AUSD", "CASH", "USX", "U", "VAI", "SAI", "HUSD", "ALUSD", "MUSD", "BOLD", "USDA", "XUSD", "TRYB", "EURE",
          "USDTB", "USR", "DEUSD", "SUSDE", "SDAI", "SUSDS", "USDQ", "USD0", "USDF", "AVUSD", "USDN", "OUSD"}
MAJOR = {"BTC", "ETH"}
WRAP = {  # обёртки → базовая монета перпа
    "WETH": "ETH", "WBTC": "BTC", "WAVAX": "AVAX", "WMATIC": "POL", "MATIC": "POL", "WPOL": "POL", "WBNB": "BNB",
    "WSOL": "SOL", "WFTM": "FTM", "WS": "S", "WHYPE": "HYPE", "WSEI": "SEI", "WMON": "MON", "WKAVA": "KAVA",
    "WCRO": "CRO", "WONE": "ONE", "WGLMR": "GLMR", "WMOVR": "MOVR", "WCELO": "CELO", "WTRX": "TRX", "TRON": "TRX",
    "WEGLD": "EGLD", "WROSE": "ROSE", "WMNT": "MNT", "WFLR": "FLR", "WFLOW": "FLOW", "WAPT": "APT", "WNEAR": "NEAR",
    "WKLAY": "KLAY", "WBERA": "BERA", "WIP": "IP", "WZETA": "ZETA", "WOKB": "OKB", "WMETIS": "METIS",
    "WCORE": "CORE", "WASTR": "ASTR", "CBXRP": "XRP", "CBADA": "ADA", "CBDOGE": "DOGE", "CBLTC": "LTC",
    "CBZEC": "ZEC", "FXRP": "XRP", "UBTC": "BTC", "UETH": "ETH", "USOL": "SOL", "BTCB": "BTC", "XBTC": "BTC",
    "SOBTC": "BTC", "SOETH": "ETH", "WBTT": "BTT", "WXRP": "XRP",
}
# Монета, «родная» для сети: её займ в своей сети — в основном петли под стейкинг (LST), а не шорт.
NATIVE = {"Binance": "BNB", "Polygon": "POL", "Avalanche": "AVAX", "Fantom": "FTM", "Solana": "SOL", "Tron": "TRX",
          "Sui": "SUI", "Aptos": "APT", "Hyperliquid L1": "HYPE", "Cronos": "CRO", "Sei": "SEI", "Mantle": "MNT",
          "Near": "NEAR", "Algorand": "ALGO", "Cardano": "ADA", "Elrond": "EGLD", "Kava": "KAVA", "Flare": "FLR",
          "Osmosis": "OSMO", "Neutron": "NTRN", "Terra": "LUNA", "Moonbeam": "GLMR", "Moonriver": "MOVR",
          "Celo": "CELO", "Klaytn": "KLAY", "Metis": "METIS", "Harmony": "ONE", "Starknet": "STRK", "Monad": "MON",
          "Berachain": "BERA", "Injective": "INJ", "Stacks": "STX", "Sonic": "S", "Op_Bnb": "BNB", "Conflux": "CFX",
          "Waves": "WAVES", "Manta": "MANTA", "Blast": "BLAST", "Mode": "MODE", "Scroll": "SCR", "Ontology": "ONT",
          "Heco": "HT", "OKExChain": "OKT", "Umee": "UMEE", "Arbitrum": "ARB", "Optimism": "OP",
          "zkSync Era": "ZK", "Linea": "LINEA", "Kaia": "KAIA", "Story": "IP", "Plasma": "XPL"}
PERIODS = [("2020–2022", "2020-10-01", "2022-10-01"), ("2022–2024", "2022-10-01", "2024-10-01"),
           ("2024–2026", "2024-10-01", "2026-11-01")]


def perp_sets():
    def base(s):
        m = re.match(r"^(1000000|100000|10000|1000|1M)(.+)$", s)
        return m.group(2) if m else s
    tradfi = pickle.load(open(os.path.join(D, "s12", "perp_kind.pkl"), "rb"))["tradfi"]
    out = {}
    for nm, f in (("2020–2022", "s117/fund_2020.pkl"), ("2022–2024", "s117/fund_oos.pkl"),
                  ("2024–2026", "s2/fund2y.pkl")):
        keys = pickle.load(open(os.path.join(D, f), "rb")).keys()
        out[nm] = {("POL" if base(k) == "MATIC" else base(k)) for k in keys if k not in tradfi}
    return out


def norm(sym):
    s = str(sym).upper().strip()
    if ":" in s or s.startswith("0X") or len(s) > 12:
        return None
    s = re.sub(r"\.(E|B|BASE)$", "", s)
    s = WRAP.get(s, s)
    return s


def load_panel():
    if os.path.exists(CACHE):
        return pickle.load(open(CACHE, "rb"))
    rows = []  # (slug, chain, sym, day, tvl_u, bor_u, tvl_usd, bor_usd)
    first = {}
    for fn in sorted(os.listdir(PROTO)):
        slug = fn[:-8]
        if slug in SKIP:
            continue
        d = json.load(gzip.open(os.path.join(PROTO, fn)))
        ct = d.get("chainTvls") or {}
        chains = [k for k in ct if "-" not in k and k not in ("borrowed", "staking", "pool2", "vesting",
                                                              "treasury", "offers", "doublecounted")]
        for ch in chains:
            b = ct.get(ch + "-borrowed")
            if not b or not b.get("tokens"):
                continue
            acc = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])
            for key, idx in ((ch, 0), (ch + "-borrowed", 1)):
                for part, off in (("tokens", 0), ("tokensInUsd", 2)):
                    for r in (ct.get(key) or {}).get(part) or []:
                        day = int(r["date"]) // 86400
                        for sy, v in (r.get("tokens") or {}).items():
                            n = norm(sy)
                            if n is None or v is None:
                                continue
                            acc[(n, day)][idx + off] += float(v)
            for (n, day), (tu, bu, tusd, busd) in acc.items():
                rows.append((slug, ch, n, day, tu, bu, tusd, busd))
            dd = [int(r["date"]) // 86400 for r in b["tokens"] if r.get("tokens")]
            if dd:
                first[(slug, ch)] = min(dd)
        print(f"  {slug:26s} сетей с займом {sum(1 for c in chains if ct.get(c + '-borrowed'))}", flush=True)
    df = pd.DataFrame(rows, columns=["slug", "chain", "sym", "day", "tvl_u", "bor_u", "tvl_usd", "bor_usd"])
    df = df.groupby(["slug", "chain", "sym", "day"], as_index=False).sum()
    pickle.dump((df, first), open(CACHE, "wb"))
    return df, first


def month_of(day):
    return pd.to_datetime(np.asarray(day, np.int64) * 86400, unit="s").to_period("M")


def daily(g):
    """Сплошная сетка дней; пропуск ≤ 2 сут заполняется предыдущим значением, дольше — NaN."""
    g = g.set_index("day").sort_index()
    idx = np.arange(g.index.min(), g.index.max() + 1)
    return g.reindex(idx).ffill(limit=2)


def first_in(days, cool):
    out, last = [], -10 ** 9
    for d in days:
        if d - last >= cool:
            out.append(d)
            last = d
    return out


def main():
    perps = perp_sets()
    allperp = set().union(*perps.values())
    df, first = load_panel()
    df = df[~df.sym.isin(STABLE | MAJOR)]
    df["native"] = [NATIVE.get(c) == s for c, s in zip(df.chain, df.sym)]
    df = df[df.sym.isin(allperp)]
    print(f"\nстрок (протокол, сеть, монета, день) с монетой-перпом, без стейблов и BTC/ETH: {len(df):,}")

    # --- охват: с какого дня есть разбивка займа по монетам
    print("\nОхват разбивки займа по монетам (первый день) — главные протоколы:")
    big = df.groupby("slug").bor_usd.max().sort_values(ascending=False)
    for slug in big.index[:25]:
        ch = sorted((c, pd.to_datetime(first[(s, c)] * 86400, unit="s").date()) for (s, c) in first if s == slug)
        print(f"  {slug:24s} пик займа альтов {big[slug] / 1e6:8.1f} млн $ | " +
              ", ".join(f"{c} с {d}" for c, d in ch[:6]))

    # --- уровень займа по годам
    tok = df.groupby(["sym", "native", "day"], as_index=False)[["tvl_u", "bor_u", "tvl_usd", "bor_usd"]].sum()
    tok["year"] = pd.to_datetime(tok.day * 86400, unit="s").dt.year
    print("\nЗайм альтов с перпом Binance по годам (среднее по дням): число монет с займом ≥ 1 млн $ и сумма займа")
    print("  год | монет ≥1 млн (не родные) | займ не родных, млн $ | монет ≥1 млн (родные) | займ родных, млн $")
    for y in range(2020, 2027):
        a = tok[tok.year == y]
        if a.empty:
            continue
        nn = a[~a.native]
        nt = a[a.native]
        ndays = a.day.nunique()
        c1 = (nn[nn.bor_usd >= 1e6].groupby("day").size().reindex(a.day.unique(), fill_value=0)).mean()
        s1 = nn.groupby("day").bor_usd.sum().mean() / 1e6
        c2 = (nt[nt.bor_usd >= 1e6].groupby("day").size().reindex(a.day.unique(), fill_value=0)).mean()
        s2 = nt.groupby("day").bor_usd.sum().mean() / 1e6
        print(f"  {y} | {c1:6.1f} | {s1:9.1f} | {c2:5.1f} | {s2:9.1f}   (дней {ndays})")

    pk = tok[~tok.native].groupby("sym").bor_usd.max().sort_values(ascending=False)
    print("\nПик займа по монетам (не родные для сети), млн $ — 40 крупнейших:")
    print("  " + ", ".join(f"{s} {v / 1e6:.0f}" for s, v in pk.head(40).items()))
    print(f"  монет с пиком ≥ 1 млн $: {(pk >= 1e6).sum()}, ≥ 10 млн $: {(pk >= 1e7).sum()}")

    # --- события на уровне монеты (сумма по протоколам и сетям); родные и не родные — раздельно
    ev = defaultdict(list)  # тип -> [(sym, day, native)]
    for (sym, nat), g in tok.groupby(["sym", "native"]):
        g = daily(g[["day", "tvl_u", "bor_u", "bor_usd"]])
        b = g.bor_u.values
        s = g.tvl_u.values + b
        bu = g.bor_usd.values
        days = g.index.values
        with np.errstate(divide="ignore", invalid="ignore"):
            U = b / s
            r3 = b[3:] / b[:-3]
            s3 = s[3:] / s[:-3]
            dU = U[3:] - U[:-3]
        bu0, bu1, dd = bu[:-3], bu[3:], days[3:]
        ok = np.isfinite(r3) & np.isfinite(dU)
        dem = ok & (r3 >= 1.3) & (dU > 0) & (bu1 >= 1e6) & (bu0 >= 5e5)
        demp = dem & (np.abs(s3 - 1) <= 0.10)
        sup = ok & (r3 >= 1.3) & (dU <= 0) & (bu1 >= 1e6) & (bu0 >= 5e5)
        cov = ok & (r3 <= 0.7) & (bu0 >= 1e6)
        for nm, m in (("D", dem), ("Dp", demp), ("S", sup), ("C", cov)):
            for d in first_in(dd[m], 7):
                ev[nm].append((sym, d, nat))

    # --- U ≥ 90% на уровне пула общего типа
    pool = df[df.slug.isin(POOLED)]
    for (slug, ch, sym), g in pool.groupby(["slug", "chain", "sym"]):
        nat = NATIVE.get(ch) == sym
        g = daily(g[["day", "tvl_u", "bor_u", "bor_usd"]])
        b = g.bor_u.values
        s = g.tvl_u.values + b
        with np.errstate(divide="ignore", invalid="ignore"):
            U = np.where(s > 0, b / s, np.nan)
        hi = (U >= 0.9) & (g.bor_usd.values >= 1e6)
        days = g.index.values
        last = -10 ** 9
        for i in np.flatnonzero(hi):
            prev = U[max(0, i - 30):i]
            if i > 0 and np.all(prev[np.isfinite(prev)] < 0.9) and days[i] - last >= 30:
                ev["U90"].append((sym, days[i], nat))
                last = days[i]

    pickle.dump(dict(ev), open(os.path.join(D, "s177", "lend_ev.pkl"), "wb"))
    print("\nСобытия в месяц (монеты с перпом Binance в своём периоде; родные для сети — отдельно):")
    names = {"D": "D  сдвиг спроса (займ ×1,3 за 3 сут, U ↑)", "Dp": "Dp чистый спрос (и предложение ±10%)",
             "S": "S  сдвиг предложения (займ ×1,3, U не ↑)", "C": "C  закрытие (займ ×0,7 за 3 сут)",
             "U90": "U90 загрузка пула ≥ 90% (впервые за 30 сут)"}
    for nm, lab in names.items():
        e = pd.DataFrame(ev[nm], columns=["sym", "day", "native"])
        if e.empty:
            print(f"  {lab}: нет");
            continue
        e["date"] = pd.to_datetime(e.day * 86400, unit="s")
        line = []
        for pn, a, z in PERIODS:
            m = (e.date >= a) & (e.date < z) & e.sym.isin(perps[pn])
            months = (pd.Timestamp(z) - pd.Timestamp(a)).days / 30.44
            nn = e[m & ~e.native]
            line.append(f"{pn}: {len(nn) / months:5.2f} ({nn.sym.nunique()} монет)"
                        f" + родные {(m & e.native).sum() / months:4.2f}")
        print(f"  {lab}\n      " + " | ".join(line))
        yy = e[~e.native].groupby(e.date.dt.year).size()
        print("      по годам (не родные, все монеты-перпы): " + ", ".join(f"{y}: {v / 12:.2f}" for y, v in yy.items()))
        top = Counter(e[~e.native].sym).most_common(12)
        print("      чаще всего: " + ", ".join(f"{s} {c}" for s, c in top))


if __name__ == "__main__":
    main()
