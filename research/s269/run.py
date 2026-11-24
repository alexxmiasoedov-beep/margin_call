"""s269 — события и сделки 🐋 на новых сетях (запись — ВЫВОДЫ.md, коммит 39edc9b) и сводка «🐋 вне Ethereum».
Строки — /home/user/mc_data/s269/raw_<сеть>.jsonl (collect.py). Монеты в обращении — история CMC (s171 k3.hist, s249 cmcfull),
монета CMC — из переписи s267 (по адресу или тикеру) с проверкой цены к фьючерсу 0,8–1,25. Сделки — s221/run.py.
Запуск из /home/user/mc_data: python3 -I <repo>/research/s269/run.py [senders|main]"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s221", "s187", "s182", "s213", "s171", "s249", os.path.join("s267", "study")):
    sys.path.insert(0, os.path.join(HERE, "..", p))
import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("s221run", os.path.join(HERE, "..", "s221", "run.py"))
S221 = importlib.util.module_from_spec(spec); spec.loader.exec_module(S221)
spec = importlib.util.spec_from_file_location("s249run", os.path.join(HERE, "..", "s249", "run.py"))
S249 = importlib.util.module_from_spec(spec); spec.loader.exec_module(S249)

OUT = "/home/user/mc_data/s269"
DAY = 86400
GAP, BIG, CALM = 48 * 3600, 0.005, 0.05
T0 = pd.Timestamp("2024-10-01", tz="UTC").timestamp()
T1 = pd.Timestamp("2026-10-19", tz="UTC").timestamp()
ZERO = "0x" + "0" * 40
SUSPECT = 300                                    # отправитель с ≥ 300 переводами на Binance — проверить по меткам
INTERNAL = json.load(open(os.path.join(HERE, "internal.json"))) if os.path.exists(os.path.join(HERE, "internal.json")) else {}


def raw():
    rows = []
    for p in sorted(glob.glob(f"{OUT}/raw_*.jsonl")):
        for line in open(p):
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    R = pd.DataFrame(rows)
    R["from"] = R["from"].astype(str).str.lower().where(~R.net.isin(["TON"]), R["from"])
    return R.drop_duplicates(["net", "tx", "perp", "from", "to", "amt"])


def binance_sets():
    import evm_probe as EP  # noqa: E402
    b, cex = EP.evm_sets()
    out = {"EVM": cex | b}
    if os.path.exists(f"{OUT}/binance_TON.json"):
        out["TON"] = set(json.load(open(f"{OUT}/binance_TON.json"))["binance"])
    out["SUI"] = {r["address"] for r in json.load(open("s250/por.json"))["data"] if r["network"] == "SUI"}
    return out


def circ_table(perps):
    """Монеты в обращении по дням: монета CMC из переписи s267; для сопоставленных по тикеру — проверка цены к фьючерсу."""
    import k3  # noqa: E402
    from cmcfull import full  # noqa: E402
    import fastbt as FB  # noqa: E402
    path = f"{OUT}/circ.json"
    C = json.load(open(path)) if os.path.exists(path) else {}
    nets = json.load(open("/dev/shm/s267/nets.json"))
    for fs in perps:
        if fs in C or fs not in nets:
            continue
        r = nets[fs]
        h = k3.hist(r["cmc"])
        days = [[d, ci, cl] for d, ci, cl, _ in full(r["cmc"], h) if ci and cl]
        ratio = np.nan
        if fs in FB.K and days:
            a = FB.K[fs]; m = (a["qv"] > 0) & (a["t"] % DAY == DAY - 900)
            px = pd.Series(a["c"][m].astype(float) / r.get("mult", 1),
                           index=pd.to_datetime(a["t"][m].astype(np.int64) // DAY * DAY, unit="s").strftime("%Y-%m-%d"))
            q = pd.Series({d: cl for d, _, cl in days}, dtype=float)
            j = q.index.intersection(px.index)
            if len(j) >= 30:
                ratio = float(np.median(q[j].values / px[j].values))
        C[fs] = {"cmc": r["cmc"], "how": r.get("cmc_how"), "ratio": ratio, "days": days}
        print(fs, "CMC", r["cmc"], r.get("cmc_how"), "цена к фьючерсу", round(ratio, 3) if ratio == ratio else None, flush=True)
    json.dump(C, open(path, "w"))
    return C


def frac(R, C):
    out = np.full(len(R), np.nan)
    for fs, idx in R.groupby("perp").groups.items():
        c = C.get(fs)
        if not c or not c["days"] or not (c["ratio"] == c["ratio"] and 0.8 <= c["ratio"] <= 1.25):
            continue
        days = {d: ci for d, ci, _ in c["days"]}; dd = sorted(days)
        g = R.loc[idx]
        d = pd.to_datetime(g.t - DAY, unit="s").dt.strftime("%Y-%m-%d").values
        i = np.searchsorted(dd, d, "right") - 1
        out[R.index.get_indexer(idx)] = g.amt.values / np.array([days[dd[j]] if j >= 0 else np.nan for j in i])
    return out


def external(R, B):
    """Отправитель — не Binance, не биржа, не нулевой адрес; в Sui — не внутренний перевод; не из списка internal.json."""
    ok = np.ones(len(R), bool)
    evm = ~R.net.isin(["TON", "SUI"])
    ok &= ~(evm & (R["from"].isin(B["EVM"]) | (R["from"] == ZERO)))
    if "TON" in B:
        ok &= ~((R.net == "TON") & R["from"].isin(B["TON"]))
    ok &= ~((R.net == "SUI") & (R.get("internal", False).fillna(False).astype(bool) | R["from"].isin(B["SUI"]) | R["from"].isna()))
    bad = {(n, a.lower() if n not in ("TON",) else a) for n, lst in INTERNAL.items() for a in lst}
    ok &= ~np.array([(n, f) in bad for n, f in zip(R.net, R["from"])])
    return ok


def first48(X):
    keep = []
    for _, g in X.sort_values("t").groupby(["net", "perp"]):
        last = -10 ** 12
        for i, t in zip(g.index, g.t.values):
            if t - last >= GAP:
                keep.append(i); last = t
    return X.loc[keep]


def senders(R, B, C):
    """До расчёта доходов: отправители событий с ≥ SUSPECT переводов на Binance за период — проверить по меткам."""
    R = R.assign(frac=frac(R, C))
    R = R[external(R, B)]
    cnt = R.groupby(["net", "from"]).size()
    E = R[(R.frac >= BIG) & (R.t >= T0) & (R.t < T1)]
    s = E.groupby(["net", "from"]).size().rename("events").to_frame().join(cnt.rename("all_transfers"))
    print(s.sort_values("all_transfers", ascending=False).head(30).to_string())
    print("\nподозрительные (≥", SUSPECT, "переводов):")
    print(s[s.all_transfers >= SUSPECT].to_string())


def main():
    R = raw()
    print("строк:", len(R), R.groupby("net").size().to_dict())
    B = binance_sets()
    C = circ_table(sorted(R.perp.unique()))
    if len(sys.argv) > 1 and sys.argv[1] == "senders":
        senders(R, B, C)
        return
    R["frac"] = frac(R, C)
    R = R[external(R, B)].copy()
    X = R[(R.frac >= BIG) & (R.t >= T0) & (R.t < T1)].copy()
    E = first48(X)
    # новый вкладчик: у того же адреса не было переводов этой монеты ≥ 0,1% обращения за 7 сут до события
    prev = R[R.frac >= 0.001][["net", "perp", "from", "t"]]
    nd = []
    for r in E.itertuples():
        f = E.loc[r.Index, "from"]
        g = prev[(prev.net == r.net) & (prev.perp == r.perp) & (prev["from"] == f) & (prev.t < r.t) & (prev.t >= r.t - 7 * DAY)]
        nd.append(len(g) == 0)
    E["newdep"] = nd
    print("событий ≥ 0,5% обращения (первые у монеты в сети за 48 ч):", len(E), E.groupby("net").size().to_dict())
    T = S221.trades(E[["perp", "t", "amt", "frac", "net", "newdep"]].copy())
    T.to_pickle("s269_trades.pkl")
    months = (T1 - T0) / (30.44 * DAY)
    x = T[T.net.notna() & (T.r24.abs() <= CALM)]
    print(f"\n=== ГЛАВНАЯ: новые сети вместе (спокойный рынок ±5%): {S221.line(x, months)}")
    for n, g in x.groupby("net"):
        print(f"  {n}: {S221.line(g, months)}")
    print(f"  новый вкладчик: {S221.line(x[x.newdep], months)}")
    print(f"  повторный вкладчик: {S221.line(x[~x.newdep], months)}")
    print(f"  без фильтра рынка: {S221.line(T[T.net.notna()], months)}")
    m, t, n = S221.ct(x.net, x.entry); mh, _, _ = S221.ct(x.hed, x.entry); md = (x.net - x.pl).mean()
    print("порог главной: " + "; ".join(f"{k} — {'да' if ok else 'нет'}" for k, ok in
                                        (("среднее > 0", m > 0), ("с хеджем > 0", mh > 0), ("сверх плацебо > 0", md > 0),
                                         ("t ≥ 2 (значимо)", t >= 2))))
    # порог 0,25% — для отчёта
    X2 = first48(R[(R.frac >= 0.0025) & (R.t >= T0) & (R.t < T1)].copy())
    T2 = S221.trades(X2[["perp", "t", "amt", "frac", "net"]].copy())
    print(f"порог 0,25% (для отчёта): {S221.line(T2[T2.net.notna() & (T2.r24.abs() <= CALM)], months)}")
    # Г3: вне Ethereum — Solana + Base + Arbitrum + BNB Chain (основная) + новые сети, одна сделка на монету за 48 ч
    cols = ["perp", "entry", "net", "hed", "pl", "stop", "lam"]

    def calm(df):
        return df[df.net.notna() & (df.r24.abs() <= CALM)]
    sol = calm(pd.read_pickle("s221_trades.pkl"))[cols].assign(src="sol")
    base = calm(pd.read_pickle("s243_trades.pkl"))[cols].assign(src="base")
    arb = calm(pd.read_pickle("s244_trades.pkl"))[cols].assign(src="arb")
    b = pd.read_pickle("s249_trades.pkl"); bsc = calm(b[(b.cls == "own") & ~b.eth.astype(bool)])[cols].assign(src="bsc")
    new = x[cols].assign(src="new")
    G3 = S249.dedup(pd.concat([sol, base, arb, bsc, new], ignore_index=True))
    mid = float(np.median(G3.entry))
    m, t, n = S221.ct(G3.net, G3.entry); mh, _, _ = S221.ct(G3.hed, G3.entry); md = (G3.net - G3.pl).mean()
    h1, h2 = G3[G3.entry < mid].net.mean(), G3[G3.entry >= mid].net.mean()
    print(f"\n=== Г3 «🐋 вне Ethereum»: {S221.line(G3, months)}; половины по медиане {h1:+.2%} / {h2:+.2%}")
    print("  по источникам:", {k: (len(g), round(g.net.mean() * 100, 2)) for k, g in G3.groupby("src")})
    print("порог Г3: " + "; ".join(f"{k} — {'да' if ok else 'нет'}" for k, ok in
                                   (("t ≥ 2", t >= 2), ("обе половины > 0", h1 > 0 and h2 > 0), ("с хеджем > 0", mh > 0),
                                    ("сверх плацебо > 0", md > 0))))
    W = pd.read_pickle("s213_main_2024–2026.pkl")
    W = W[W.net.notna() & (W.r24.abs() <= CALM)][cols].assign(src="eth")
    A = S249.dedup(pd.concat([W, sol, base, arb, bsc, new], ignore_index=True))
    print(f"для отчёта — все сети вместе с Ethereum: {S221.line(A, months)}")


if __name__ == "__main__":
    main()
