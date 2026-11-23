"""s252 — доля событий пилота рядом с известными разлоками (только доля, без цены): окно [T − 7 сут, T + 1 сут] разлока
(1) DefiLlama ≥ 1% обращения (s142_2024–2026.pkl) и (2) CMC token-unlock (кэш s28/ev/<id>_past.json и _up.json, только
чтение): событие разлока с долей ≥ 0,5% общего предложения (любой тип вестинга) и отдельно cliff ≥ 0,5%.
Монета CMC — s252/bsc_tokens.json (BNB Chain) и s160/cmc_ids.json (Ethereum).
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s252/study/unlock_overlap.py"""
import json
import os

import pandas as pd


def cmc_unlocks(cid):
    out = []
    for kind in ("past", "up"):
        p = f"s28/ev/{cid}_{kind}.json"
        if not os.path.exists(p):
            continue
        for e in json.load(open(p)) or []:
            try:
                t = pd.Timestamp(e["time"]).timestamp()
            except Exception:  # noqa: BLE001
                continue
            cliff = any(str(a.get("vestingType") or "").lower() == "cliff" for a in e.get("allocations") or [])
            out.append((t, float(e.get("percentage") or 0), cliff))
    return out


def share(E, unl, key):
    hit = []
    for r in E.itertuples():
        U = unl.get(getattr(r, key), [])
        hit.append(any(T - 7 * 86400 <= r.t <= T + 86400 for T in U))
    return sum(hit), len(hit)


def main():
    S142 = pd.read_pickle("s142_2024–2026.pkl")[["s", "T"]]
    dl = S142.groupby("s")["T"].apply(list).to_dict()
    TB = json.load(open("s252/bsc_tokens.json"))
    ids = json.load(open("s160/cmc_ids.json")) if os.path.exists("s160/cmc_ids.json") else {}
    have = {}
    for name, f, thr_key in (("BNB Chain", "s252/cex_events_25.pkl", "perp"), ("Ethereum", "s252/eth_nospot.pkl", "perp")):
        if not os.path.exists(f):
            continue
        E = pd.read_pickle(f)
        if name == "Ethereum":
            E = E[E.f48c & E.cls.isin(["а", "б"])]
            E = E.assign(pk=E.perp)
            cid = {}
            for tok, v in ids.items():
                if isinstance(v, dict) and v.get("id"):
                    cid[tok] = v["id"]
            E = E.assign(cid=E.tok.map(cid))
        else:
            E = E[E.first48]
            E = E.assign(pk=E.perp.str[:-4], cid=E.perp.map(lambda s: TB[s]["cmc"]))
        cm_any, cm_cliff = {}, {}
        for c in E.cid.dropna().unique():
            u = cmc_unlocks(int(c))
            cm_any[c] = [t for t, p, cl in u if p >= 0.5]
            cm_cliff[c] = [t for t, p, cl in u if p >= 0.5 and cl]
            have[c] = bool(u)
        a, n = share(E, dl, "pk")
        b, _ = share(E, cm_any, "cid")
        c2, _ = share(E, cm_cliff, "cid")
        k = sum(1 for c in E.cid.dropna().unique() if have.get(c))
        print(f"{name}: событий {n}; у разлока DefiLlama ≥ 1% — {a} ({a / max(n, 1):.1%}); CMC ≥ 0,5% — {b} ({b / max(n, 1):.1%}), "
              f"из них cliff — {c2}; монет с расписанием CMC в кэше s28: {k} из {E.cid.nunique()}")


if __name__ == "__main__":
    main()
