"""s252 — бережный клиент SQD Portal (BNB Chain) поверх s249/sqd.py: один запрос за раз в потоке (не больше двух потоков),
при 529/429/5xx — пауза 5–23 с со случайной добавкой и повтор без ограничения числа попыток (портал перегружен общим
сбором), общий предел времени — deadline. Ответ портала покрывает ~1000 блоков — продолжаем с последнего блока + 1."""
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "s249"))
import sqd  # noqa: E402,F401  (URL, UA, block_guess)

URL = sqd.URL
UA = sqd.UA
STAT = {"req": 0, "busy": 0, "ok": 0}


def stream(q, deadline=None, log=print):
    body = json.dumps(q).encode()
    k = 0
    while True:
        if deadline and time.time() > deadline:
            raise TimeoutError("SQD: истёк срок")
        STAT["req"] += 1
        try:
            r = urllib.request.urlopen(urllib.request.Request(URL, data=body, headers=UA), timeout=300)
            txt = r.read().decode()
            STAT["ok"] += 1
            return [json.loads(x) for x in txt.splitlines() if x.strip()]
        except urllib.error.HTTPError as e:
            if e.code in (429, 529, 502, 503, 504, 500):
                STAT["busy"] += 1
                time.sleep(5 + 3 * min(k, 5) + random.random() * 3)
                k += 1
                continue
            raise
        except Exception:  # noqa: BLE001  (обрыв, тайм-аут)
            STAT["busy"] += 1
            time.sleep(5 + 3 * min(k, 5) + random.random() * 3)
            k += 1
            continue


def logs(fr, to, flt, fields=None, deadline=None, on_block=None):
    """Все логи в [fr, to] по фильтру flt (dict address/topic0..3). → [(блок, время, лог)]; on_block(next) — для продолжения."""
    fields = fields or {"block": {"number": True, "timestamp": True},
                        "log": {"address": True, "topics": True, "data": True, "transactionHash": True, "logIndex": True}}
    out, cur = [], fr
    while cur <= to:
        q = {"type": "evm", "fromBlock": cur, "toBlock": to, "fields": fields, "logs": [flt]}
        bl = stream(q, deadline=deadline)
        if not bl:
            break
        for b in bl:
            h = b["header"]
            for lg in b.get("logs") or []:
                out.append((h["number"], h.get("timestamp"), lg))
        cur = bl[-1]["header"]["number"] + 1
        if on_block:
            on_block(cur, out)
    return out


_ANCH = None


def block_guess(ts):
    """Блок по времени: кусочно-линейно по опорным точкам s252/anchors.json (уточнены 23.11 на 2025–2026 гг., где время блока
    менялось: 3 с → 1,5 с 29.04.2025, → 0,75 с 30.06.2025, → 0,45 с 01.2026); нет файла — s249/anchors.json."""
    global _ANCH
    if _ANCH is None:
        p = "s252/anchors.json" if os.path.exists("s252/anchors.json") else None
        if p is None:
            return sqd.block_guess(ts)
        _ANCH = sorted((int(t), int(b)) for b, t in json.load(open(p)).items() if t)
    A = _ANCH
    if ts <= A[0][0]:
        return A[0][1]
    for (t0, b0), (t1, b1) in zip(A, A[1:]):
        if t0 <= ts <= t1:
            return int(b0 + (b1 - b0) * (ts - t0) / (t1 - t0))
    t0, b0 = A[-1]
    return int(b0 + (ts - t0) / 0.45)
