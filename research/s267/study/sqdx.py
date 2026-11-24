"""s267 — бережный клиент SQD Portal для любого набора данных (EVM, Tron): поток блоков с логами или транзакциями
по фильтру, поиск блока по времени. Без ключа; один запрос за раз; при 429/529/5xx — пауза 5–25 с и повтор;
общий предел времени — deadline. Портал отдаёт кусок диапазона — продолжаем с последнего блока + 1."""
import json
import random
import time
import urllib.error
import urllib.request

BASE = "https://portal.sqd.dev/datasets/"
UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
STAT = {"req": 0, "busy": 0}
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def head(ds):
    r = urllib.request.urlopen(urllib.request.Request(BASE + ds + "/head", headers=UA), timeout=60)
    return json.loads(r.read())["number"]


def stream(ds, q, deadline=None):
    body = json.dumps(q).encode()
    k = 0
    while True:
        if deadline and time.time() > deadline:
            raise TimeoutError("SQD: истёк срок")
        STAT["req"] += 1
        try:
            r = urllib.request.urlopen(urllib.request.Request(BASE + ds + "/stream", data=body, headers=UA), timeout=300)
            txt = r.read().decode()
            return [json.loads(x) for x in txt.splitlines() if x.strip()]
        except urllib.error.HTTPError as e:
            if e.code in (429, 529, 500, 502, 503, 504):
                STAT["busy"] += 1
                time.sleep(5 + 4 * min(k, 5) + random.random() * 3)
                k += 1
                continue
            raise
        except Exception:  # noqa: BLE001  (обрыв, тайм-аут)
            STAT["busy"] += 1
            time.sleep(5 + 4 * min(k, 5) + random.random() * 3)
            k += 1
            continue


def block_ts(ds, n, kind="evm"):
    q = {"type": kind, "fromBlock": n, "toBlock": n, "includeAllBlocks": True,
         "fields": {"block": {"number": True, "timestamp": True}}}
    bl = stream(ds, q)
    if not bl:
        return None
    t = bl[0]["header"]["timestamp"]
    return t / 1000 if t > 10 ** 11 else t       # Tron отдаёт миллисекунды


def rpc_block_ts(rpc, n):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_getBlockByNumber", "params": [hex(n), False]}).encode()
    for k in range(6):
        try:
            r = json.loads(urllib.request.urlopen(urllib.request.Request(rpc, data=body, headers=UA), timeout=30).read())
            res = r.get("result")
            return int(res["timestamp"], 16) if res else None
        except Exception:  # noqa: BLE001
            time.sleep(2 + 2 * k)
    return None


def block_at(ds, ts, lo=0, hi=None, kind="evm", rpc=None):
    """Первый блок со временем ≥ ts (двоичный поиск, ~25–30 запросов). С rpc — по публичному узлу сети (SQD не грузим);
    для Tron без rpc — оценка по шагу 3 с от вершины и уточнение по SQD."""
    hi = hi or head(ds)
    if kind == "tron" and not rpc:
        th = block_ts(ds, hi, kind)
        g = max(lo, hi - int((th - ts) / 3))
        for _ in range(4):
            tg = block_ts(ds, g, kind)
            if tg is None:
                break
            step = int((tg - ts) / 3)
            if abs(step) <= 1:
                break
            g = max(lo, min(hi, g - step))
        return g
    if rpc:
        while hi - lo > 1:
            mid = (lo + hi) // 2
            t = rpc_block_ts(rpc, mid)
            if t is None or t >= ts:
                hi = mid
            else:
                lo = mid
        return hi
    while hi - lo > 1:
        mid = (lo + hi) // 2
        t = block_ts(ds, mid, kind)
        if t is None or t >= ts:
            hi = mid
        else:
            lo = mid
    return hi


def pad(a):
    return "0x" + "0" * 24 + a.lower()[2:]


def stream_all(ds, fr, to, q0, deadline=None, kind="evm", progress=None):
    """Все блоки [fr, to] по запросу q0 (без fromBlock/toBlock). → список блоков (header + logs/transactions)."""
    out, cur = [], fr
    while cur <= to:
        q = dict(q0, type=kind, fromBlock=cur, toBlock=to)
        bl = stream(ds, q, deadline=deadline)
        if not bl:
            break
        out += [b for b in bl if b.get("logs") or b.get("transactions")]
        cur = bl[-1]["header"]["number"] + 1
        if progress:
            progress(cur)
    return out
