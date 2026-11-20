"""s236 — каталог событий экосистемы Binance Alpha / Wallet с живым фьючерсом Binance USDT-M.
События:
  E1 — листинг в Alpha с эйрдропом за очки (флаг onlineAirdrop списка Alpha, время — listingTime);
  E2 — TGE / Pre-TGE в Binance Wallet (флаг onlineTge, время — listingTime);
  E3 — программы Booster (объявления: тикер, доля предложения на кампанию, число фаз; дата — объявление);
  E4 — торговые соревнования Alpha (объявления: тикер, период «… (UTC) to … (UTC)», конец периода);
  E5 — удаление из Alpha (раздел 161 «Binance Alpha Will Remove …», дата объявления).
Фьючерс «живой», если первая 15-мин свеча с оборотом — не позже чем за сутки до события (s224/k_d.pkl, по 19.11.2026).
Оборот фьючерса — за 24 ч до события. Итог — s236/events.pkl и сводка по месяцам.
Запуск из /home/user/mc_data: MC_K=s224/k_d.pkl MC_F=s224/fund_d.pkl python3 <repo>/research/s236/catalog.py"""
import json
import os
import pickle
import re
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s15"))
from common import K, live  # noqa: E402

DAY = 86400


def fut_for(names):
    for n in names:
        for p in ("", "1000", "1000000"):
            if p + n in K:
                return p + n
    return None


def qv24(s, t):
    a = K[s]; tt = a["t"].astype(np.int64) + 900
    i = np.searchsorted(tt, t, "right"); j = np.searchsorted(tt, t - DAY, "right")
    return float(a["qv"][j:i].sum()) if i > j else np.nan


def ts_utc(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp()


def main():
    LIVE = {s: live(s)[0] for s in K}
    ev = []
    for x in json.load(open("s236/alpha_now.json"))["data"]:
        if x.get("stockState") or x.get("rwaInfo") or not x.get("listingTime"):
            continue
        names = {str(x.get("symbol") or "").upper(), str(x.get("cexCoinName") or "").upper()} - {""}
        t = x["listingTime"] / 1000
        for kind, flag in (("E1 эйрдроп Alpha", "onlineAirdrop"), ("E2 TGE Wallet", "onlineTge")):
            if x.get(flag):
                ev.append({"kind": kind, "t": t, "tick": x["symbol"], "fs": fut_for(names), "chain": x.get("chainName"),
                           "note": ""})
    T = pickle.load(open("s236/texts.pkl", "rb"))
    for v in T.values():
        title, body, t0 = v["title"], v.get("body", ""), v["ts"] / 1000
        m = re.search(r"\(([A-Z0-9]{2,12})\) (?:Booster|Pre-Token|Exclusive Pre|Booster Program|Booster Campaign)", title) \
            or re.search(r"Exclusive [^()]*\(([A-Z0-9]{2,12})\)[^()]*Booster", title)
        if re.search(r"booster", title, re.I) and m:
            share = re.search(r"share of ([\d.]+)% [A-Z0-9]+ token", body)
            ph = re.search(r"(\d+)-(?:phase|week)", body)
            ev.append({"kind": "E3 Booster", "t": t0, "tick": m.group(1), "fs": fut_for({m.group(1)}), "chain": None,
                       "note": f"доля {share.group(1) if share else '?'}%, фаз/недель {ph.group(1) if ph else '?'}"})
        m = re.search(r"Alpha Trading Competition: Trade [^(]*\(([A-Z0-9]{2,12})\)", title)
        if m:
            per = re.findall(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})(?::\d{2})? \(UTC\)", body)
            tend = ts_utc(per[1]) if len(per) >= 2 else t0 + 7 * DAY
            ev.append({"kind": "E4 соревнование Alpha (конец)", "t": tend, "tick": m.group(1), "fs": fut_for({m.group(1)}),
                       "chain": None, "note": f"начало {per[0] if per else '?'}"})
        m = re.search(r"Binance Alpha Will Remove (.+?) \(\d{4}-\d{2}-\d{2}\)", title)
        if m:
            for tk in re.split(r",\s*| and ", m.group(1)):
                tk = re.sub(r"\s*\(.*?\)", "", tk).strip().upper()
                if tk:
                    ev.append({"kind": "E5 удаление из Alpha", "t": t0, "tick": tk, "fs": fut_for({tk}), "chain": None,
                               "note": ""})
    E = pd.DataFrame(ev)
    E["live"] = [bool(f) and np.isfinite(LIVE.get(f, np.nan)) and LIVE[f] <= t - DAY for f, t in zip(E.fs, E.t)]
    E["qv24"] = [qv24(f, t) if lv else np.nan for f, t, lv in zip(E.fs, E.t, E.live)]
    E["month"] = pd.to_datetime(E.t, unit="s").dt.strftime("%Y-%m")
    E.to_pickle("s236/events.pkl")
    pd.set_option("display.width", 220)
    print("событий по классам (всего / с живым фьючерсом ≥ 1 сут до события):")
    print(E.groupby("kind").agg(всего=("t", "size"), с_фьючерсом=("live", "sum")).to_string())
    print("\nс живым фьючерсом по месяцам:")
    print(pd.crosstab(E.month[E.live], E.kind[E.live]).to_string())
    print("\nоборот фьючерса за 24 ч до события, млн $ (медиана):",
          E[E.live].groupby("kind").qv24.median().div(1e6).round(1).to_dict())
    print("\nBooster:"); print(E[E.kind == "E3 Booster"][["month", "tick", "fs", "live", "note"]].to_string())


if __name__ == "__main__":
    main()
