"""s288 — качество меток Whale Alert в Ethereum: сверка адресов алертов архива с нашими метками бирж (s160 sets.json:
5331 адрес, spellbook cex_evms + Blockscout, снимок 18.11.2026) — где «unknown wallet» на деле биржа, где биржи
расходятся, сколько адресов Whale Alert помечает сверх наших (адреса пополнения клиентов).
Запуск из /home/user/mc_data: python3 -I <repo>/research/s288/study/labels_check.py → s288/labels_report.txt"""
import json
import os
import re
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


CUST = re.compile(r"prime|anchorage|falconx|bitcoin suisse|copper|bitgo|fireblocks|cumberland|galaxy|wintermute|amber|"
                  r"matrixport|ceffu|cobo|custody", re.I)


def canon(name):
    n = (name or "").lower().replace(" ", "").replace(".", "")
    return {"okex": "okx", "huobi": "htx", "huobiglobal": "htx", "gate": "gateio", "cryptocom": "cryptocom",
            "coinbaseinstitutional": "coinbaseprime", "coinbaseprime": "coinbaseprime", "bitx": "luno"}.get(n, n)


def main():
    S = json.load(open("s160/sets.json"))
    ours = {a.lower(): v[0] for a, v in S["cex"].items()}
    A = pd.read_pickle(f"{C.OUT}/wa_archive.pkl.gz")
    E = A[(A.chain == "ethereum") & (A.type == "transfer")].copy()
    E["per"] = C.period_of(E.tb)
    rows = []
    for side, lab, adr, at in (("отправитель", "frm", "fa", "fat"), ("получатель", "to", "ta", "tat")):
        x = pd.DataFrame({"per": E.per, "lab": E[lab], "adr": E[adr].fillna("").str.lower(), "atype": E[at], "side": side})
        rows.append(x)
    X = pd.concat(rows, ignore_index=True)
    X = X[X.adr != ""]
    X["wa"] = X.lab.map(lambda s: C.entity(s)[0])
    X["wa_name"] = X.lab.map(lambda s: C.entity(s)[1])
    X["our"] = X.adr.map(ours)
    X["our_cust"] = X.our.fillna("").map(lambda s: bool(CUST.search(s)))
    say("Ethereum, переводы из архива Whale Alert (стороны алертов с адресом):", len(X))
    u = X[X.wa == "unknown"]
    say("\n== «unknown wallet» у Whale Alert, а по нашим меткам — биржа (доля сторон) ==")
    g = u.groupby("per").agg(n=("adr", "size"), our_cex=("our", lambda s: s.notna().mean()))
    g["our_cex_not_custody"] = u[~u.our_cust].groupby("per").our.apply(lambda s: s.notna().mean())
    say(g.round(4).to_string())
    say("   какие биржи: " + str(u.our.value_counts().head(10).to_dict()))
    ub = u[u.our == "Binance"]
    say("   «unknown», а у нас Binance — частые адреса (доля таких сторон): " +
        ", ".join(f"{a[:10]}…:{n}" for a, n in ub.adr.value_counts().head(6).items()))
    k = X[X.wa == "cex"].copy()
    k["same"] = [canon(a) == canon(b) for a, b in zip(k.wa_name, k.our.fillna(""))]
    k["cls"] = np.where(k.our.isna(), "нет в наших", np.where(k.same, "та же биржа", "другая биржа"))
    say("\n== Метка биржи у Whale Alert против наших меток (доля сторон) ==")
    say(pd.crosstab(k.per, k.cls, normalize="index").round(3).to_string())
    say("   типы адресов Whale Alert, которых нет в наших метках: " +
        str(k[k.cls == "нет в наших"].atype.fillna("—").value_counts().head(6).to_dict()))
    d = k[k.cls == "другая биржа"]
    say("   расхождения (Whale Alert → наша): " + str((d.wa_name + " → " + d.our).value_counts().head(12).to_dict()))
    b = k[k.wa_name == "Binance"]
    say("\n== Метка «binance» у Whale Alert: типы адресов и совпадение с нашими 150 адресами Binance ==")
    say(pd.crosstab(b.atype.fillna("—"), b.cls).to_string())
    open(f"{C.OUT}/labels_report.txt", "w").write("\n".join(LINES) + "\n")


if __name__ == "__main__":
    main()
