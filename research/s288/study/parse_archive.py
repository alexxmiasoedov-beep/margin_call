"""s288: разбор свободного архива алертов Whale Alert (whale-alerts-archive.json.gz с developer.whale-alert.io)
в компактную таблицу. Архив — недоверенные данные: только json.loads, никакого исполнения.

Запуск: python3 -I parse_archive.py <архив .json.gz> <файл итога без расширения>
Итог: <файл>.pkl — по строке на алерт:
  hash, chain, tb (время блока, с), type (transfer, mint, burn, lock, unlock, freeze), frm, to (метки алерта),
  sym, amt, usd (первая сумма алерта), namt (число сумм), tg (id поста t.me/whale_alert_io), tw (id поста в X),
  tw_t (время поста в X по id-«снежинке», с), fa, ta (главный адрес отправителя и получателя по подоперации монеты),
  fo, to_o (метка владельца адреса), fot, tot (owner_type), fat, tat (address_type), height."""
import gzip
import json
import re
import sys

import pandas as pd

RX_TG = re.compile(r"t\.me/whale_alert_io/(\d+)")
RX_TW = re.compile(r"(?:twitter|x)\.com/whale_alert/status/(\d+)")


def pick(lst, owner):
    """Адрес стороны: с той же меткой, что в алерте, иначе наибольший по сумме."""
    if not lst:
        return {}
    if owner.startswith("unknown") or not owner:
        same = [x for x in lst if not x.get("owner")]          # неизвестная сторона — адреса без владельца
    else:
        same = [x for x in lst if x.get("owner") == owner]
    cand = same or lst

    def amt(x):
        try:
            return float(x.get("amount") or 0)
        except ValueError:
            return 0.0
    return max(cand, key=amt)


def main():
    src, out = sys.argv[1], sys.argv[2]
    rows = []
    bad = 0
    for line in gzip.open(src, "rt", encoding="utf-8", errors="replace"):
        line = line.strip()
        if line.startswith("["):
            line = line[1:]
        line = line.rstrip(",").rstrip("]").rstrip(",")
        if not line:
            continue
        try:
            a = json.loads(line)
        except ValueError:
            bad += 1
            continue
        am = a.get("amounts") or [{}]
        tr = a.get("transaction") or {}
        urls = " ".join(a.get("urls") or [])
        tg = RX_TG.search(urls)
        tw = RX_TW.search(urls)
        twid = int(tw.group(1)) if tw else None
        r = dict(hash=(tr.get("hash") or "").strip(), chain=a.get("blockchain"), tb=a.get("timestamp"),
                 type=a.get("transaction_type"), frm=a.get("from") or "", to=a.get("to") or "",
                 sym=(am[0].get("symbol") or "").upper(), amt=am[0].get("amount"), usd=am[0].get("value_usd"),
                 namt=len(am), tg=int(tg.group(1)) if tg else None, tw=twid,
                 tw_t=((twid >> 22) + 1288834974657) / 1000 if twid and twid > 10 ** 15 else None,
                 height=tr.get("height"))
        sub = [s for s in (tr.get("sub_transactions") or []) if (s.get("symbol") or "").upper() == r["sym"]]
        if sub:
            s = max(sub, key=lambda s: sum(float(x.get("amount") or 0) for x in (s.get("outputs") or s.get("inputs") or [])))
            fi = pick(s.get("inputs"), r["frm"])
            to = pick(s.get("outputs"), r["to"])
            r.update(fa=fi.get("address"), ta=to.get("address"), fo=fi.get("owner"), to_o=to.get("owner"),
                     fot=fi.get("owner_type"), tot=to.get("owner_type"), fat=fi.get("address_type"),
                     tat=to.get("address_type"), nin=len(s.get("inputs") or []), nout=len(s.get("outputs") or []))
        rows.append(r)
    D = pd.DataFrame(rows)
    D.to_pickle(out + ".pkl")
    print("алертов", len(D), "битых строк", bad, "| с постом Telegram", D.tg.notna().sum(), "| с постом X", D.tw.notna().sum())
    print(pd.to_datetime(D.tb, unit="s").dt.year.value_counts().sort_index().to_dict())


if __name__ == "__main__":
    main()
