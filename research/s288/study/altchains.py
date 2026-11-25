"""s288 — альты на биржи по цепям (вопрос о расширении 🐋 на сети, которые мы не собирали): заводы монет с перпом Binance
от небиржевых адресов на Binance и другие биржи — в месяц по периодам и цепям, доля монет в обращении (CMC), сумма
к суточному обороту CMC. Только счёт и описательные величины.
Запуск из /home/user/mc_data: python3 -I <repo>/research/s288/study/altchains.py → s288/altchains.csv, altchains_report.txt"""
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


def main():
    P = pd.read_pickle(f"{C.OUT}/posts.pkl.gz")
    x = P[(P.kind == "transfer") & P.cc.isin(["alt", "wrapped"]) & (P.te == "cex") & (P.fe != "cex") & P.per.notna()].copy()
    x["dest"] = np.where(x.tn == "Binance", "Binance", "другие")
    x["chain"] = x.chain.fillna("—")
    CI = C.Circ(syms=set(x.tic.dropna().unique()))
    v = [CI.get(s, t, (u / a) if a else None) for s, t, u, a in zip(x.tic, x.t, x.usd, x.amt)]
    x["circ"], x["cmc_px"], x["cmc_vol"] = [z[0] for z in v], [z[1] for z in v], [z[2] for z in v]
    px = x.usd / x.amt
    x["px_ok"] = (x.cmc_px > 0) & (px / x.cmc_px).between(0.5, 2)
    x["frac"] = np.where(x.px_ok, x.amt / x.circ, np.nan)
    x["lam"] = np.where(x.px_ok & (x.cmc_vol > 0), x.usd / x.cmc_vol, np.nan)
    x["from_unk"] = x.fe == "unknown"
    say(f"Заводы альтов (и обёрток) на биржи от небиржевых адресов, периоды 10.2020–11.2026: {len(x)}")
    say("доля с перпом Binance:", round(x.perp.mean(), 3), "| с обращением CMC и сверкой цены:", round(x.frac.notna().mean(), 3))
    rows = []
    for (per, dest, ch), g in x[x.perp].groupby(["per", "dest", "chain"]):
        m = C.months(per)
        rows.append(dict(per=per, dest=dest, chain=ch, n_mo=len(g) / m, unk_mo=g.from_unk.sum() / m,
                         f05_mo=(g.frac >= 0.005).sum() / m, f01_mo=(g.frac >= 0.001).sum() / m,
                         lam05_mo=(g.lam >= 0.05).sum() / m, coins=g.tic.nunique(),
                         usd_med=g.usd.median() / 1e6, frac_med=g.frac.median()))
    R = pd.DataFrame(rows)
    R.to_csv(f"{C.OUT}/altchains.csv", index=False)
    for dest in ("Binance", "другие"):
        say(f"\n== Заводы альтов с перпом → {dest}: в месяц по периодам и цепям ==")
        say("   n — все; unk — от «unknown wallet»; f05 — ≥ 0,5% обращения; f01 — ≥ 0,1%; lam05 — сумма ≥ 5% суточного "
            "оборота CMC; usd_med — медиана, млн $")
        t = R[R.dest == dest].pivot_table(index="chain", columns="per", values=["n_mo", "f05_mo", "lam05_mo"], aggfunc="sum")
        say(t.round(2).fillna(0).to_string())
    say("\n== Монеты заводов → Binance с ≥ 0,5% обращения (все периоды) ==")
    y = x[x.perp & (x.dest == "Binance") & (x.frac >= 0.005)]
    say(y.groupby(["per", "chain"]).tic.agg(lambda s: ", ".join(f"{k}:{n}" for k, n in s.value_counts().head(12).items())).to_string())
    say("\n== Медиана доли обращения у заводов → Binance по цепям (не Ethereum) ==")
    z = x[x.perp & (x.dest == "Binance") & (x.chain != "ethereum")]
    say(z.groupby(["chain"]).agg(n=("id", "size"), usd_med=("usd", "median"), frac_med=("frac", "median"),
                                 frac_p90=("frac", lambda s: s.quantile(0.9))).round(5).to_string())
    x.drop(columns=["text"], errors="ignore").to_pickle(f"{C.OUT}/alt_deposits.pkl.gz", compression="gzip")
    open(f"{C.OUT}/altchains_report.txt", "w").write("\n".join(LINES) + "\n")


if __name__ == "__main__":
    main()
