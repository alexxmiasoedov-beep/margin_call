"""s196 — анбондинг Polkadot (28 сут) и Kusama (7 сут) по событиям Staking.Unbonded из открытого API Statescan
(`<сеть>-api.statescan.io/events?section=staking&method=Unbonded`, без ключа; 100 событий на страницу, новые первыми).
После переезда стейкинга на Asset Hub (Kusama 07.10.2025, Polkadot 04.11.2025) события реле-цепи кончаются.
Итог — /home/user/mc_data/s196/<сеть>_unbonded.json: [[блок, время мс, stash, сумма в монетах]]."""
import json
import os
import sys
import time
from common196 import http, OUT

NET = {"polkadot": 1e10, "kusama": 1e12}


def fetch(net, start_page=0, keep=None):
    """keep — уже загруженные события (до start_page); листание продолжается со start_page."""
    p = f"{OUT}/{net}_unbonded.json"
    if os.path.exists(p) and keep is None:
        return json.load(open(p))
    out, page, empty = list(keep or []), start_page, 0
    while True:
        d = http(f"https://{net}-api.statescan.io/events?section=staking&method=Unbonded&page={page}&page_size=100",
                 timeout=60)
        if d is None:
            print("  стоп на странице", page, flush=True)
            break
        items = d.get("items") or []
        if not items:
            break
        for it in items:
            # аргументы — по позиции: (stash, amount); у старых рантаймов оба названы «AccountId»
            args = [x.get("value") for x in it.get("args") or []]
            stash = args[0] if args else None
            amt = args[1] if len(args) > 1 else None
            if isinstance(amt, str):
                amt = int(amt, 16) if amt.startswith("0x") else int(amt)
            out.append([it["indexer"]["blockHeight"], it["indexer"]["blockTime"], stash,
                        amt / NET[net] if amt is not None else None])
        if page % 50 == 0:
            print(net, "стр.", page, "событий", len(out), time.strftime("%Y-%m-%d", time.gmtime(items[-1]["indexer"]["blockTime"] / 1000)),
                  flush=True)
        page += 1
        time.sleep(0.15)
    json.dump(out, open(p, "w"))
    return out


if __name__ == "__main__":
    if sys.argv[1:2] == ["fix"]:
        # Polkadot: события старых рантаймов загружены без суммы — догрузить их заново с нужной страницы
        net = sys.argv[2]
        ev = json.load(open(f"{OUT}/{net}_unbonded.json"))
        k = next(i for i, e in enumerate(ev) if e[3] is None)
        page = k // 100
        print(net, "первое событие без суммы", k, "→ страница", page, flush=True)
        fetch(net, start_page=page, keep=ev[:page * 100])
        ev = json.load(open(f"{OUT}/{net}_unbonded.json"))
        print(net, "всего событий", len(ev), "без суммы", sum(e[3] is None for e in ev), flush=True)
    else:
        for n in (sys.argv[1:] or list(NET)):
            ev = fetch(n)
            print(n, "всего событий", len(ev), flush=True)
