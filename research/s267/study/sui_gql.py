"""s267 — мини-клиент Sui GraphQL (graphql.mainnet.sui.io, без ключа; история с генезиса, страница до 50 транзакций).
JSON-RPC на публичных узлах Sui отключён (ответ «JSON-RPC on public fullnodes has been deprecated»)."""
import json
import time
import urllib.error
import urllib.request

URL = "https://graphql.mainnet.sui.io/graphql"
UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
STAT = {"req": 0, "busy": 0}

TXQ = """query($addr: SuiAddress!, $after: String, $before: String, $first: Int, $last: Int, $cp0: UInt53, $cp1: UInt53) {
  transactions(filter: {affectedAddress: $addr, afterCheckpoint: $cp0, beforeCheckpoint: $cp1}, after: $after, before: $before,
               first: $first, last: $last) {
    pageInfo { hasNextPage endCursor hasPreviousPage startCursor }
    nodes { digest sender { address }
      effects { timestamp checkpoint { sequenceNumber }
        balanceChanges(first: 50) { nodes { owner { address } coinType { repr } amount } } } }
  }
}"""


def q(query, var=None, tries=8):
    body = json.dumps({"query": query, "variables": var or {}}).encode()
    for k in range(tries):
        STAT["req"] += 1
        try:
            time.sleep(0.3)
            d = json.loads(urllib.request.urlopen(urllib.request.Request(URL, data=body, headers=UA), timeout=90).read())
            if d.get("errors") and not d.get("data"):
                raise RuntimeError(str(d["errors"])[:300])
            return d["data"]
        except urllib.error.HTTPError as e:
            STAT["busy"] += 1
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(3 + 4 * k)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            STAT["busy"] += 1
            time.sleep(3 + 4 * k)
    raise RuntimeError("Sui GraphQL: нет ответа")


def checkpoint_at(ts_iso_or_unix):
    """Номер контрольной точки около времени (двоичный поиск по checkpoint(sequenceNumber))."""
    import calendar
    t = ts_iso_or_unix if isinstance(ts_iso_or_unix, (int, float)) else calendar.timegm(time.strptime(ts_iso_or_unix, "%Y-%m-%d"))
    hi = int(q("{ checkpoint { sequenceNumber } }")["checkpoint"]["sequenceNumber"])
    lo = 0
    while hi - lo > 1:
        mid = (lo + hi) // 2
        ts = q("query($n: UInt53!) { checkpoint(sequenceNumber: $n) { timestamp } }", {"n": mid})["checkpoint"]["timestamp"]
        tm = calendar.timegm(time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S"))
        if tm >= t:
            hi = mid
        else:
            lo = mid
    return hi


def txs(addr, cp0=None, cp1=None, max_pages=10 ** 6, newest_first=False):
    """Транзакции, затронувшие адрес, в (cp0, cp1): генератор узлов."""
    cur, n = None, 0
    while n < max_pages:
        var = {"addr": addr, "cp0": cp0, "cp1": cp1}
        if newest_first:
            var.update(last=50, before=cur)
        else:
            var.update(first=50, after=cur)
        d = q(TXQ, var)["transactions"]
        nodes = d["nodes"]
        for x in (reversed(nodes) if newest_first else nodes):
            yield x
        n += 1
        pi = d["pageInfo"]
        if newest_first:
            if not pi["hasPreviousPage"]:
                break
            cur = pi["startCursor"]
        else:
            if not pi["hasNextPage"]:
                break
            cur = pi["endCursor"]
