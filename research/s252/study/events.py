"""s252 — пилот частот: заводы токенов BNB Chain (перпы без спота Binance) на биржи, классы (а), (б), (г).
Вход — s252/rawwin/<окно>.jsonl собранных окон (collect_win.py, окна s252/windows.json), получатели — s252/receivers.json, токены — s252/bsc_tokens.json и
tokens.json, состав индекса — nospot.json. Доходы и цену после событий не считаем — только число событий.
Событие — перевод токена на адрес биржи:
  - отправитель не адрес биржи (метки EVM `bot/cex_labels.tsv`, адреса сметания Binance) и не нулевой адрес;
  - доля = сумма / монет в обращении CMC за день до перевода; пороги 0,5% и 0,25%;
  - перп уже торгуется (onboardDate), спота Binance нет (снимок 23.11.2026).
Классы: (а) биржа есть в составе индекса перпа (gateio, mexc, bitget, bybit, okex, kucoin, coinbase); (б) прочие биржи;
(г) Binance (адреса сметания в BNB Chain).
Подсчёт: все переводы и «первое у монеты за 48 ч» (как у 🐋), по месяцам и с пересчётом окон на месяц; группы токенов по доле выпуска в BNB Chain
(H — выпуск в BNB Chain ≥ 50% монет в обращении, M — меньше).
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s252/study/events.py"""
import bisect
import collections
import glob
import json
import os

import pandas as pd

LABELS = "/home/user/mc_main/bot/cex_labels.tsv"
CONS2EX = {"gateio": "Gate.io", "mexc": "MEXC", "bitget": "Bitget", "bybit": "Bybit", "okex": "OKX", "kucoin": "KuCoin",
           "coinbase": "Coinbase", "bitfinex": "Bitfinex", "huobi": "HTX", "htx": "HTX", "kraken": "Kraken"}
ZERO = "0x0000000000000000000000000000000000000000"


def load():
    lab = set()
    for line in open(LABELS, encoding="utf-8"):
        if not line.startswith("#") and line.strip():
            lab.add(line.split("\t")[0].strip().lower())
    rec = json.load(open("s252/receivers.json"))
    if os.path.exists("s252/extra_receivers.json"):
        for a, ex in json.load(open("s252/extra_receivers.json")).items():
            rec.setdefault(a.lower(), ex)
    lab |= set(rec)
    TB = json.load(open("s252/bsc_tokens.json"))
    TK = json.load(open("s252/tokens.json"))
    NS = json.load(open("s252/nospot.json"))
    tok = {}
    for s, v in TB.items():
        if not v.get("cmc") or TK[s].get("alpha_chain") != "bsc" or not TK[s]["bsc_native"]:
            continue
        days = v["days"]
        ci = [d[1] for d in days]
        last_circ = ci[-1] if ci else None
        grp = "H" if (v["bsc_supply"] and last_circ and v["bsc_supply"] >= 0.5 * last_circ) else "M"
        cons = {CONS2EX.get(c["exchange"], c["exchange"]) for c in NS[s]["cons"]}
        tok[v["contract"]] = {"perp": s, "dates": [d[0] for d in days], "circ": ci, "grp": grp, "cons": cons,
                              "onboard": NS[s]["onboard"] / 1000}
    rows = []
    W = {w["id"]: w for w in json.load(open("s252/windows.json"))}
    done = []
    for f in sorted(glob.glob("s252/rawwin/done_*")):
        wid = f.split("done_")[1]
        done.append(W[wid])
        for line in open(f"s252/rawwin/{wid}.jsonl"):
            rows.append(json.loads(line))
        if os.path.exists(f"s252/rawwin/donex_{wid}"):        # дособор по новым адресам сметания
            for line in open(f"s252/rawwin/{wid}_x.jsonl"):
                rows.append(json.loads(line))
    return lab, rec, tok, rows, done


def circ_at(t, ts):
    day = pd.Timestamp(int(ts) - 86400, unit="s").strftime("%Y-%m-%d")
    i = bisect.bisect_right(t["dates"], day) - 1
    return t["circ"][i] if i >= 0 else None


def main():
    lab, rec, tok, rows, done = load()
    hours = sum((w["t1"] - w["t0"]) / 3600 for w in done)
    print("окон собрано:", len(done), "часов:", hours, "строк:", len(rows), "токенов в выборке:", len(tok))
    ev = []
    seen = set()
    for b, ts, tk, fr, to, amt, tx in rows:
        if (tx, tk, fr, to) in seen:
            continue
        seen.add((tx, tk, fr, to))
        t = tok.get(tk)
        if t is None or fr in lab or fr == ZERO:
            continue
        if ts < t["onboard"]:
            continue
        c = circ_at(t, ts)
        if not c:
            continue
        ex = rec.get(to, "?")
        cls = "г" if ex == "Binance" else ("а" if ex in t["cons"] else "б")
        ev.append({"perp": t["perp"], "t": ts, "frac": amt / c, "ex": ex, "cls": cls, "grp": t["grp"], "fr": fr, "tx": tx,
                   "block": b})
    E = pd.DataFrame(ev)
    U = pd.read_pickle("s142_2024–2026.pkl")[["s", "T"]]                 # разлоки ≥ 1% (DefiLlama, s142)
    E["unl"] = [bool(((U.s == r.perp[:-4]) & (U["T"] - 7 * 86400 <= r.t) & (r.t <= U["T"] + 86400)).any())
                for r in E.itertuples()]
    E.to_pickle("s252/cex_transfers.pkl")
    print("переводов на биржи от не-бирж после запуска перпа:", len(E))
    E["m"] = pd.to_datetime(E.t, unit="s").dt.strftime("%Y-%m")
    for thr in (0.005, 0.0025, 0.001):
        X = E[E.frac >= thr].sort_values("t")
        # первое у монеты за 48 ч (среди событий своего класса и среди всех)
        keep, last = [], {}
        for r in X.itertuples():
            k = (r.perp, r.cls)
            keep.append(not (k in last and r.t - last[k] < 48 * 3600))
            if keep[-1]:
                last[k] = r.t
        X = X.assign(first48=keep)
        print(f"\n=== порог {thr:.2%}: переводов {len(X)}, первых за 48 ч (в своём классе) {int(X.first48.sum())}")
        print(X.groupby(["cls", "grp"]).agg(n=("t", "size"), first48=("first48", "sum"), perps=("perp", "nunique")))
        print("по биржам:", X.ex.value_counts().head(15).to_dict(), "| у разлоков ≥ 1% (T − 7 … T + 1 сут):",
              f"{X.unl.mean():.1%}" if len(X) else "—")
        piv = X[X.first48].pivot_table(index="m", columns="cls", values="t", aggfunc="size", fill_value=0)
        print(piv.to_string())
        # пересчёт на месяц: «монето-окна» с событием (не больше одного на монету и класс в окне 12 ч) / часы окон × 730,5 ч.
        # Это верхняя оценка числа «первых за 48 ч»: пачки переводов одной монеты в соседние дни сливаются в одно событие.
        for lab_, a, b in (("04–06.2025", "2025-04", "2025-06"), ("07–12.2025", "2025-07", "2025-12"),
                           ("01–11.2026", "2026-01", "2026-11")):
            hw = sum((w["t1"] - w["t0"]) / 3600 for w in done
                     if a <= pd.Timestamp(w["t0"], unit="s").strftime("%Y-%m") <= b)
            if not hw:
                continue
            Z = X[(X.m >= a) & (X.m <= b) & X.first48]
            k = 730.5 / hw
            print(f"  {lab_}: окон {hw:.0f} ч; монето-окон с событием в пересчёте на месяц — (а) {len(Z[Z.cls == 'а']) * k:.0f}, "
                  f"(б) {len(Z[Z.cls == 'б']) * k:.0f}, (г) {len(Z[Z.cls == 'г']) * k:.0f}; из них группа H (а) "
                  f"{len(Z[(Z.cls == 'а') & (Z.grp == 'H')]) * k:.0f}, M (а) {len(Z[(Z.cls == 'а') & (Z.grp == 'M')]) * k:.0f}; "
                  f"монето-окон {len(Z)}, разных монет {Z.perp.nunique()}")
        X.to_pickle(f"s252/cex_events_{int(thr * 10000)}.pkl")
        # повторы: у адреса пополнения есть другой перевод ≥ 0,1% той же монеты в том же окне (поток ММ/арбитража)
        S = E[E.frac >= 0.001]
        cnt = S.groupby(["perp", "fr"]).size()
        rep = [cnt.get((r.perp, r.fr), 0) > 1 for r in X.itertuples()]
        print(f"  доля переводов с повтором адреса пополнения в окне (≥ 0,1%): {sum(rep) / max(len(rep), 1):.0%}; "
              f"сметаний Gate в минуту :07 часа: {sum(1 for r in X.itertuples() if r.ex == 'Gate.io' and (r.t // 60) % 60 in (6, 7, 8))}"
              f" из {sum(1 for r in X.itertuples() if r.ex == 'Gate.io')}")


if __name__ == "__main__":
    main()
