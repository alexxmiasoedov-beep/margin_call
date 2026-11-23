"""s249 — 🐋 в BNB Chain (гипотеза — ВЫВОДЫ.md, записана до расчёта, коммит 9c1c348). События — переводы на адреса сметания
Binance в BNB Chain (s249/raw, collect.py), монеты в обращении — s249/bsc_circ.json. Сделка — как у 🐋 и s221 (функции
s221/run.py). Запуск из /home/user/mc_data: python3 <repo>/research/s249/run.py"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s221", "s187", "s182", "s213"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("s221run", os.path.join(HERE, "..", "s221", "run.py"))
S221 = importlib.util.module_from_spec(spec); spec.loader.exec_module(S221)
DAY = 86400
GAP, BIG, CALM = 48 * 3600, 0.005, 0.05
T0 = pd.Timestamp("2024-10-01", tz="UTC").timestamp()
T1 = pd.Timestamp("2026-10-19", tz="UTC").timestamp()
ZERO = "0x" + "0" * 40


def labels():
    lab = set()
    for line in open(os.path.join(HERE, "..", "..", "bot", "cex_labels.tsv")):
        if line.strip() and not line.startswith("#"):
            lab.add(line.split("\t")[0].lower())
    return lab


def own_token():
    """Монеты, у которых адрес BEP-20 — сам токен проекта, а не обёртка Binance (решение 23.11 до расчёта доходов):
    адрес BNB Chain есть у монеты CoinGecko с тем же тикером (id не binance-peg-…) или в платформе монеты CMC.
    Binance-Peg (id binance-peg-…) и неподтверждённые адреса (родные монеты других сетей) — отдельной строкой."""
    import re
    C = json.load(open("s249/bsc_circ.json"))
    cmc = {c["id"]: c for c in json.load(open("s167/cmc_map_all.json"))}
    by = {}
    for c in json.load(open("s220/cg_list.json")):
        a = str((c.get("platforms") or {}).get("binance-smart-chain") or "").lower()
        if a:
            by.setdefault(a, []).append((c["id"], str(c["symbol"]).upper()))
    out = {}
    for fs, r in C.items():
        m = re.match(r"^(1000000|100000|10000|1000|1M)(.+)$", fs)
        coin = m.group(2) if m and not m.group(2)[0].isdigit() else fs
        ids = by.get(r["contract"], [])
        peg = any(i.startswith("binance-peg") for i, _ in ids)
        pl = (cmc.get(r["cmc"]) or {}).get("platform")
        own = any(not i.startswith("binance-peg") and s == coin for i, s in ids) or (
            isinstance(pl, dict) and str(pl.get("token_address") or "").lower() == r["contract"])
        out[fs] = "own" if own and not peg else ("peg" if peg else "unk")
    return out


def raw():
    rows = []
    for p in sorted(glob.glob("s249/raw/part_*.jsonl")):
        for line in open(p):
            rows.append(json.loads(line))
    return pd.DataFrame(rows, columns=["block", "t", "tok", "frm", "to", "amt", "tx"]).drop_duplicates(["tx", "tok", "frm", "to", "amt"])


def events(R):
    C = json.load(open("s249/bsc_circ.json"))
    by = {r["contract"]: fs for fs, r in C.items()}
    skip = labels() | set(json.load(open("s249/collectors.json"))) | {ZERO}
    R = R[~R.frm.isin(skip) & R.tok.isin(by)].copy()
    R["perp"] = R.tok.map(by)
    out = []
    for fs, g in R.groupby("perp"):
        days = {d: c for d, c, _ in C[fs]["days"]}; dd = sorted(days)
        d = pd.to_datetime(g.t - DAY, unit="s").dt.strftime("%Y-%m-%d").values
        i = np.searchsorted(dd, d, "right") - 1
        circ = np.array([days[dd[j]] if j >= 0 else np.nan for j in i])
        g = g.assign(frac=g.amt.values / circ, eth=C[fs]["eth"], since=C[fs]["since"])
        out.append(g)
    X = pd.concat(out)
    X = X[(X.frac >= BIG) & (X.t >= T0) & (X.t < T1) & (X.t >= X.since)].sort_values(["perp", "t"])
    keep = []
    for perp, g in X.groupby("perp"):
        last = -10 ** 12
        for r in g.itertuples():
            if r.t - last >= GAP:
                keep.append(r); last = r.t
    return pd.DataFrame(keep)


def main():
    R = raw()
    print("переводов на адреса сметания:", len(R), "токенов", R.tok.nunique())
    E = events(R)
    print("событий ≥ 0,5% обращения (первые за 48 ч):", len(E), "монет", E.perp.nunique(),
          "; без сети ETH:", int((~E.eth).sum()))
    T = S221.trades(E[["perp", "t", "amt", "frac", "eth"]].copy())
    T["cls"] = T.perp.map(own_token())
    T.to_pickle("s249_trades.pkl")
    months = (T1 - T0) / (30.44 * DAY)
    x0 = T[T.net.notna() & (T.r24.abs() <= CALM)]
    print(f"\nкак записано 23.11 (все монеты без сети ETH, с Binance-Peg): {S221.line(x0[~x0.eth], months)}")
    print(f"  Binance-Peg: {S221.line(x0[~x0.eth & (x0.cls == 'peg')], months)}")
    print(f"  адрес не подтверждён: {S221.line(x0[~x0.eth & (x0.cls == 'unk')], months)}")
    x = x0[x0.cls == "own"]                                   # основная — BEP-20 самого токена (решение до расчёта)
    C = json.load(open("s249/bsc_circ.json")); cmc = {c["id"]: c for c in json.load(open("s167/cmc_map_all.json"))}
    nat = x.perp.map(lambda fs: not isinstance((cmc.get(C[fs]["cmc"]) or {}).get("platform"), dict))
    print(f"  для прозрачности — основная без родных монет других сетей (IOST, ZIL, BB, 0G…): "
          f"{S221.line(x[~x.eth & ~nat], months)}")
    print(f"\n🐋 BNB Chain, монеты без сети ETH, BEP-20 — свой токен (основная, спокойный рынок ±5%): {S221.line(x[~x.eth], months)}")
    print(f"монеты с сетью ETH: {S221.line(x[x.eth], months)}")
    print(f"все монеты: {S221.line(x, months)}")
    print(f"без фильтра рынка (без сети ETH): {S221.line(T[T.net.notna() & ~T.eth & (T.cls == 'own')], months)}")
    print(f"🐋ᵛ (λ ≥ 0,05), без сети ETH: {S221.line(x[~x.eth & (x.lam >= 0.05)], months)}")
    m, t, n = S221.ct(x[~x.eth].net, x[~x.eth].entry); mh, _, _ = S221.ct(x[~x.eth].hed, x[~x.eth].entry)
    md = (x[~x.eth].net - x[~x.eth].pl).mean()
    print("\nпорог s249: " + "; ".join(f"{k} — {'да' if ok else 'нет'}" for k, ok in
                                      (("среднее > 0 и t ≥ 2", m > 0 and t >= 2), ("с хеджем > 0", mh > 0), ("сверх плацебо > 0", md > 0))))
    cols = ["perp", "entry", "net", "hed", "pl", "stop", "lam"]
    W = pd.read_pickle("s213_main_2024–2026.pkl")
    W = W[W.net.notna() & (W.r24.abs() <= CALM)][cols]
    S = pd.read_pickle("s221_trades.pkl")
    S = S[S.net.notna() & (S.r24.abs() <= CALM)][cols]
    for name, B in (("BNB Chain — монеты без сети ETH", x[~x.eth]), ("BNB Chain — все монеты", x)):
        A = dedup(pd.concat([W.assign(src="eth"), S.assign(src="sol"), B[cols].assign(src="bsc")], ignore_index=True))
        print(f"🐋 Ethereum + Solana + {name} (одна сделка на монету за 48 ч): {S221.line(A, months)}")


def dedup(A):
    """Одна сделка на монету за 48 ч по всем сетям вместе (первая по времени входа)."""
    keep = []
    for perp, g in A.sort_values(["perp", "entry"]).groupby("perp"):
        last = -10 ** 12
        for i, e in zip(g.index, g.entry.values):
            if e - last >= GAP:
                keep.append(i); last = e
    return A.loc[keep]


if __name__ == "__main__":
    main()
