"""Обход назад от «холодного» адреса Binance (до 3 шагов) — ищем адрес, во входящих которого числовые мемо (адрес ввода по мемо)."""
import json, sys, time, urllib.request, urllib.parse, collections, re
sys.path.insert(0, "work")
from bech import convert
UA = {"User-Agent": "research-script/1.0"}
def get(u, t=60):
    for i in range(2):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t))
        except Exception as e:
            err = str(e)[:100]; time.sleep(2)
    return {"_err": err}
def inbound(lcd, a, n=50):
    qq = urllib.parse.quote(f"transfer.recipient='{a}'")
    t = get(f"{lcd}/cosmos/tx/v1beta1/txs?query={qq}&pagination.limit={n}&order_by=ORDER_BY_DESC&page=1")
    if not t.get("tx_responses"):
        t2 = get(f"{lcd}/cosmos/tx/v1beta1/txs?events={qq}&pagination.limit={n}&order_by=ORDER_BY_DESC")
        if t2.get("tx_responses"): t = t2
    trs = t.get("tx_responses") or []
    snd = collections.Counter(); memos = []
    for r in trs:
        memos.append(((r.get("tx") or {}).get("body") or {}).get("memo", ""))
        for ev in r.get("events") or []:
            if ev["type"] == "transfer":
                at = {x["key"]: x["value"] for x in ev["attributes"]}
                if at.get("recipient") == a and at.get("sender"): snd[at["sender"]] += 1
    tot = t.get("total") or (t.get("pagination") or {}).get("total")
    return snd, memos, tot, (trs[0]["timestamp"] if trs else None)
CH = {"celestia": "https://public-celestia-lcd.numia.xyz", "dydx": "https://dydx-rest.publicnode.com", "saga": "https://saga-rest.publicnode.com",
      "bbn": "https://babylon-rest.publicnode.com"}
KEY = "cosmos1p3ucd3ptpw902fluyjzhq3ffgq4ntddac9sa3s"
for hrp, lcd in CH.items():
    start = convert(KEY, hrp); seen = {start}; frontier = [start]; found = None
    for depth in range(3):
        nxt = []
        for a in frontier:
            snd, memos, tot, last = inbound(lcd, a)
            num = sum(1 for m in memos if re.fullmatch(r"\d{6,12}", m or ""))
            if depth > 0:
                print(f"  {hrp} шаг {depth} {a} входящих={tot} числовых мемо {num}/{len(memos)} последний={last}", flush=True)
            if num >= max(3, len(memos) // 3) and depth > 0:
                found = a; break
            for s, c in snd.most_common(3):
                if s not in seen: seen.add(s); nxt.append(s)
            time.sleep(0.4)
        if found: break
        frontier = nxt[:6]
    print(hrp, "адрес ввода по мемо:", found, flush=True)
