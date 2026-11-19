"""s181 — выгрузка истории казначейств DefiLlama (бесплатный api.llama.fi/treasury/<slug>).

Кандидаты: протоколы из /protocols (кэш s177) и родительские протоколы из /lite/protocols2 с полем treasury, у которых
тикер совпадает с базой перпа Binance USDT-M или тикера нет («-»: DAO сетей). Только загрузка; доходы не считаются.
Кэш — /home/user/mc_data/s181/treasury/<slug>.json.gz. Запуск: python3 -I treasury_fetch.py"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common181 as C  # noqa: E402

OUTD = f"{C.OUT}/treasury"
os.makedirs(OUTD, exist_ok=True)


def candidates():
    P = C.perps()
    B = {C.base(k).upper() for k in P}
    L = json.load(open(f"{C.D}/s177/raw/api.llama.fi_protocols.json"))
    lp_path = f"{C.OUT}/raw/lite_protocols2.json"
    if not os.path.exists(lp_path):
        code, raw = C.get("https://api.llama.fi/lite/protocols2")
        open(lp_path, "wb").write(raw)
    lp = json.load(open(lp_path))
    out = []
    for p in L:
        if p.get("treasury"):
            out.append(dict(slug=p["slug"], sym=p.get("symbol"), kind="child", name=p["name"], gecko=p.get("gecko_id"),
                            cmc=p.get("cmcId"), file=p["treasury"]))
    for p in lp["parentProtocols"]:
        if p.get("treasury"):
            out.append(dict(slug=p["id"].split("#")[-1], sym=p.get("symbol"), kind="parent", name=p["name"],
                            gecko=p.get("gecko_id"), cmc=p.get("cmcId"), file=p["treasury"]))
    keep = [x for x in out if (x["sym"] or "-").upper() in B or (x["sym"] or "-") in ("-", "")]
    return out, keep


def main():
    allc, keep = candidates()
    print(f"казначейств в списках DefiLlama: {len(allc)}; к выгрузке (тикер перпа или «-»): {len(keep)}", flush=True)
    json.dump(keep, open(f"{C.OUT}/treasury_candidates.json", "w"), ensure_ascii=False)
    ok = bad = 0
    for i, x in enumerate(keep):
        fn = f"{OUTD}/{x['slug']}.json.gz"
        if os.path.exists(fn):
            ok += 1
            continue
        t0 = time.time()
        code, raw = C.get(f"https://api.llama.fi/treasury/{x['slug']}")
        if code == 200 and raw:
            C.jsave(json.loads(raw), fn)
            ok += 1
            print(f"{i + 1:3d}/{len(keep)} {x['slug']:34s} {x['sym']!s:8s} {len(raw) / 1e6:6.1f} МБ {time.time() - t0:5.1f} с",
                  flush=True)
        else:
            bad += 1
            print(f"{i + 1:3d}/{len(keep)} {x['slug']:34s} {x['sym']!s:8s} нет ({code})", flush=True)
        time.sleep(1.0)
    print(f"готово: есть {ok}, нет {bad}", flush=True)


if __name__ == "__main__":
    main()
