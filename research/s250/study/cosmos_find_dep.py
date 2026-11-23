"""Найти адрес ввода Binance (мемо) в сетях Cosmos: отправители на «холодный» адрес Binance (ключ p3ucd3…) → у кого много входящих с числовым мемо."""
import json, sys, time, urllib.request, urllib.parse, collections, re
sys.path.insert(0, "work")
from bech import convert
UA = {"User-Agent": "research-script/1.0"}
def get(u, t=60):
    try:
        return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t))
    except Exception as e:
        return {"_err": str(e)[:120]}
def txs(lcd, q, n=50):
    qq = urllib.parse.quote(q)
    t = get(f"{lcd}/cosmos/tx/v1beta1/txs?query={qq}&pagination.limit={n}&order_by=ORDER_BY_DESC&page=1")
    if not t.get("tx_responses"):
        t2 = get(f"{lcd}/cosmos/tx/v1beta1/txs?events={qq}&pagination.limit={n}&order_by=ORDER_BY_DESC")
        if t2.get("tx_responses"): t = t2
    return t
CH = {"celestia": "https://public-celestia-lcd.numia.xyz", "dydx": "https://dydx-rest.publicnode.com", "saga": "https://saga-rest.publicnode.com",
      "bbn": "https://babylon-rest.publicnode.com", "osmo": "https://osmosis-rest.publicnode.com", "band": "https://laozi1.bandchain.org/api"}
KEY = "cosmos1p3ucd3ptpw902fluyjzhq3ffgq4ntddac9sa3s"
for hrp, lcd in CH.items():
    cold = convert(KEY, hrp)
    t = txs(lcd, f"transfer.recipient='{cold}'")
    senders = collections.Counter()
    for r in t.get("tx_responses") or []:
        for ev in r.get("events") or []:
            if ev["type"] == "transfer":
                at = {a["key"]: a["value"] for a in ev["attributes"]}
                if at.get("recipient") == cold and at.get("sender"): senders[at["sender"]] += 1
        for l in r.get("logs") or []:
            for ev in l.get("events") or []:
                if ev["type"] == "transfer":
                    vals = [a["value"] for a in ev["attributes"]]
                    keys = [a["key"] for a in ev["attributes"]]
                    for i, k in enumerate(keys):
                        if k == "recipient" and vals[i] == cold and i + 1 < len(keys) and keys[i + 1] == "sender": senders[vals[i + 1]] += 1
    print(hrp, "cold", cold[:20], "txs", len(t.get("tx_responses") or []), "senders", senders.most_common(5), t.get("_err", ""), flush=True)
    for s, _ in senders.most_common(4):
        if s == cold: continue
        u = txs(lcd, f"transfer.recipient='{s}'", 30)
        trs = u.get("tx_responses") or []
        memos = [ (x.get("tx") or {}).get("body", {}).get("memo", "") for x in trs]
        num = sum(1 for m in memos if re.fullmatch(r"\d{6,12}", m or ""))
        tot = u.get("total") or (u.get("pagination") or {}).get("total")
        print(f"   кандидат {s} входящих всего={tot} на странице={len(trs)} числовых мемо={num} последний={trs[0]['timestamp'] if trs else None} мемо={memos[:4]}", flush=True)
        time.sleep(0.5)
