"""s288 — сверка канала Whale Alert с событиями 🐋 (заводы ERC-20 на адреса Binance ≥ 0,5% обращения, первый у монеты
за 48 ч; s160/s202) и наоборот: алерты ERC-20 → Binance, которых нет в нашем сборе. Только счёт и задержки.

События 🐋 — s202_main_<период>.pkl (вид «single»; берутся только perp, tb, sum, r24 — ход за 24 ч ДО входа, это фильтр
правила), хеш и сумма — из s195_deposits.pkl. Цена токена — ряды CMC s160/circ.
Запуск из /home/user/mc_data: python3 -I <repo>/research/s288/study/whale_match.py → s288/whale_match.csv, отчёт."""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common288 as C  # noqa: E402

LINES = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LINES.append(s)


def whale_events():
    E = []
    for p in ("2020–2022", "2022–2024", "2024–2026"):
        R = pd.read_pickle(f"s202_main_{p}.pkl")
        R = R[R.kind == "single"][["perp", "tb", "sum", "r24"]].copy()
        R["per"] = p
        E.append(R)
    E = pd.concat(E, ignore_index=True).drop_duplicates(["perp", "tb"])
    X = pd.read_pickle("s195_deposits.pkl")
    X = X[(X.exch == "Binance") & X.perp.notna()].copy()
    X["tb"] = X.t.astype(np.int64)
    X = X.sort_values(["tb", "block", "li"]).drop_duplicates(["perp", "tb", "frac"])
    M = E.merge(X[["perp", "tb", "frac", "tx", "tok", "amt", "frm", "to", "block"]], left_on=["perp", "tb", "sum"],
                right_on=["perp", "tb", "frac"], how="left")
    say(f"События 🐋 (single): {len(E)}, с хешем: {M.tx.notna().sum()}")
    # цена токена на сутки — CMC s160/circ
    ids = json.load(open("s160/cmc_ids.json"))
    px = {}
    for tok, v in ids.items():
        f = f"s160/circ/{v['id']}.json"
        if os.path.exists(f):
            px[tok.lower()] = {r[0]: float(r[2] or 0) for r in json.load(open(f))}
    d = pd.to_datetime(M.tb, unit="s").dt.strftime("%Y-%m-%d")
    M["px"] = [px.get(str(t).lower(), {}).get(dd, np.nan) for t, dd in zip(M.tok, d)]
    M["usd"] = M.amt * M.px
    return M


def main():
    M = whale_events()
    A = pd.read_pickle(f"{C.OUT}/wa_archive.pkl.gz")
    A["hl"] = A.hash.map(C.norm_hash)
    T = pd.read_pickle(f"{C.OUT}/posts.pkl.gz")
    T["hl"] = T.hash.map(C.norm_hash)
    M["hl"] = M.tx.map(C.norm_hash)
    a1 = A.drop_duplicates("hl").set_index("hl")
    t1 = T[T.hl != ""].sort_values("id").drop_duplicates("hl").set_index("hl")
    # 1) прямое совпадение хеша (алерт и есть перевод на горячий кошелёк Binance)
    M["m_hash"] = M.hl.isin(a1.index)
    # 2) по адресу: Whale Alert помечает адреса пополнения клиентов как «binance» (address_type deposit_wallet); событие 🐋 —
    #    сметание с адреса пополнения. Алерт «→ binance» на адрес, с которого потом ушло сметание того же токена,
    #    за 0–72 ч до сметания, сумма 0,5–1,02 от сметания (сметание бывает пакетом нескольких пополнений).
    e = A[(A.chain == "ethereum") & (A.type == "transfer")].copy()
    e["ta_l"] = e.ta.fillna("").str.lower()
    by = {k: g for k, g in e.groupby("ta_l")}
    hit_t, hit_h, hit_usd, hit_frm = [], [], [], []
    for frm, sym_tb, amt in zip(M.frm.fillna("").str.lower(), zip(M.perp, M.tb), M.amt):
        g = by.get(frm)
        best = None
        if g is not None:
            perp, tb = sym_tb
            base = C.base_of(perp)
            g = g[(g.sym == base) & (g.tb <= tb + 120) & (g.tb >= tb - 72 * 3600)]
            g = g[(g.amt >= 0.5 * amt) & (g.amt <= 1.02 * amt)]
            if len(g):
                best = g.sort_values("tb").iloc[-1]
        hit_t.append(best.tb if best is not None else np.nan)
        hit_h.append(C.norm_hash(best.hash) if best is not None else "")
        hit_usd.append(best.usd if best is not None else np.nan)
        hit_frm.append(best.frm if best is not None else None)
    M["m_addr"] = [h != "" for h in hit_h]
    M["dep_tb"] = hit_t
    M["dep_hl"] = hit_h
    M["dep_frm"] = hit_frm
    M["in_arch"] = M.m_hash | M.m_addr
    key = np.where(M.m_addr, M.dep_hl, M.hl)
    M["in_tg"] = pd.Series(key).isin(t1.index).values
    M["t_post"] = pd.Series(key).map(t1.t).values
    M["t_x"] = pd.Series(key).map(a1.tw_t).values
    M["a_to"] = pd.Series(key).map(a1.to).values
    M["a_frm"] = pd.Series(key).map(a1.frm).values
    M["a_tat"] = pd.Series(key).map(a1.tat).values
    M["calm"] = M.r24.abs() <= 0.05
    M["y"] = pd.to_datetime(M.tb, unit="s").dt.year
    say("\n== Доля событий 🐋 в канале (Telegram) и в архиве (X + Telegram) ==")
    g = M.groupby("per").agg(n=("tb", "size"), calm=("calm", "sum"), in_tg=("in_tg", "mean"), in_arch=("in_arch", "mean"),
                             m_hash=("m_hash", "mean"), m_addr=("m_addr", "mean"), usd_med=("usd", "median"))
    g["in_tg_calm"] = M[M.calm].groupby("per").in_tg.mean()
    say(g.round(3).to_string())
    say("\n== По годам ==")
    say(M.groupby("y").agg(n=("tb", "size"), in_tg=("in_tg", "mean"), in_arch=("in_arch", "mean"),
                           usd_med=("usd", "median")).round(3).to_string())
    # порог канала по годам: 1-й перцентиль суммы алертов «ERC-20 альт → binance» в архиве
    e0 = A[(A.chain == "ethereum") & (A.type == "transfer") & (A.to == "binance")].copy()
    e0 = e0[e0.sym.map(C.coin_class) == "alt"]
    thr = e0.groupby(pd.to_datetime(e0.tb, unit="s").dt.year).usd.quantile(0.01)
    M["thr"] = M.y.map(thr)
    M["above"] = M.usd >= M.thr
    say("\n== Порог канала для ERC-20 → binance (1-й перцентиль суммы, млн $) и охват событий 🐋 выше порога ==")
    say(M.groupby("y").agg(thr=("thr", lambda s: s.iloc[0] / 1e6), above=("above", "mean"),
                           in_arch_above=("in_arch", lambda s: s[M.loc[s.index, "above"]].mean())).round(3).to_string())
    say("\n== По сумме завода, млн $ (все периоды) ==")
    b = pd.cut(M.usd / 1e6, [0, 0.5, 1, 2, 5, 10, 20, 50, 1e9])
    say(M.groupby(b, observed=True).agg(n=("tb", "size"), in_tg=("in_tg", "mean"), in_arch=("in_arch", "mean")).round(3).to_string())
    say("\n== Метки канала у найденных событий 🐋 (откуда → куда) ==")
    x = M[M.in_arch]
    say((x.a_frm.fillna("?") + " → " + x.a_to.fillna("?")).value_counts().head(15).to_string())
    say("   типы адреса получателя у найденных (a_tat): " + str(M[M.in_arch].a_tat.fillna("—").value_counts().to_dict()))
    lead = (M.tb - M.dep_tb) / 60
    say("\n== Пополнение клиента (алерт) раньше сметания 🐋, мин ==")
    say(lead.describe(percentiles=[0.1, 0.5, 0.9]).round(1).to_string())
    lag = (M.t_post - M.tb) / 60
    say("\n== Пост Telegram относительно блока сметания 🐋, мин (минус — пост раньше сметания) ==")
    say(lag.describe(percentiles=[0.1, 0.5, 0.9, 0.99]).round(1).to_string())
    say("   вход 🐋 — закрытие первой 15-мин свечи не раньше чем через 15 мин после блока: пост приходит раньше входа в "
        f"{(lag[lag.notna()] < 15).mean():.0%} случаев")

    # --- обратная сверка: алерты ERC-20 (альты с перпом) → Binance, которых нет в сборе s195
    S = json.load(open("s160/sets.json"))
    cex = {a.lower(): v for a, v in S["cex"].items()}
    toks = {a.lower() for a in S["toks"]} if isinstance(S["toks"], (list, dict)) else set()
    P = C.perps()
    e = A[(A.chain == "ethereum") & (A.type == "transfer") & (A.to == "binance")].copy()
    e["cc"] = e.sym.map(C.coin_class)
    e = e[(e.cc == "alt")].copy()
    e["perp"] = [C.has_perp(P, s, t) for s, t in zip(e.sym, e.tb)]
    e = e[e.perp & (e.tb >= C.PER["2020–2022"][0])]
    syms160 = {v["sym"].upper() for v in S["toks"].values()}
    say(f"\n(алерты с тикером из 261 токена s160: {e.sym.isin(syms160).sum()} из {len(e)})")
    e = e[e.sym.isin(syms160)].copy()
    e["ta_l"] = e.ta.fillna("").str.lower()
    e["lab_ours"] = e.ta_l.map(lambda a: cex.get(a, [None])[0])
    e["in195"] = e.hash.map(C.norm_hash).isin(set(pd.read_pickle("s195_deposits.pkl").tx.map(C.norm_hash)))
    e["per"] = C.period_of(e.tb)
    e["from_unknown"] = e.frm.str.startswith("unknown")
    say("\n== Обратная сверка: алерты «ERC-20 альт с перпом → binance» в архиве ==")
    g = e.groupby("per").agg(n=("hash", "size"), from_unknown=("from_unknown", "mean"), in195=("in195", "mean"),
                             our_binance=("lab_ours", lambda s: (s == "Binance").mean()),
                             our_none=("lab_ours", lambda s: s.isna().mean()))
    say(g.round(3).to_string())
    say("   our_binance — адрес получателя в наших метках Binance (s160 sets.json); our_none — адреса нет в наших метках")
    say("   типы адресов получателя у Whale Alert (tat), где нашей метки нет: " +
        str(e[e.lab_ours.isna()].tat.fillna("—").value_counts().head(6).to_dict()))
    newaddr = e[e.lab_ours.isna()].ta_l.value_counts().head(8)
    say("   частые адреса без нашей метки: " + ", ".join(f"{a[:10]}…:{n}" for a, n in newaddr.items()))
    M.drop(columns=["hl"]).to_csv(f"{C.OUT}/whale_match.csv", index=False)
    open(f"{C.OUT}/whale_match_report.txt", "w").write("\n".join(LINES) + "\n")


if __name__ == "__main__":
    main()
