"""Выгрузка реальных сделок бота для сверки с бэктестом.

Запуск на сервере одной строкой из любой папки:
  curl -sL https://raw.githubusercontent.com/alexxmiasoedov-beep/margin_call/main/tools/export_trades.py | python3

Что делает: читает журнал бота (state.json) и для каждой реальной сделки берёт с Binance
фактические исполнения (/fapi/v1/userTrades: цена, maker/taker, комиссия) и каждое
начисление фандинга (/fapi/v1/income). Печатает компактный текст — его нужно скопировать
в чат. Ключи берутся из ~/.config/margin-call.env и на экран не выводятся; ничего не
меняет и ордеров не ставит.
"""
import json
import os
import sys
import time

home = os.path.expanduser("~")
bot = None
for cand in (os.path.join(home, "projects", "margin_call-live", "bot"),):
    if os.path.exists(os.path.join(cand, "trader.py")):
        bot = cand
if not bot:
    for root, dirs, files in os.walk(home):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__")]
        if "trader.py" in files and "scanner.py" in files and os.path.exists(os.path.join(root, "state.json")):
            bot = root
            break
if not bot:
    raise SystemExit("папка бота со state.json не найдена")
envf = os.path.join(home, ".config", "margin-call.env")
if os.path.exists(envf):
    for line in open(envf):
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
os.chdir(bot)
sys.path.insert(0, bot)
import trader  # noqa: E402

trader.log = lambda *a: None
if not trader.KEY or not trader.SECRET:
    raise SystemExit("ключи Binance не найдены в окружении")
trader.sync_time()
state = json.load(open(os.environ.get("STATE_FILE", "state.json")))
trader.configure(state)
trades = [t for t in state.get("trades", []) if t.get("mode") == "live"]
fmt = lambda ts: time.strftime("%d.%m %H:%M:%S", time.gmtime(ts))
print(f"EXPORT v1 | папка {bot} | реальных сделок {len(trades)} | сейчас {fmt(time.time())} UTC")
print(f"параметры: tp {trader.TP_PCT:g} sl {trader.SL_PCT:g} hold {trader.HOLD_H:g} margin {trader.MARGIN_USDT:g} lev {trader.LEVERAGE}")
for t in sorted(trades, key=lambda t: t["opened"]):
    a = int((t["opened"] - 180) * 1000)
    b = int(((t.get("closed") or time.time()) + 180) * 1000)
    fills = trader._request("GET", "/fapi/v1/userTrades", {"symbol": f"{t['sym']}USDT", "startTime": a, "endTime": min(b, a + 7 * 86400000 - 1), "limit": 1000})
    inc = trader._request("GET", "/fapi/v1/income", {"symbol": f"{t['sym']}USDT", "startTime": a, "endTime": b, "limit": 1000})
    f_txt = []
    if isinstance(fills, list):
        for f in sorted(fills, key=lambda f: int(f["time"])):
            f_txt.append(f"{fmt(int(f['time']) / 1000)} {f['side'][0]} {f['price']}x{f['qty']} {'M' if f.get('maker') else 'T'} "
                         f"fee {float(f['commission']):.5f}{f.get('commissionAsset', '')[:1]} pnl {float(f['realizedPnl']):+.4f}")
    else:
        f_txt.append(f"ошибка userTrades: {trader._err(fills)}")
    fund = []; tot = {"FUNDING_FEE": 0.0, "REALIZED_PNL": 0.0, "COMMISSION": 0.0}
    if isinstance(inc, list):
        for r in sorted(inc, key=lambda r: int(r["time"])):
            typ = r.get("incomeType"); v = float(r.get("income", 0))
            if typ in tot:
                tot[typ] += v
            if typ == "FUNDING_FEE":
                fund.append(f"{fmt(int(r['time']) / 1000)[6:11]} {v:+.5f}")
    print(f"\n# {t['sym']} {'слив' if t.get('rule') == 'dump' else 'памп'} | открыта {fmt(t['opened'])} вход {t['entry']:.6g} (котировка {t.get('quote', 0):.6g}) "
          f"qty {t.get('qty')} sl {t.get('sl', 0):.6g} tp {t.get('tp', 0):.6g}")
    print(f"  закрыта {fmt(t['closed']) if t.get('closed') else 'ОТКРЫТА'} выход {t.get('exit', 0):.6g} причина: {t.get('reason', '')} | бот: {t.get('pnl_usdt', 0):+.4f}")
    print(f"  биржа: pnl {tot['REALIZED_PNL']:+.4f} комиссии {tot['COMMISSION']:+.4f} фандинг {tot['FUNDING_FEE']:+.5f} ({len(fund)} начисл.)")
    print("  исполнения: " + " | ".join(f_txt))
    if fund:
        print("  фандинг: " + ", ".join(fund))
