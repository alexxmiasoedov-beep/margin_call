"""Частота крупных вводов на адрес ввода Binance (мемо) в сетях Cosmos: страницы входящих (новые → старые), сумма в монетах, доля обращения (CoinGecko, кэш s160)."""
import json, sys, time, urllib.request, urllib.parse, collections, re, calendar
UA = {"User-Agent": "research-script/1.0"}
def get(u, t=90):
    err = ""
    for i in range(3):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t))
        except Exception as e:
            err = str(e)[:100]; time.sleep(3 + 3 * i)
    return {"_err": err}
CFG = {  # сеть: (LCD, адрес ввода, denom, делитель, монет в обращении)
    "TIA": ("https://public-celestia-lcd.numia.xyz", "celestia1fd3mclxp4e2fh0wpau3eg55x2fsm7yjxzg29j2", "utia", 1e6, 992_412_012),
    "ATOM": ("https://cosmos-rest.publicnode.com", "cosmos1j8pp7zvcu9z8vd882m284j29fn2dszh05cqvf9", "uatom", 1e6, 542_559_612),
    "DYDX": ("https://dydx-rest.publicnode.com", "dydx1vvl7htcnzc3g0hsrysxf3vvrk6tpx70822ef6g", "adydx", 1e18, 846_094_216),
    "BABY": ("https://babylon-rest.publicnode.com", "bbn12xkfr9xa9hctxuvaks57xmrxwtlvujxhftz0qf", "ubbn", 1e6, 5_204_594_961),
}
MAXP = int(sys.argv[1]) if len(sys.argv) > 1 else 15
for sym, (lcd, dep, den, dv, circ) in CFG.items():
    rows = []; qq = urllib.parse.quote(f"transfer.recipient='{dep}'")
    for p in range(1, MAXP + 1):
        t = get(f"{lcd}/cosmos/tx/v1beta1/txs?query={qq}&pagination.limit=100&order_by=ORDER_BY_DESC&page={p}")
        trs = t.get("tx_responses") or []
        if not trs:
            if p == 1: print(sym, "нет ответа", t.get("_err", "")); 
            break
        for r in trs:
            if r.get("code"): continue
            ts = calendar.timegm(time.strptime(r["timestamp"][:19], "%Y-%m-%dT%H:%M:%S"))
            amt = 0.0; snd = None
            for ev in r.get("events") or []:
                if ev["type"] == "transfer":
                    at = {x["key"]: x["value"] for x in ev["attributes"]}
                    if at.get("recipient") == dep:
                        for part in (at.get("amount") or "").split(","):
                            m = re.fullmatch(r"(\d+)" + re.escape(den), part.strip())
                            if m: amt += int(m.group(1)) / dv
                        snd = at.get("sender")
            memo = ((r.get("tx") or {}).get("body") or {}).get("memo", "")
            rows.append((ts, amt, snd, memo))
        if len(trs) < 100: break
        time.sleep(0.4)
    if not rows: continue
    span = (max(r[0] for r in rows) - min(r[0] for r in rows)) / 86400
    big5 = [r for r in rows if r[1] >= 0.005 * circ]; big1 = [r for r in rows if r[1] >= 0.001 * circ]
    mon = max(span / 30.4, 1e-9)
    print(f"{sym}: вводов {len(rows)} за {span:.0f} сут ({time.strftime('%Y-%m-%d', time.gmtime(min(r[0] for r in rows)))} … {time.strftime('%Y-%m-%d', time.gmtime(max(r[0] for r in rows)))}); "
          f">=0,1% обращения: {len(big1)} ({len(big1)/mon:.1f}/мес), >=0,5%: {len(big5)} ({len(big5)/mon:.1f}/мес); макс {max(r[1] for r in rows)/circ*100:.2f}%", flush=True)
    for r in sorted(rows, key=lambda x: -x[1])[:5]:
        print("   ", time.strftime('%Y-%m-%d %H:%M', time.gmtime(r[0])), f"{r[1]:,.0f} ({r[1]/circ*100:.2f}%)", r[2], "мемо", r[3][:12])
