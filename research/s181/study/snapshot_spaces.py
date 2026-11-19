"""s181 — пространства Snapshot (hub.snapshot.org/graphql, без ключа), связанные с перпами Binance USDT-M.
Источники: рейтинг пространств (ranking, по 20 за запрос, первые 4000) и governanceID «snapshot:<id>» в DefiLlama
(/protocols, /lite/protocols2). Связь с перпом: адрес токена в стратегиях голосования = адрес монеты перпа (s160/perp_map:
ethereum, bsc, base, arbitrum), governanceID DefiLlama с тикером перпа или тикер пространства = база перпа при ≥ 5
предложениях и совпадении имени пространства с именем монеты (CoinGecko id из s160/perp_map или имя CMC); пространства
с «test» в имени отброшены.
Итог — /home/user/mc_data/s181/snap_spaces.json. Только охват; доходы не считаются."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common181 as C  # noqa: E402

URL = "https://hub.snapshot.org/graphql"
RAW = f"{C.OUT}/raw/snap_ranking.json"
NOT = {"dao-chain.eth", "so3.sieunhancam.eth", "deepworkstudio.eth"}    # совпадение имени случайное (проверено вручную)


def gql(q):
    code, raw = C.get(URL, data=json.dumps({"query": q}).encode(), headers={"Content-Type": "application/json"})
    if code != 200 or not raw:
        return None
    d = json.loads(raw)
    return d.get("data")


def ranking(pages=200):
    if os.path.exists(RAW):
        return json.load(open(RAW))
    items = []
    for k in range(pages):
        d = gql('query { ranking(first: 20, skip: %d, where: {search: ""}) { items { id name symbol proposalsCount '
                'network strategies { name network params } } } }' % (20 * k))
        it = ((d or {}).get("ranking") or {}).get("items") or []
        if not it:
            break
        items += it
        time.sleep(0.7)
    json.dump(items, open(RAW, "w"))
    return items


def main():
    items = ranking()
    print(f"пространств в рейтинге загружено: {len(items)}")
    P = C.perps()
    B = {}
    for k in P:
        B.setdefault(C.base(k).upper(), []).append(k)
    addr = {}
    for x in json.load(open(f"{C.D}/s160/perp_map.json")):
        for ch in ("eth", "bsc", "base", "arb"):
            if x.get(ch):
                addr[x[ch].lower()] = x["perp"]
    gov = {}
    L = json.load(open(f"{C.D}/s177/raw/api.llama.fi_protocols.json"))
    lp = json.load(open(f"{C.OUT}/raw/lite_protocols2.json"))
    for p in L + lp["parentProtocols"]:
        for g in p.get("governanceID") or []:
            if g.startswith("snapshot:"):
                gov.setdefault(g.split(":", 1)[1], set()).add(((p.get("symbol") or "-").upper(), p.get("gecko_id") or ""))
    ids = {x["id"] for x in items}
    extra = sorted(set(gov) - ids)
    for i in range(0, len(extra), 50):
        part = extra[i:i + 50]
        d = gql('query { spaces(first: 50, where: {id_in: %s}) { id name symbol proposalsCount network '
                'strategies { name network params } } }' % json.dumps(part))
        items += (d or {}).get("spaces") or []
        time.sleep(0.7)
    print(f"добавлено пространств из governanceID DefiLlama: {len(items) - len(ids)}")
    name_of, gid = {}, {}
    for x in json.load(open(f"{C.D}/s160/perp_map.json")):
        name_of.setdefault(x["perp"], set()).add(x["id"].replace("-", " ").lower())
        gid[x["perp"]] = x["id"]
    for x in json.load(open(f"{C.D}/s167/cmc_map_all.json")):
        for k in B.get(str(x["symbol"]).upper(), []):
            if (x.get("rank") or 10 ** 9) < 3000:
                name_of.setdefault(k, set()).add(str(x["name"]).lower())

    def name_ok(space_name, perp):
        sn = str(space_name or "").lower()
        for nm in name_of.get(perp, ()):
            w = [t for t in nm.replace("(", " ").split() if len(t) >= 3 and t not in ("dao", "token", "network",
                                                                                   "protocol", "finance", "coin")]
            if any(t in sn.replace(" ", "") or t in sn for t in w if len(t) >= 4):
                return True
        return False

    out = {}
    for x in items:
        if "test" in str(x.get("name") or "").lower() or "test" in x["id"] or x["id"] in NOT:
            continue
        perps, how = set(), set()
        for s in x.get("strategies") or []:
            a = str((s.get("params") or {}).get("address") or "").lower()
            if a in addr and name_ok(x.get("name"), addr[a]):
                perps.add(addr[a]); how.add("адрес")
        sym = str(x.get("symbol") or "").upper()
        if not perps and sym in B and (x.get("proposalsCount") or 0) >= 5:
            pp = sorted(B[sym], key=len)[0]
            if name_ok(x.get("name"), pp):
                perps.add(pp); how.add("тикер+имя")
        for gsym, gg in gov.get(x["id"], ()):
            if gsym in B:
                pp = sorted(B[gsym], key=len)[0]
                if (gg and gid.get(pp) == gg) or (pp not in gid and name_ok(x.get("name"), pp)):
                    perps.add(pp); how.add("DefiLlama")
        if perps:
            out[x["id"]] = dict(name=x.get("name"), symbol=x.get("symbol"), n=x.get("proposalsCount") or 0,
                                perps=sorted(perps), how=sorted(how))
    json.dump(out, open(f"{C.OUT}/snap_spaces.json", "w"), ensure_ascii=False)
    n5 = {k: v for k, v in out.items() if v["n"] >= 5}
    print(f"пространств, связанных с перпами: {len(out)}; с ≥ 5 предложениями: {len(n5)}; перпов: "
          f"{len({p for v in n5.values() for p in v['perps']})}; предложений всего {sum(v['n'] for v in n5.values())}")
    for k, v in sorted(n5.items(), key=lambda kv: -kv[1]["n"])[:60]:
        print(f"  {k:34s} {str(v['name'])[:28]:28s} {str(v['symbol'])[:8]:8s} {v['n']:5d} {','.join(v['perps'])} ({','.join(v['how'])})")


if __name__ == "__main__":
    main()
