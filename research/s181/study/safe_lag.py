"""s181 — сколько времени виден перевод казны до исполнения в очереди Safe (api.safe.global/tx-service, без ключа):
для адресов казначейств из строгого списка, с которых шли крупные выходы собственного токена (treasury_big.pkl),
проверка «это Safe» (getThreshold через публичный RPC) и разница executionDate − submissionDate у исполненных
переводов токенов (до 200 последних транзакций на Safe). Только задержки; доходы не считаются."""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common181 as C  # noqa: E402

UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
RPC = "https://gateway.tenderly.co/public/mainnet"


def threshold(a):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_call", "params": [{"to": a, "data": "0xe75235b8"}, "latest"]})
    for k in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(RPC, data=body.encode(), headers=UA), timeout=60) as r:
                res = json.load(r).get("result")
            return int(res, 16) if res and res != "0x" and len(res) == 66 else 0
        except Exception:
            time.sleep(3 + 3 * k)
    return None


def checksum(a):
    """EIP-55 через web3_sha3 публичного узла (локального keccak нет)."""
    h = a.lower()[2:]
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "web3_sha3", "params": ["0x" + h.encode().hex()]}).encode()
    for url in (RPC, "https://ethereum-rpc.publicnode.com"):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=UA), timeout=30) as r:
                k = json.load(r).get("result")
            if k:
                k = k[2:]
                return "0x" + "".join(c.upper() if c.isalpha() and int(k[i], 16) >= 8 else c for i, c in enumerate(h))
        except Exception:
            time.sleep(2)
    return None


def safe_get(url):
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "research-script/1.0",
                                                                             "Accept": "application/json"}),
                                        timeout=60) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            if e.code in (404, 422):
                return e.code, b""
            time.sleep(10 * (k + 1))
        except Exception:
            time.sleep(5 * (k + 1))
    return None, b""


def main():
    B = pd.read_pickle(f"{C.OUT}/treasury_big.pkl")
    top = B.groupby("frm").size().sort_values(ascending=False).head(25).index.tolist()
    rows = []
    for a in top:
        th = threshold(a)
        if not th:
            rows.append(dict(addr=a, safe=False))
            continue
        ca = checksum(a)
        url = f"https://api.safe.global/tx-service/eth/api/v1/safes/{ca}/multisig-transactions/?executed=true&limit=200"
        code, raw = safe_get(url)
        if code != 200 or not raw:
            rows.append(dict(addr=a, safe=True, threshold=th, api=code))
            continue
        res = json.loads(raw).get("results") or []
        lags = []
        for t in res:
            dd = t.get("dataDecoded") or {}
            if not (t.get("submissionDate") and t.get("executionDate")):
                continue
            if dd.get("method") not in ("transfer", "multiSend", "approve") and not t.get("transfers"):
                continue
            s0 = datetime.fromisoformat(t["submissionDate"].replace("Z", "+00:00"))
            s1 = datetime.fromisoformat(t["executionDate"].replace("Z", "+00:00"))
            lags.append((s1 - s0).total_seconds() / 3600)
        rows.append(dict(addr=a, safe=True, threshold=th, api=code, n=len(res), n_tr=len(lags),
                         lag_med=float(np.median(lags)) if lags else np.nan,
                         lag_p25=float(np.percentile(lags, 25)) if lags else np.nan,
                         lag_p75=float(np.percentile(lags, 75)) if lags else np.nan))
        time.sleep(1.0)
    X = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print(X.to_string(index=False))
    s = X[X.safe & X.get("lag_med", pd.Series(dtype=float)).notna()] if "lag_med" in X else X.iloc[0:0]
    print(f"\nадресов с крупными выходами: {len(X)}; Safe: {int(X.safe.sum())}; с историей переводов: {len(s)}; "
          f"медиана по Safe медиан задержки «подача → исполнение», ч: {s.lag_med.median():.1f}")


if __name__ == "__main__":
    main()
