"""s186 — списки токенов с плечом по биржам и периодам (только списки, даты жизни, оборот самих токенов).

Источники (без ключей, проверено запросами 19.11.2026):
- Gate: /spot/currency_pairs (только текущие пары; снятые API не отдаёт), /spot/tickers (поля etf_*: NAV, время последнего
  ребаланса, текущее плечо), /spot/candlesticks 1d (история дневного оборота токена с первого дня торгов, предел 10000 точек);
- FTX: токены BULL/BEAR/HALF/HEDGE из карты CMC (s167/cmc_map_all.json, статус untracked), адреса ERC-20 —
  CMC data-api cryptocurrency/detail, дневные цена и оборот — cryptocurrency/historical;
- Binance BLVT (UP/DOWN): жизненный цикл по архиву объявлений s124/ann.pkl, дневные цена и оборот — CMC historical;
- MEXC, KuCoin, HTX, Bitget, OKX: текущие списки (для отчёта «что живо сейчас»).
Итог: /home/user/mc_data/s186/lt_universe.pkl, gate_daily.pkl, cmc_lt_daily.pkl; лог — lt_lists.log.
Доходы не считаются."""
import json
import os
import pickle
import re
import time
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

import common186 as C

L = C.Log("lt_lists")
GATE = "https://api.gateio.ws/api/v4"
CMC = "https://api.coinmarketcap.com/data-api/v3"


# ---------- перпы Binance по периодам (из файлов фандинга) ----------
def perp_spans():
    kind = pd.read_pickle(f"{C.D}/s12/perp_kind.pkl")
    bad = set(kind.get("tradfi", set()))
    out = {}
    for p in (f"{C.D}/s117/fund_2020.pkl", f"{C.D}/s117/fund_oos.pkl", f"{C.D}/s2/fund2y.pkl"):
        F = pickle.load(open(p, "rb"))
        for k, a in F.items():
            if k in bad or not len(a):
                continue
            b = C.C3.base(k)
            if b in C.C3.NONCRYPTO:
                continue
            lo, hi = float(a[0, 0]), float(a[-1, 0])
            s = out.setdefault(b, [lo, hi])
            s[0], s[1] = min(s[0], lo), max(s[1], hi)
    return out


# ---------- Gate ----------
def gate():
    pairs = C.jget(f"{GATE}/spot/currency_pairs", cache="gate_pairs.json") or []
    tick = C.jget(f"{GATE}/spot/tickers", cache="gate_tickers.json") or []
    tk = {t["currency_pair"]: t for t in tick}
    rows = []
    for p in pairs:
        m = C.LT_RE.match(p["base"])
        if not m or p["quote"] != "USDT" or not re.search(r"Long|Short", p.get("base_name", ""), re.I):
            continue
        und, lev, side = m.group(1), int(m.group(2)), m.group(3)
        t = tk.get(p["id"], {})
        rows.append(dict(ex="gate", token=p["base"], und=und, lev=lev if side == "L" else -lev, pair=p["id"],
                         status=p["trade_status"], buy_start=p.get("buy_start"),
                         nav=float(t.get("etf_net_value") or "nan"), pre_ts=t.get("etf_pre_timestamp"),
                         cur_lev=float(t.get("etf_leverage") or "nan"), qv24=float(t.get("quote_volume") or 0)))
    G = pd.DataFrame(rows)
    # дневные свечи токенов: [t, оборот в USDT, close, high, low, open, оборот в токенах, закрыта]
    path = f"{C.OUT}/gate_daily.pkl"
    daily = pickle.load(open(path, "rb")) if os.path.exists(path) else {}
    for pair in G.pair:
        if pair in daily:
            continue
        rows_ = []
        t1 = int(time.time()) // C.DAY * C.DAY          # от сегодня назад кусками по 999 сут до 01.01.2020
        while t1 > 1577836800:
            t0 = max(t1 - 999 * C.DAY, 1577836800)
            d = C.jget(f"{GATE}/spot/candlesticks?currency_pair={pair}&interval=1d&from={t0}&to={t1}")
            time.sleep(0.12)
            if not isinstance(d, list) or not d:
                break
            rows_ += [(int(x[0]), float(x[1]), float(x[2])) for x in d]
            if int(d[0][0]) > t0 + C.DAY:                # история кончилась внутри куска
                break
            t1 = t0 - C.DAY
        if rows_:
            a = np.array(sorted(set(rows_)))
            daily[pair] = pd.DataFrame({"qv": a[:, 1], "c": a[:, 2]}, index=a[:, 0].astype(np.int64))
        if len(daily) % 50 == 0:
            pickle.dump(daily, open(path, "wb"))
    pickle.dump(daily, open(path, "wb"))
    first = {p: (int(df[df.qv > 0].index.min()) if (df.qv > 0).any() else None) for p, df in daily.items()}
    G["first"] = G.pair.map(first)
    return G, daily


# ---------- CMC: FTX и BLVT ----------
FTX_SUF = [("BULL", 3.0), ("BEAR", -3.0), ("HALF", 0.5), ("HEDGE", -1.0)]
FTX_IDX = {"ALT", "MID", "SHIT", "DRGN", "DEFI", "EXCH", "PRIV", "BVOL", "IBVOL", "UNISWAP", "CUSDT", "USDT", "TRYB",
           "XAUT", "PAXG", "BTMX", "LEO", "HT", "OKB", "DMG"}


def ftx_tokens():
    Lm = json.load(open(f"{C.D}/s167/cmc_map_all.json"))
    out = []
    for x in Lm:
        nm, sym = str(x.get("name", "")), str(x.get("symbol", ""))
        if not re.match(r"^(3X Long|3X Short|0\.5X Long|1X Short)", nm, re.I) or "Volatility" in nm:
            continue
        if sym in ("BULLSHIT", "HALFSHIT"):
            und, lev = "SHIT", (3.0 if sym == "BULLSHIT" else 0.5)
        else:
            und, lev = None, None
            for suf, lv in FTX_SUF:
                if sym.endswith(suf):
                    und, lev = (sym[: -len(suf)] or "BTC"), lv
                    break
        if und is None:
            continue
        out.append(dict(ex="ftx", token=sym, und=und, lev=lev, cmc_id=x["id"], name=nm))
    return pd.DataFrame(out)


def blvt_tokens():
    A = pickle.load(open(f"{C.D}/s124/ann.pkl", "rb"))
    rows = sorted(A.values(), key=lambda r: r["ts"])
    lst, cease = {}, {}
    for r in rows:
        t, tt = r["ts"] / 1000, r["title"]
        if re.search(r"Leveraged Token|BLVT|UP (and|&) [A-Z0-9]+DOWN", tt):
            for c in re.findall(r"\b([A-Z0-9]{2,10})UP\b", tt):
                if re.search(r"List|Launch", tt):
                    lst.setdefault(c, t)
                if re.search(r"Cease|Delist", tt):
                    cease.setdefault(c, t)
    # 1INCH и FIL в архиве без отдельной строки листинга — дата по CMC
    Lm = json.load(open(f"{C.D}/s167/cmc_map_all.json"))
    ids = {x["symbol"]: x["id"] for x in Lm if re.search(r"(UP|DOWN)$", str(x.get("symbol", ""))) and x["name"] == x["symbol"]}
    out = []
    for c in sorted(set(lst) | set(cease) | {s[:-2] for s in ids if s.endswith("UP")}):
        for suf, lv in (("UP", 2.5), ("DOWN", -2.5)):       # переменное плечо 1,25–4 (по объявлению 12.2020)
            sym = c + suf
            if sym not in ids or c in ("P", "S", "ZK"):
                continue
            out.append(dict(ex="binance", token=sym, und=c, lev=lv, cmc_id=ids[sym], t_list=lst.get(c),
                            t_cease=cease.get(c)))
    return pd.DataFrame(out)


def cmc_daily(cid):
    p = f"{C.RAW}/cmc_{cid}.json"
    if os.path.exists(p):
        return json.load(open(p))
    out = []
    for y in range(2019, 2025):
        t0, t1 = C.ts(f"{y}-01-01"), C.ts(f"{y + 1}-01-01")
        code, raw = C.get(f"{CMC}/cryptocurrency/historical?id={cid}&convertId=2781&timeStart={t0}&timeEnd={t1}"
                          f"&interval=1d", headers={"Accept": "application/json"})
        time.sleep(0.5)
        if code == 200 and raw:
            for q in ((json.loads(raw).get("data") or {}).get("quotes") or []):
                u = q["quote"]
                out.append([q["timeOpen"][:10], u.get("close"), u.get("volume")])
    json.dump(out, open(p, "w"))
    return out


def cmc_contract(cid):
    p = f"{C.RAW}/cmcdet_{cid}.json"
    if os.path.exists(p):
        return json.load(open(p)).get("addr")
    code, raw = C.get(f"{CMC}/cryptocurrency/detail?id={cid}", headers={"Accept": "application/json"})
    time.sleep(0.5)
    addr = None
    if code == 200 and raw:
        for pl in ((json.loads(raw).get("data") or {}).get("platforms") or []):
            if pl.get("contractPlatform") == "Ethereum":
                addr = pl.get("contractAddress")
    json.dump({"addr": addr}, open(p, "w"))
    return addr


def other_lists():
    res = {}
    me = C.jget("https://api.mexc.com/api/v3/exchangeInfo", cache="mexc_exchangeInfo.json") or {}
    res["mexc"] = sum(1 for s in me.get("symbols", []) if re.search(r"\d(L|S)USDT$", s["symbol"]))
    ku = C.jget("https://api.kucoin.com/api/v2/symbols", cache="kucoin_symbols.json") or {}
    res["kucoin"] = sum(1 for s in ku.get("data", []) if re.search(r"\d(L|S)-USDT$|(UP|DOWN)-USDT$", s["symbol"]))
    ht = C.jget("https://api.huobi.pro/v2/settings/common/symbols", cache="htx_symbols.json") or {}
    etp = [x for x in ht.get("data", []) if "etp" in str(x.get("tags", ""))]
    res["htx_etp_all"] = len(etp)
    res["htx_etp_online"] = sum(1 for x in etp if x.get("state") == "online")
    res["htx_etp_list"] = sorted(x["bc"] for x in etp)
    bg = C.jget("https://api.bitget.com/api/v2/spot/public/symbols", cache="bitget_symbols.json") or {}
    res["bitget"] = sum(1 for s in bg.get("data", []) if re.search(r"\d(L|S)USDT$", s["symbol"]))
    ok = C.jget("https://www.okx.com/api/v5/public/instruments?instType=SPOT", cache="okx_spot.json") or {}
    res["okx"] = sum(1 for s in ok.get("data", []) if re.search(r"\d(L|S)-USDT$", s["instId"]))
    return res


def main():
    spans = perp_spans()
    L("перпов Binance (крипто, все периоды):", len(spans))
    # --- Gate
    G, gdaily = gate()
    L("\n== Gate: пар ETF-токенов к USDT сейчас:", len(G), "базовых:", G.und.nunique())
    L("плечо:", dict(Counter(G.lev)))
    hr = Counter(int(x) % C.DAY // 3600 for x in G.pre_ts.dropna())
    L("час UTC последнего ребаланса (etf_pre_timestamp) по токенам:", dict(sorted(hr.items())))
    fy = Counter(pd.Timestamp(int(x), unit="s").year for x in G["first"].dropna())
    L("год первой дневной свечи с оборотом:", dict(sorted(fy.items())))
    G["perp"] = G.und.map(lambda u: u in spans)
    L("базовых с перпом Binance (когда-либо):", G[G.perp].und.nunique(), "из", G.und.nunique())
    L("24ч оборот токенов сейчас, $ млн: всего %.1f, медиана на базовый %.3f" % (
        G.qv24.sum() / 1e6, G.groupby("und").qv24.sum().median() / 1e6))
    top = G.groupby("und").qv24.sum().sort_values(ascending=False).head(15)
    L("топ-15 базовых по 24ч обороту токенов, $ млн:", ", ".join(f"{k} {v / 1e6:.2f}" for k, v in top.items()))
    # --- FTX
    F = ftx_tokens()
    F["addr"] = [cmc_contract(c) for c in F.cmc_id]
    fd = {}
    for _, r in F.iterrows():
        q = cmc_daily(r.cmc_id)
        if q:
            df = pd.DataFrame(q, columns=["d", "c", "v"])
            df["t"] = [C.ts(x) for x in df.d]
            fd[r.token] = df.set_index("t")[["c", "v"]].astype(float)
    F["first"] = F.token.map(lambda s: int(fd[s].index.min()) if s in fd and len(fd[s]) else None)
    F["last"] = F.token.map(lambda s: int(fd[s][fd[s].v > 0].index.max()) if s in fd and (fd[s].v > 0).any() else None)
    L("\n== FTX: токенов в карте CMC:", len(F), "с адресом ERC-20:", F.addr.notna().sum(), "базовых:", F.und.nunique())
    L("по плечу:", dict(Counter(F.lev)))
    Fp = F[F.und.map(lambda u: u in spans) & ~F.und.isin(FTX_IDX)]
    L("базовых с перпом Binance:", Fp.und.nunique(), sorted(Fp.und.unique()))
    L("первая / последняя дата котировок CMC (медиана):", C.iso(F["first"].dropna().median()),
      C.iso(F["last"].dropna().median()))
    # --- Binance BLVT
    B = blvt_tokens()
    bd = {}
    for _, r in B.iterrows():
        q = cmc_daily(r.cmc_id)
        if q:
            df = pd.DataFrame(q, columns=["d", "c", "v"])
            df["t"] = [C.ts(x) for x in df.d]
            bd[r.token] = df.set_index("t")[["c", "v"]].astype(float)
    B["first"] = B.token.map(lambda s: int(bd[s][bd[s].v > 0].index.min()) if s in bd and (bd[s].v > 0).any() else None)
    B["last"] = B.token.map(lambda s: int(bd[s][bd[s].v > 0].index.max()) if s in bd and (bd[s].v > 0).any() else None)
    L("\n== Binance BLVT: токенов:", len(B), "базовых:", B.und.nunique())
    for u, g in B.groupby("und"):
        L(f"  {u}: объявление листинга {C.iso(g.t_list.iloc[0]) if pd.notna(g.t_list.iloc[0]) else '—'}, "
          f"прекращение {C.iso(g.t_cease.iloc[0]) if pd.notna(g.t_cease.iloc[0]) else '—'}, "
          f"котировки CMC {C.iso(g['first'].min()) if pd.notna(g['first'].min()) else '—'} … "
          f"{C.iso(g['last'].max()) if pd.notna(g['last'].max()) else '—'}")
    # --- прочие биржи
    O = other_lists()
    L("\n== сейчас (19.11.2026) токенов с плечом к USDT: MEXC %d, KuCoin %d, Bitget %d, OKX %d; HTX ETP %d (живых %d)" % (
        O["mexc"], O["kucoin"], O["bitget"], O["okx"], O["htx_etp_all"], O["htx_etp_online"]))
    L("HTX ETP:", " ".join(O["htx_etp_list"]))
    # --- вселенная по периодам: базовый актив × биржа × [начало, конец]
    U = []
    for _, r in G.iterrows():
        if pd.notna(r["first"]):
            U.append(dict(ex="gate", und=r.und, token=r.token, lev=r.lev, t0=int(r["first"]), t1=int(time.time())))
    for _, r in F.iterrows():
        if pd.notna(r["first"]) and r.und not in FTX_IDX:
            U.append(dict(ex="ftx", und=r.und, token=r.token, lev=r.lev, t0=int(r["first"]),
                          t1=min(int(r["last"]) if pd.notna(r["last"]) else C.ts("2022-11-11"), C.ts("2022-11-11"))))
    for _, r in B.iterrows():
        if pd.notna(r["first"]):
            U.append(dict(ex="binance", und=r.und, token=r.token, lev=r.lev, t0=int(r["first"]), t1=int(r["last"])))
    U = pd.DataFrame(U)
    U["perp"] = U.und.map(lambda u: u in spans)
    pickle.dump(dict(U=U, G=G, F=F, B=B, other=O), open(f"{C.OUT}/lt_universe.pkl", "wb"))
    pickle.dump(dict(ftx=fd, blvt=bd), open(f"{C.OUT}/cmc_lt_daily.pkl", "wb"))
    L("\n== базовых активов с токенами (и перпом Binance) на середину каждого периода и в среднем за период:")
    for per in C.PERS:
        t0, t1 = C.ts(C.PER[per]["t0"]), C.ts(C.PER[per]["t1"])
        mid = (t0 + t1) / 2
        line = []
        for ex in ("ftx", "binance", "gate"):
            u = U[(U.ex == ex) & U.perp]
            at_mid = u[(u.t0 <= mid) & (u.t1 >= mid)].und.nunique()
            days = [len(set(u[(u.t0 <= t) & (u.t1 >= t)].und)) for t in range(t0, t1, 7 * C.DAY)]
            line.append(f"{ex}: {at_mid} (среднее {np.mean(days):.1f}, макс {max(days)})")
        L(f"  {per}: " + "; ".join(line))
    L("\nсписки Gate неполны: снятые пары API не отдаёт (выживаемость); MEXC/KuCoin/Bybit истории без ключа нет.")


if __name__ == "__main__":
    main()
