"""Выгрузка флагов Upbit, которые пишет бот (scanner.upbit_flags_watch), — для проверки флагов как сигналов (research/s17).
Источники: файл upbit_flags.csv рядом с state.json бота (вся история с 10.11.2026) и журнал службы — строки «UPBIT»
(хранится около недели) за время до начала файла. В выводе только рыночные данные: время, флаг, монета, фьючерс Binance
и его цена. Имени сервера, логинов, путей и ключей в нём нет — его можно вставить в чат целиком.

Запуск на сервере одной строкой из любой папки:
  curl -sL https://raw.githubusercontent.com/alexxmiasoedov-beep/margin_call/main/tools/upbit_flags.py | python3
Если чат не принимает такой длинный текст — сжатый вариант (в ~5 раз короче):
  curl -sL https://raw.githubusercontent.com/alexxmiasoedov-beep/margin_call/main/tools/upbit_flags.py | python3 - z

Строка вывода: ГГММДД ЧЧММ знак флаг монета фьючерс цена [gN]
  знак: + флаг появился, - снят, = снимок при старте без сохранённой истории;
  флаг: W предупреждение, P скачки цены, V всплеск объёма, D всплеск депозитов, G разница с мировой ценой,
        C концентрация мелких счетов; фьючерс «-» — его нет; gN — прошлый опрос бота был N мин назад (бот не работал).
Ничего не меняет. Копия — в ~/upbit_flags.txt."""
import base64
import collections
import datetime
import gzip
import os
import re
import subprocess
import sys
import time

SINCE = "2026-10-21"
CODE = {"warning": "W", "PRICE_FLUCTUATIONS": "P", "TRADING_VOLUME_SOARING": "V", "DEPOSIT_AMOUNT_SOARING": "D",
        "GLOBAL_PRICE_DIFFERENCES": "G", "CONCENTRATION_OF_SMALL_ACCOUNTS": "C"}
LINE = re.compile(r"(\d{4}-\d\d-\d\d \d\d:\d\d):\d\d UPBIT ([+−=-])(\S+) KRW-(\S+) \| (.*)$")
FUT = re.compile(r"фьючерс (\S+?)(?: ([0-9.eE+-]+))?(?:,|$)")
GAP = re.compile(r"прошлый опрос (\d+) мин назад")
UTC = datetime.timezone.utc


def state_dir():
    """Папка state.json бота: STATE_FILE из ~/.config/margin-call.env, иначе ~/.local/state/margin-call."""
    home = os.path.expanduser("~")
    try:
        for ln in open(os.path.join(home, ".config", "margin-call.env"), encoding="utf-8"):
            if ln.strip().startswith("STATE_FILE="):
                p = ln.split("=", 1)[1].strip().strip("'\"")
                if os.path.isabs(p):
                    return os.path.dirname(p)
                return os.path.dirname(os.path.join(home, "projects", "margin_call-live", "bot", p))
    except OSError:
        pass
    return os.path.join(home, ".local", "state", "margin-call")


def from_file():
    """Строки файла upbit_flags.csv → [(время, знак, флаг, монета, фьючерс, цена, пропуск)]."""
    out = []
    try:
        f = open(os.path.join(state_dir(), "upbit_flags.csv"), encoding="utf-8")
    except OSError:
        return out
    for ln in f:
        p = ln.rstrip("\n").split(",")
        if len(p) < 8 or not p[0].isdigit():
            continue
        fut = p[4][:-4] if p[4].endswith("USDT") else "-"
        out.append((int(p[0]), p[1], p[2], p[3], fut, p[5] or "-", p[7]))
    return out


def from_journal():
    """Строки «UPBIT» журнала службы margin-scanner с SINCE; разные варианты journalctl — как в export_signals.py."""
    deadline, got, partial = time.time() + 150, [], False
    for cmd in (["journalctl", "--user", "-u", "margin-scanner"], ["journalctl", "--user-unit", "margin-scanner"],
                ["journalctl", "-u", "margin-scanner"]):
        for grep in (["-g", "UPBIT"], []):           # -g фильтрует внутри journalctl; старые версии его не знают
            left = int(deadline - time.time())
            if left <= 5:
                break
            try:
                pr = subprocess.Popen(["timeout", str(left)] + cmd + ["--since", SINCE, "--utc", "-o", "cat", "--no-pager", "-q"]
                                      + grep, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, errors="replace")
            except OSError:
                return [], False
            got = [ln.rstrip("\n") for ln in pr.stdout if " UPBIT " in ln]
            partial = pr.wait() == 124               # 124 — journalctl остановлен по времени
            if got:
                break
        if got:
            break
    out = []
    for ln in got:
        m = LINE.search(ln)
        if not m:
            continue
        ts, sign, flag, coin, rest = m.groups()
        t = int(datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M").replace(tzinfo=UTC).timestamp())
        f = FUT.search(rest); g = GAP.search(rest)
        fut = f.group(1)[:-4] if f and f.group(1).endswith("USDT") else "-"
        out.append((t, "-" if sign in "−-" else sign, flag, coin, fut, f.group(2) if f and f.group(2) else "-", g.group(1) if g else ""))
    return out, partial


def main():
    print("читаю файл флагов и журнал службы — до 2–3 минут…", file=sys.stderr, flush=True)
    fl = from_file()
    jl, partial = from_journal()
    first = min((r[0] for r in fl), default=None)
    ev = sorted([r for r in jl if first is None or r[0] < first - 60] + fl)   # из журнала — только то, что было до файла
    rows, cnt = [], collections.Counter()
    for t, sign, flag, coin, fut, price, gap in ev:
        d = datetime.datetime.fromtimestamp(t, UTC)
        rows.append(f"{d:%y%m%d %H%M} {sign} {CODE.get(flag, flag)} {coin} {fut} {price}" + (f" g{gap}" if gap else ""))
        cnt[(sign, CODE.get(flag, flag))] += 1
    head = (f"UPBIT-FLAGS v2 | строк {len(rows)} (из файла {len(fl)}, из журнала {len(rows) - len(fl)}) | "
            f"с {rows[0][:11] if rows else '—'} по {rows[-1][:11] if rows else '—'} (UTC, ГГММДД ЧЧММ)"
            + (" | ⚠️ журнал прочитан не полностью" if partial else ""))
    summary = "появилось: " + ", ".join(f"{c} {cnt[('+', c)]}" for c in "WPVDGC") + "; снято: " + \
              ", ".join(f"{c} {cnt[('-', c)]}" for c in "WPVDGC")
    body = [head, summary] + rows
    try:
        with open(os.path.expanduser("~/upbit_flags.txt"), "w") as fh:
            fh.write("\n".join(body) + "\n")
    except OSError:
        pass
    if not rows:
        print(head)
        print("флагов нет ни в файле, ни в журнале службы — пришлите, пожалуйста, вывод: "
              "journalctl --user -u margin-scanner -n 5 --no-pager")
        return
    print("===== НАЧАЛО — скопируйте всё до строки КОНЕЦ =====")
    if sys.argv[1:2] == ["z"]:
        z = base64.b64encode(gzip.compress("\n".join(body).encode())).decode()
        print(head + " | сжато gzip+base64")
        for i in range(0, len(z), 100):
            print(z[i:i + 100])
    else:
        print("\n".join(body))
    print("===== КОНЕЦ =====")
    print(f"строк {len(rows)}; копия — ~/upbit_flags.txt", file=sys.stderr)


if __name__ == "__main__":
    main()
