"""s167: keccak256 of event signatures via public RPC web3_sha3 (no local keccak library)."""
import json, sys, urllib.request
UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
for sig in sys.argv[1:]:
    body = {"jsonrpc": "2.0", "id": 1, "method": "web3_sha3", "params": ["0x" + sig.encode().hex()]}
    r = json.load(urllib.request.urlopen(urllib.request.Request("https://ethereum-rpc.publicnode.com", data=json.dumps(body).encode(), headers=UA), timeout=20))
    print(r["result"], sig)
