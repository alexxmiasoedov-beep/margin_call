"""s234 — разбор минусовых сделок виртуальных журналов по выгрузке tools/export_signals.py (вопрос владельца 20.11).
Читает раздел «ВИРТУАЛЬНЫЕ ЖУРНАЛЫ» выгрузки и пишет таблицу сделок: журнал, вход, монета, сторона, цена входа,
тейк/стоп, плечо, исход, время выхода, итог (USDT на 1 USDT маржи), фандинг, хедж, контекст входа.
Доход на сделку в долях цены — итог ÷ плечо (маржа 1 USDT), как в research/s101.
Выгрузка в репозиторий не кладётся (репозиторий публичный). Запуск: python3 parse_export.py <выгрузка> <итог.pkl>"""
import re
import sys
from datetime import datetime, timezone

import pandas as pd

YEAR = 2026
OWN = re.compile(r"^(?P<j>\S+) (?P<d>\d\d\.\d\d \d\d:\d\d:\d\d) (?P<s>\S+) (?P<long>ЛОНГ )?вход (?P<px>[\d.e-]+) "
                 r"(?P<tp>[\d—]+)/(?P<sl>\d+) ×(?P<lev>\d+) (?P<rest>.*)$")
EXIT = re.compile(r"^(?P<why>тейк|стоп|время|выход\S*) (?P<xd>\d\d\.\d\d \d\d:\d\d) (?P<pnl>[+-][\d.]+) ф(?P<f>[+-][\d.]+)"
                  r"(?: хедж (?P<h>[+-][\d.]+))?")
CH = re.compile(r"^(?P<d>\d\d\.\d\d \d\d:\d\d:\d\d) (?P<s>\S+) (?P<kind>pump|dump) вход (?P<px>[\d.e-]+)"
                r"(?: ф/ч (?P<fh>[+-][\d.]+)%)? \| (?P<rest>.*)$")
CHJ = re.compile(r"^(?P<j>\S+) (?P<tp>[\d—]+)/(?P<sl>\d+) (?P<why>тейк|стоп|время) (?P<xd>\d\d\.\d\d \d\d:\d\d) "
                 r"(?P<pnl>[+-][\d.]+) ф(?P<f>[+-][\d.]+)")


def ts(s, fmt):
    return datetime.strptime(f"{YEAR}.{s}", fmt).replace(tzinfo=timezone.utc).timestamp()


def parse(path):
    lines = open(path, encoding="utf-8").read().splitlines()
    a = next(i for i, x in enumerate(lines) if x.startswith("# ВИРТУАЛЬНЫЕ ЖУРНАЛЫ"))
    b = next(i for i, x in enumerate(lines) if i > a and x.startswith("# ") )
    out = []
    for x in lines[a + 1:b]:
        m = OWN.match(x)
        if m:
            head, _, ctx = m["rest"].partition(" | ")
            e = EXIT.match(head)
            out.append({"j": m["j"], "t": ts(m["d"], "%Y.%d.%m %H:%M:%S"), "s": m["s"],
                        "side": "long" if m["long"] else "short", "px": float(m["px"]),
                        "tp": None if m["tp"] == "—" else float(m["tp"]), "sl": float(m["sl"]), "lev": int(m["lev"]),
                        "why": e["why"] if e else ("открыта" if head.startswith("открыта") else head[:20]),
                        "tx": ts(e["xd"], "%Y.%d.%m %H:%M") if e else None,
                        "pnl": float(e["pnl"]) if e else None, "fund": float(e["f"]) if e else None,
                        "hedge": float(e["h"]) if e and e["h"] else None, "ctx": ctx, "kind": None, "fh": None})
            continue
        m = CH.match(x)
        if m:
            for part in m["rest"].split(" | "):
                e = CHJ.match(part.strip())
                if not e:
                    continue
                out.append({"j": e["j"], "t": ts(m["d"], "%Y.%d.%m %H:%M:%S"), "s": m["s"], "side": "short",
                            "px": float(m["px"]), "tp": None if e["tp"] == "—" else float(e["tp"]), "sl": float(e["sl"]),
                            "lev": 10, "why": e["why"], "tx": ts(e["xd"], "%Y.%d.%m %H:%M"), "pnl": float(e["pnl"]),
                            "fund": float(e["f"]), "hedge": None, "ctx": "", "kind": m["kind"],
                            "fh": float(m["fh"]) if m["fh"] else None})
    D = pd.DataFrame(out)
    D["ret"] = D.pnl / D.lev                                   # доход в долях цены при марже 1 USDT
    return D


if __name__ == "__main__":
    D = parse(sys.argv[1])
    D.to_pickle(sys.argv[2])
    C = D[D.pnl.notna()]
    print(f"сделок {len(D)}, закрыто {len(C)}, открыто {D.pnl.isna().sum()}")
    print(C.groupby("j").agg(n=("ret", "size"), ret=("ret", "mean"), win=("ret", lambda r: (r > 0).mean()),
                             loss_n=("ret", lambda r: (r <= 0).sum()), stop=("why", lambda w: (w == "стоп").sum()))
          .sort_values("n", ascending=False).to_string())
