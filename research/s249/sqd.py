"""Мини-клиент SQD Portal (BNB Chain) без ключа: поток блоков с логами по фильтру; 529/429 — пауза и повтор."""
import json, time, urllib.request, urllib.error
URL = "https://portal.sqd.dev/datasets/binance-mainnet/stream"
HEAD = "https://portal.sqd.dev/datasets/binance-mainnet/head"
UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}

def head():
    return json.loads(urllib.request.urlopen(urllib.request.Request(HEAD, headers=UA), timeout=30).read())["number"]

def stream(q, tries=30, log=print):
    """Один запрос потока: список блоков (dict). Портал может отдать не весь диапазон — вызывающий продолжает с последнего блока + 1."""
    body = json.dumps(q).encode()
    for k in range(tries):
        try:
            r = urllib.request.urlopen(urllib.request.Request(URL, data=body, headers=UA), timeout=300)
            txt = r.read().decode()
            return [json.loads(x) for x in txt.splitlines() if x.strip()]
        except urllib.error.HTTPError as e:
            code = e.code
            if code in (429, 529, 502, 503, 504):
                time.sleep(min(60, 5 + 5 * k)); continue
            raise
        except Exception as e:
            time.sleep(min(60, 5 + 5 * k)); continue
    raise RuntimeError("SQD: нет ответа")

def logs(fr, to, address=None, topic0=None, topic1=None, topic2=None, log=print):
    """Все блоки с логами в [fr, to] по фильтру (догрузка по частям). → [(блок, время, лог)]."""
    out, cur = [], fr
    flt = {}
    if address: flt["address"] = address
    if topic0: flt["topic0"] = topic0
    if topic1: flt["topic1"] = topic1
    if topic2: flt["topic2"] = topic2
    while cur <= to:
        q = {"type": "evm", "fromBlock": cur, "toBlock": to,
             "fields": {"block": {"number": True, "timestamp": True},
                        "log": {"address": True, "topics": True, "data": True, "transactionHash": True, "logIndex": True}},
             "logs": [flt]}
        bl = stream(q)
        if not bl:
            break
        for b in bl:
            h = b["header"]
            for l in b.get("logs") or []:
                out.append((h["number"], h["timestamp"], l))
        cur = bl[-1]["header"]["number"] + 1
    return out

def block_ts(n):
    """Время блока n (SQD, includeAllBlocks)."""
    q = {"type": "evm", "fromBlock": n, "toBlock": n, "includeAllBlocks": True, "fields": {"block": {"number": True, "timestamp": True}}}
    bl = stream(q)
    return bl[0]["header"]["timestamp"] if bl else None

def block_at(ts, lo=0, hi=None):
    """Первый блок со временем ≥ ts (двоичный поиск)."""
    hi = hi or head()
    while hi - lo > 1:
        mid = (lo + hi) // 2
        t = block_ts(mid)
        if t is None or t >= ts:
            hi = mid
        else:
            lo = mid
    return hi
