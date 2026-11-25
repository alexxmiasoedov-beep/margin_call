"""s288 — опись канала Whale Alert: категории постов, частоты в месяц по периодам, пороги и суммы, доля монет с перпом
Binance, задержка «блок → пост» (время блока — из архива Whale Alert по хешу). Только счёт и описательные величины.

Запуск из /home/user/mc_data: python3 -I <repo>/research/s288/study/describe.py [таблица постов без расширения]
Итог — s288/posts.pkl.gz (посты с классами и временем блока), s288/cat_counts.csv, s288/describe_report.txt."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common288 as C  # noqa: E402

SRC = sys.argv[1] if len(sys.argv) > 1 else f"{C.OUT}/wa_io"
LINES = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LINES.append(s)


def load():
    T = pd.read_pickle(SRC + ".pkl")
    A = pd.read_pickle(f"{C.OUT}/wa_archive.pkl.gz")
    A["hl"] = A.hash.str.lower()
    A = A.drop_duplicates(["hl", "sym"])
    T["hl"] = T.hash.fillna("").str.lower()
    m = T.merge(A[["hl", "sym", "tb", "tw_t", "fot", "tot", "fat", "tat", "fa", "ta", "frm", "to", "type", "chain"]]
                .rename(columns={"frm": "a_frm", "to": "a_to", "chain": "a_chain", "sym": "tic"}),
                on=["hl", "tic"], how="left")
    # запасной ключ — только хеш (тикер в посте и архиве иногда разный: BTCB/BTC, USDT/USD₮ и т. п.)
    miss = m.tb.isna() & (m.hl != "")
    if miss.any():
        a1 = A.drop_duplicates("hl").set_index("hl")
        for c in ("tb", "tw_t", "fot", "tot", "fat", "tat", "fa", "ta"):
            m.loc[miss, c] = m.loc[miss, "hl"].map(a1[c])
    return m, A


def classify(D):
    fe = D.frm.map(C.entity)
    te = D.to.map(C.entity)
    D["fe"], D["fn"] = fe.str[0], fe.str[1]
    D["te"], D["tn"] = te.str[0], te.str[1]
    D["cc"] = D.tic.map(C.coin_class)
    D["per"] = C.period_of(D.t)
    cat = np.full(len(D), "", object)
    k, cc, fe_, te_, tn = D.kind.values, D.cc.values, D.fe.values, D.te.values, D.tn.values
    tic = D.tic.fillna("").values
    for i in range(len(D)):
        if k[i] in ("mint", "burn"):
            s = tic[i] if tic[i] in ("USDT", "USDC") else ("другие стейблкоины" if cc[i] == "stable" else "не стейблкоин")
            cat[i] = f"{'чеканка' if k[i] == 'mint' else 'сжигание'} {s}"
            continue
        if k[i] != "transfer":
            continue
        cls = {"stable": "стейблкоин", "btc": "BTC", "eth": "ETH", "alt": "альт", "wrapped": "обёртка", "gold": "золото"}[cc[i]]
        f, t = fe_[i], te_[i]
        dest = "Binance" if (t == "cex" and tn[i] == "Binance") else "другие биржи"
        if cc[i] == "stable" and f == "issuer":
            cat[i] = f"казна → {'биржа ' + dest if t == 'cex' else ('кастоди' if t == 'inst' else 'не биржа')}"
        elif cc[i] == "stable" and t == "issuer":
            cat[i] = f"→ казна ({'с биржи' if f == 'cex' else 'не с биржи'})"
        elif f == "cex" and t == "cex":
            cat[i] = f"{cls}: биржа → биржа" + (" (внутри)" if D.fn.values[i] == tn[i] else "")
        elif t == "cex":
            cat[i] = f"{cls} → {dest}"
        elif f == "cex":
            src = "Binance" if D.fn.values[i] == "Binance" else "другие биржи"
            cat[i] = f"{cls} ← {src}"
        elif t == "inst" or f == "inst":
            cat[i] = f"{cls}: кастоди и ОТС"
        elif f == "unknown" and t == "unknown":
            cat[i] = f"{cls}: неизвестный → неизвестный"
        else:
            cat[i] = f"{cls}: прочее"
    D["cat"] = cat
    # смена сети у эмитента: выход из казны в одной сети и возврат в казну той же суммы (±0,5%) в другой сети за ±24 ч
    D["swap"] = ""
    for tic in ("USDT", "USDC"):
        o = D[(D.kind == "transfer") & (D.tic == tic) & (D.fe == "issuer")]
        r = D[(D.kind == "transfer") & (D.tic == tic) & (D.te == "issuer")]
        if not len(o) or not len(r):
            continue
        rt, ra, rc = r.t.values, r.amt.values, r.chain.fillna("").values
        for i, t, a, ch in zip(o.index, o.t.values, o.amt.values, o.chain.fillna("").values):
            k = (np.abs(rt - t) <= 86400) & (np.abs(ra / a - 1) <= 0.005) & (rc != ch)
            if k.any():
                d = rt[k] - t
                D.at[i, "swap"] = "возврат раньше" if (d <= 0).any() else "возврат позже"
    return D


def per_month(D, mask):
    out = {}
    for p in C.PER:
        out[p] = (mask & (D.per == p)).sum() / C.months(p)
    return out


def main():
    D, A = load()
    D = classify(D)
    D["y"] = pd.to_datetime(D.t, unit="s").dt.year
    say(f"Постов {len(D)}, с {pd.to_datetime(D.t.min(), unit='s')} по {pd.to_datetime(D.t.max(), unit='s')}")
    say("\n== Виды постов по годам ==")
    say(pd.crosstab(D.y, D.kind).to_string())
    al = D.kind.isin(["transfer", "mint", "burn", "stolen", "unlock", "escrow", "stake", "unstake", "frozen", "dormant", "fee"])
    say("\n== Цепи (по ссылке Details), посты-алерты по годам ==")
    say(pd.crosstab(D[al].y, D[al].chain.fillna("—")).to_string())

    # --- категории
    rows = []
    for c in sorted(set(D.cat) - {""}):
        r = per_month(D, D.cat == c)
        r["категория"] = c
        r["всего"] = int((D.cat == c).sum())
        rows.append(r)
    CT = pd.DataFrame(rows).set_index("категория")[["всего"] + list(C.PER)].sort_values("2024–2026", ascending=False)
    CT.to_csv(f"{C.OUT}/cat_counts.csv")
    say("\n== Категории: постов в месяц ==")
    say(CT.round(1).to_string())

    # --- пороги и суммы
    tr = D[D.kind == "transfer"]
    say("\n== Порог канала: 1-й / 5-й перцентиль и медиана суммы перевода, млн $ ==")
    for cc in ("btc", "eth", "stable", "alt"):
        x = tr[tr.cc == cc].groupby("y").usd.quantile([0.01, 0.05, 0.5]).unstack() / 1e6
        say(f"-- {cc}\n" + x.round(2).to_string())
    for k in ("mint", "burn"):
        x = D[(D.kind == k) & D.tic.isin(["USDT", "USDC"])].groupby(["tic", "y"]).usd.quantile([0.01, 0.5]).unstack() / 1e6
        say(f"-- {k} USDT/USDC\n" + x.round(1).to_string())
    say("\n== Суммы переводов по периодам: перцентили 10/50/90/99, млн $ ==")
    for cc in ("btc", "eth", "stable", "alt"):
        x = tr[(tr.cc == cc) & tr.per.notna()].groupby("per").usd.quantile([0.1, 0.5, 0.9, 0.99]).unstack() / 1e6
        say(f"-- {cc}\n" + x.round(1).to_string())

    # --- доля монет с перпом
    P = C.perps()
    D["perp"] = [C.has_perp(P, s, t) if isinstance(s, str) else False for s, t in zip(D.tic, D.t)]
    say("\n== Доля постов-переводов с перпом Binance у монеты (в момент поста) ==")
    for cc in ("alt", "wrapped", "btc", "eth"):
        x = D[(D.kind == "transfer") & (D.cc == cc) & D.per.notna()].groupby("per").perp.agg(["mean", "size"])
        say(f"-- {cc}\n" + x.round(3).to_string())
    alt = D[(D.kind == "transfer") & (D.cc == "alt")]
    say("\n== Альты: топ тикеров по периодам (переводов, из них с перпом) ==")
    for p in C.PER:
        x = alt[alt.per == p]
        top = x.groupby("tic").agg(n=("id", "size"), perp=("perp", "mean")).sort_values("n", ascending=False).head(25)
        say(f"-- {p}: всего {len(x)}, монет {x.tic.nunique()}\n" + " ".join(f"{i}:{r.n}{'' if r.perp > 0.5 else '*'}"
                                                                   for i, r in top.iterrows()))
    say("   (* — без перпа Binance в момент поста)")

    # --- задержка
    D["lag"] = (D.t - D.tb) / 60
    D["lag_x"] = (D.tw_t - D.t) / 60
    say("\n== Сопоставление с архивом по хешу: доля алертов канала с временем блока; доля алертов архива в канале ==")
    a_y = pd.to_datetime(A.tb, unit="s").dt.year
    in_tg = A.hl.isin(set(D.hl[D.hl != ""]))
    cov = pd.DataFrame({"канал→архив": D[al].groupby("y").tb.apply(lambda s: s.notna().mean()),
                        "алертов канала": D[al].groupby("y").size(),
                        "архив→канал": in_tg.groupby(a_y).mean(), "алертов архива": a_y.value_counts().sort_index()})
    say(cov.round(3).to_string())
    say("\n== Задержка «блок → пост Telegram», мин: перцентили по годам ==")
    x = D[al & D.lag.notna()]
    q = x.groupby("y").lag.quantile([0.1, 0.5, 0.75, 0.9, 0.95, 0.99]).unstack()
    q["n"] = x.groupby("y").size()
    say(q.round(1).to_string())
    say("\n== То же по цепям, 2024–2026 гг. ==")
    x2 = x[x.per == "2024–2026"]
    q = x2.groupby("chain").lag.quantile([0.1, 0.5, 0.9, 0.99]).unstack()
    q["n"] = x2.groupby("chain").size()
    say(q[q.n >= 20].round(1).to_string())
    say("\n== Пост в X минус пост в Telegram, мин (где есть оба) ==")
    y = D[al & D.lag_x.notna()]
    say(y.groupby("y").lag_x.quantile([0.1, 0.5, 0.9]).unstack().round(2).to_string())

    say("\n== Выход из казны эмитента: смена сети (парный возврат в казну в другой сети за ±24 ч) ==")
    o = D[(D.kind == "transfer") & D.tic.isin(["USDT", "USDC"]) & (D.fe == "issuer") & D.per.notna()]
    say(pd.crosstab([o.tic, o.per], o.swap.replace("", "выпуск")).to_string())
    say("\n== Получатели выхода из казны (USDT и USDC отдельно), доля по периодам ==")
    for tic in ("USDT", "USDC"):
        o2 = o[(o.tic == tic)].copy()
        o2["кому"] = np.where(o2.te == "cex", o2.tn, o2.te)
        say(f"-- {tic}\n" + pd.crosstab(o2.per, o2["кому"], normalize="index").round(2).loc[:, lambda d: d.max() >= 0.03].to_string())
    say("\n== Стейблкоины на биржи от небиржевых адресов: биржи-получатели, доля по периодам ==")
    q = D[(D.kind == "transfer") & (D.cc == "stable") & (D.te == "cex") & ~D.fe.isin(["cex", "issuer"]) & D.per.notna()]
    say(pd.crosstab(q.per, q.tn, normalize="index").round(2).loc[:, lambda d: d.max() >= 0.04].to_string())
    say("\n== BTC: доля кастоди (Coinbase Inst. и др.) среди переводов BTC по периодам ==")
    b = D[(D.kind == "transfer") & (D.tic == "BTC") & D.per.notna()]
    say(b.groupby("per").apply(lambda g: ((g.fe == "inst") | (g.te == "inst")).mean()).round(3).to_string())
    say("\n== Метка «unknown new wallet» (новый адрес) — доля среди получателей «unknown» по годам ==")
    u = D[(D.kind == "transfer") & D.to.fillna("").str.lower().str.startswith("unknown")]
    say(u.groupby("y").to.apply(lambda s: s.str.lower().str.contains("new").mean()).round(3).to_string())
    D.drop(columns=["hl"]).to_pickle(f"{C.OUT}/posts.pkl.gz", compression="gzip")
    open(f"{C.OUT}/describe_report.txt", "w").write("\n".join(LINES) + "\n")


if __name__ == "__main__":
    main()
