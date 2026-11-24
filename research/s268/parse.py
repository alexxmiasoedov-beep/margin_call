"""s268 — разбор экспорта Telegram канала Margin_data_exper (messages*.html, присланы владельцем; в репозиторий не кладутся).
Пост — снимок «Margin 24h — ДД.ММ ЧЧ:ММ UTC» с четырьмя таблицами:
  SYM BOR REP B/R CHNG   — займ и отдача маржи за 24 ч (как канал MarginData), их отношение, CHNG;
  FUT FUND OI4H LS P24   — фандинг, изменение OI за 4 ч, лонг/шорт, ход цены за 24 ч;
  LOAN APR [ПУЛ ПУСТ 🔥] — ставка займа и метка «пул пуст»;
  СЕРИЯ ЧАС Р4Ч          — сколько часов монета подряд в списке и ход за 4 ч.
Итог — /home/user/mc_data/s268/posts.pkl: строка на монету в посте.
Запуск: python3 -I <repo>/research/s268/parse.py <messages.html> [ещё файлы…]"""
import html
import re
import sys
from datetime import datetime, timezone, timedelta

import pandas as pd

NUM = {"K": 1e3, "M": 1e6, "B": 1e9}


def num(s):
    s = s.strip()
    if s in ("-", ""):
        return float("nan")
    m = re.fullmatch(r"([+-]?[0-9.]+)([KMB]?)", s.replace("%", ""))
    return float(m.group(1)) * NUM.get(m.group(2), 1) if m else float("nan")


def parse_pre(txt, year):
    lines = [x.rstrip() for x in txt.split("\n")]
    m = re.match(r"Margin 24h — (\d\d)\.(\d\d) (\d\d):(\d\d) UTC", lines[0])
    if not m:
        return None, []
    d, mo, hh, mm = map(int, m.groups())
    hdr = datetime(year, mo, d, hh, mm, tzinfo=timezone.utc)
    rows, sec = {}, None
    for ln in lines[1:]:
        if not ln.strip():
            continue
        p = ln.split()
        if p[0] in ("SYM", "FUT", "LOAN", "СЕРИЯ"):
            sec = p[0]
            continue
        s = p[0]
        r = rows.setdefault(s, {"sym": s})
        if sec == "SYM" and len(p) >= 5:
            r.update(bor=num(p[1]), rep=num(p[2]), br=num(p[3]), chng=num(p[4]))
        elif sec == "FUT" and len(p) >= 5:
            r.update(fund=num(p[1]), oi4h=num(p[2]), ls=num(p[3]), p24=num(p[4]))
        elif sec == "LOAN" and len(p) >= 2:
            r.update(apr=num(p[1]), empty="ПУСТ" in ln)
        elif sec == "СЕРИЯ" and len(p) >= 3:
            r.update(ser_h=num(p[1].rstrip("ч")), p4h=num(p[2]))
        else:
            r.setdefault("other", []).append(ln)
    return hdr, list(rows.values())


def main():
    out = []
    for path in sys.argv[1:]:
        h = open(path, encoding="utf-8").read()
        for m in re.finditer(r'id="message-?(\d+)".*?title="(\d\d)\.(\d\d)\.(\d{4}) (\d\d):(\d\d):(\d\d) GMT([+-]\d\d):(\d\d)"'
                             r'.*?<div class="text">\s*<pre>(.*?)</pre>', h, re.S):
            mid, d, mo, y, hh, mi, ss, tzh, tzm, pre = m.groups()
            tz = timezone(timedelta(hours=int(tzh), minutes=int(tzm) * (1 if int(tzh) >= 0 else -1)))
            posted = datetime(int(y), int(mo), int(d), int(hh), int(mi), int(ss), tzinfo=tz).astimezone(timezone.utc)
            txt = html.unescape(re.sub(r"<br\s*/?>", "\n", pre))
            hdr, rows = parse_pre(txt, posted.year)
            if hdr is None:
                print("не разобран пост", mid, txt[:80].replace("\n", " | "))
                continue
            if hdr > posted + timedelta(days=1):          # переход года
                hdr = hdr.replace(year=hdr.year - 1)
            for r in rows:
                r.update(msg=int(mid), posted=posted, hdr=hdr, n=len(rows))
                out.append(r)
    X = pd.DataFrame(out)
    X.to_pickle("/home/user/mc_data/s268/posts.pkl")
    print("строк", len(X), "постов", X.msg.nunique(), "снимков (время в заголовке)", X.hdr.nunique(),
          "монет", X.sym.nunique())
    print("посты:", X.posted.min(), "…", X.posted.max())
    print("заголовки:", X.hdr.min(), "…", X.hdr.max())


if __name__ == "__main__":
    main()
