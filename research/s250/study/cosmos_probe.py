"""Проба: какие адреса Binance (ключи из меток Cosmostation и PoR Binance, перевод префикса bech32) получают вводы с мемо в сетях Cosmos.
Без ключей: LCD/RPC из chain-registry. Печатает баланс, число вводов на странице и пример мемо."""
import json, sys, time, urllib.request, urllib.parse
sys.path.insert(0, "work")
from bech import convert
UA = {"User-Agent": "research-script/1.0"}
def get(u, t=40):
    try:
        return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t))
    except Exception as e:
        return {"_err": str(e)[:120]}
KEYS = ["cosmos15v50ymp6n5dn73erkqtmq0u8adpl8d3ujv2e74", "cosmos1j8pp7zvcu9z8vd882m284j29fn2dszh05cqvf9",
        "cosmos1l0znsvddllw9knha3yx2svnlxny676d8ns7uys", "cosmos1p3ucd3ptpw902fluyjzhq3ffgq4ntddac9sa3s"]
CH = {"cosmos": ("https://cosmos-rest.publicnode.com", "uatom"), "celestia": ("https://public-celestia-lcd.numia.xyz", "utia"),
      "dydx": ("https://dydx-rest.publicnode.com", "adydx"), "osmo": ("https://osmosis-rest.publicnode.com", "uosmo"),
      "saga": ("https://saga-rest.publicnode.com", "usaga"), "bbn": ("https://babylon-rest.publicnode.com", "ubbn"),
      "terra": ("https://terra-rest.publicnode.com", "uluna"), "band": ("https://laozi1.bandchain.org/api", "uband")}
for hrp, (lcd, den) in CH.items():
    for k in KEYS:
        a = convert(k, hrp)
        b = get(f"{lcd}/cosmos/bank/v1beta1/balances/{a}")
        bal = None
        if "balances" in b:
            bal = sum(int(x["amount"]) for x in b["balances"] if x["denom"] == den)
        q = urllib.parse.quote(f"transfer.recipient='{a}'")
        t = get(f"{lcd}/cosmos/tx/v1beta1/txs?query={q}&pagination.limit=20&order_by=ORDER_BY_DESC&page=1", 60)
        if "_err" in t or not t.get("tx_responses"):
            t2 = get(f"{lcd}/cosmos/tx/v1beta1/txs?events={q}&pagination.limit=20&order_by=ORDER_BY_DESC", 60)
            if t2.get("tx_responses"): t = t2
        trs = t.get("tx_responses") or []
        memos = [ (x.get("tx") or {}).get("body", {}).get("memo", "") for x in trs]
        tot = t.get("total") or (t.get("pagination") or {}).get("total")
        print(f"{hrp:9s} {a[:22]}… bal={bal} txs_on_page={len(trs)} total={tot} last={trs[0]['timestamp'] if trs else None} memos={memos[:5]} err={t.get('_err','')[:60]}", flush=True)
        time.sleep(0.5)
