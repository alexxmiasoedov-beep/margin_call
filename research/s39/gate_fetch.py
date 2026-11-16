"""s39 — почасовая статистика контрактов Gate (`futures/usdt/contract_stats`, без ключа, история 180 сут) для 300 самых
торгуемых фьючерсов Binance (оборот за 30 сут до 18.10.2026, s2/k2y.pkl). Монета Gate — `<база>_USDT` или `<символ Binance>_USDT`.
Хранятся: время, марк-цена, OI в $, ликвидации лонгов и шортов в $, число счетов в лонге и в шорте, соотношение позиций
крупных счетов. Итог — s39/gate.pkl: {символ Binance: {"gate": контракт, поле: массив}}. Запуск из папки с данными."""
import json
import pickle
import time
import urllib.error
import urllib.request
import numpy as np

API = "https://api.gateio.ws/api/v4/futures/usdt"
FIELDS = ("mark_price", "open_interest_usd", "long_liq_usd", "short_liq_usd", "long_users", "short_users", "top_lsr_size")


def get(u):
    for i in range(5):
        try:
            r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "research", "Accept": "application/json"}), timeout=60)
            return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return None
            time.sleep(3 + 3 * i)
        except Exception:
            time.sleep(3 + 3 * i)
    return None


def top_binance(n=300):
    K = pickle.load(open("s2/k2y.pkl", "rb"))
    vol = {}
    for s, a in K.items():
        t = a["t"]; m = (t >= t[-1] - 30 * 86400)
        vol[s] = float(a["qv"][m].sum())
    skip = {"BTCDOM", "DEFI", "USDC", "XAU", "XAG", "XAUT", "PAXG", "USDBRL"}
    return [s for s, _ in sorted(vol.items(), key=lambda kv: -kv[1]) if s not in skip][:n]


if __name__ == "__main__":
    gate = {c["name"] for c in get(f"{API}/contracts")}
    out, miss = {}, []
    now = int(time.time()); t0 = now - 179 * 86400
    for n, s in enumerate(top_binance()):
        base = s
        for p in ("1000000", "10000", "1000"):
            if s.startswith(p) and len(s) > len(p):
                base = s[len(p):]; break
        name = next((c for c in (f"{s}_USDT", f"{base}_USDT") if c in gate), None)
        if name is None:
            miss.append(s); continue
        rows, frm = [], t0
        while frm < now:
            x = get(f"{API}/contract_stats?contract={name}&interval=1h&limit=2000&from={frm}")
            time.sleep(0.15)
            if not x:
                break
            rows += x
            last = max(r["time"] for r in x)
            if last <= frm or len(x) < 2000:
                break
            frm = last + 3600
        if not rows:
            miss.append(s); continue
        rows = {r["time"]: r for r in rows}
        ts = np.array(sorted(rows))
        d = {"gate": name, "t": ts}
        for f in FIELDS:
            d[f] = np.array([float(rows[t].get(f) or 0) for t in ts])
        out[s] = d
        if n % 25 == 0:
            print(f"  {n}: {s} ← {name}, часов {len(ts)}", flush=True)
    pickle.dump(out, open("s39/gate.pkl", "wb"))
    print(f"готово: {len(out)} монет, нет на Gate: {len(miss)} {miss[:20]}")
