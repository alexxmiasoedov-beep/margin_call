"""Выгрузка флагов Upbit, которые бот пишет в журнал службы с 21.10.2026 (строки «UPBIT», scanner.upbit_flags_watch), —
для проверки флагов как сигналов (research). В выводе только рыночные данные: время, флаг, монета, фьючерс Binance и его цена.
Имени сервера, логинов, путей и ключей в нём нет — его можно вставить в чат целиком.

Запуск на сервере одной строкой из любой папки:
  curl -sL https://raw.githubusercontent.com/alexxmiasoedov-beep/margin_call/main/tools/upbit_flags.py | python3
Если чат не принимает такой длинный текст — сжатый вариант (в ~5 раз короче):
  curl -sL https://raw.githubusercontent.com/alexxmiasoedov-beep/margin_call/main/tools/upbit_flags.py | python3 - z

Строка вывода: ММДД ЧЧММ знак флаг монета фьючерс цена [gN]
  знак: + флаг появился, - снят, = снимок при старте без сохранённой истории;
  флаг: W предупреждение, P скачки цены, V всплеск объёма, D всплеск депозитов, G разница с мировой ценой,
        C концентрация мелких счетов; фьючерс «-» — его нет; gN — прошлый опрос бота был N мин назад (бот не работал).
Ничего не меняет. Копия — в ~/upbit_flags.txt."""
import base64
import collections
import gzip
import os
import re
import subprocess
import sys
import time

SINCE = "2026-10-21"
CODE = {"warning": "W", "PRICE_FLUCTUATIONS": "P", "TRADING_VOLUME_SOARING": "V", "DEPOSIT_AMOUNT_SOARING": "D",
        "GLOBAL_PRICE_DIFFERENCES": "G", "CONCENTRATION_OF_SMALL_ACCOUNTS": "C"}
LINE = re.compile(r"(\d{4})-(\d\d)-(\d\d) (\d\d):(\d\d):\d\d UPBIT ([+−=-])(\S+) KRW-(\S+) \| (.*)$")
FUT = re.compile(r"фьючерс (\S+?)(?: ([0-9.eE+-]+))?(?:,|$)")
GAP = re.compile(r"прошлый опрос (\d+) мин назад")


def journal():
    """Строки «UPBIT» журнала службы margin-scanner с SINCE; разные варианты journalctl — как в export_signals.py."""
    deadline = time.time() + 150
    for cmd in (["journalctl", "--user", "-u", "margin-scanner"], ["journalctl", "--user-unit", "margin-scanner"],
                ["journalctl", "-u", "margin-scanner"]):
        for grep in (["-g", "UPBIT"], []):           # -g фильтрует внутри journalctl; старые версии его не знают
            left = int(deadline - time.time())
            if left <= 5:
                return [], True
            try:
                pr = subprocess.Popen(["timeout", str(left)] + cmd + ["--since", SINCE, "--utc", "-o", "cat", "--no-pager", "-q"]
                                      + grep, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, errors="replace")
            except OSError:
                return [], False
            got = [ln.rstrip("\n") for ln in pr.stdout if " UPBIT " in ln]
            partial = pr.wait() == 124               # 124 — journalctl остановлен по времени
            if got:
                return got, partial
    return [], False


def main():
    print("читаю журнал службы — до 2–3 минут…", file=sys.stderr, flush=True)
    raw, partial = journal()
    rows, cnt = [], collections.Counter()
    for ln in raw:
        m = LINE.search(ln)
        if not m:
            continue
        y, mo, d, hh, mi, sign, flag, coin, rest = m.groups()
        f = FUT.search(rest)
        fut = f.group(1)[:-4] if f and f.group(1).endswith("USDT") else "-"
        price = f.group(2) if f and f.group(2) else "-"
        g = GAP.search(rest)
        sign = "-" if sign in "−-" else sign
        rows.append(f"{mo}{d} {hh}{mi} {sign} {CODE.get(flag, flag)} {coin} {fut} {price}" + (f" g{g.group(1)}" if g else ""))
        cnt[(sign, CODE.get(flag, flag))] += 1
    head = (f"UPBIT-FLAGS v1 | строк {len(rows)} | с {rows[0][:9] if rows else '—'} по {rows[-1][:9] if rows else '—'} (UTC, ММДД ЧЧММ)"
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
        print("строк «UPBIT» в журнале службы нет — пришлите, пожалуйста, вывод: journalctl --user -u margin-scanner -n 5 --no-pager")
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
