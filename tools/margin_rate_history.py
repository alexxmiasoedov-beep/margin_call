"""История ставок маржи Binance через ключ бота — только чтение (research/s10/ВЫВОДЫ.md, «выкачка пула»).

Запуск на сервере одной строкой из любой папки:
  curl -sL https://raw.githubusercontent.com/alexxmiasoedov-beep/margin_call/main/tools/margin_rate_history.py | python3

Ключ берётся из файлов окружения бота (~/.config/margin-call.env, файлы службы margin-scanner, .env репозитория)
и не печатается. Запросы к ключу — только чтение: GET /sapi/v1/margin/interestRateHistory (вес 1) по каждому
маржинальному активу, VIP 0, окнами по 30 суток назад, пока Binance отдаёт данные (не глубже 12 месяцев).
Ордеров не ставит, бота не трогает. Цены — публичные дневные свечи фьючерсов Binance.

Сохраняет историю в margin_rates/history.csv.gz рядом с state.json и печатает:
  1) глубину и частоту истории ставок;
  2) первую проверку: что было с ценой фьючерса после резкого роста ставки («выкачка пула» автора — пул выбирают,
     займ дорожает) и у монет с самыми высокими ставками (дорогой займ — переполненный шорт).
Копия вывода — ~/margin_rate_history.txt. Время работы — 5–20 минут.
"""
import datetime
import gzip
import hashlib
import hmac
import json
import os
import re
import statistics
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

DAY, WIN, MAX_WIN = 86400, 30 * 86400, 13             # окно запроса истории — 30 суток; не глубже 13 окон (~12 месяцев)
SPEC_URL = "https://www.binance.com/bapi/margin/v1/public/margin/vip/spec/list-all"
SAPI, FAPI = "https://api.binance.com", "https://fapi.binance.com"
home = os.path.expanduser("~")
out = []
MASK = re.compile(r"\d{8,10}:[A-Za-z0-9_-]{30,}|gh[pousr]_[A-Za-z0-9]{20,}|[A-Za-z0-9]{48,}")   # токены и длинные ключи


def p(line=""):
    line = MASK.sub("***", str(line))
    out.append(line)
    print(line, flush=True)


def fmt(ts):
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%d.%m.%Y")


def read_env(path):
    env = {}
    try:
        for line in open(path):
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return env


def run(cmd, timeout=30):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


def find_env():
    """Ключ, секрет и папка состояния бота — как у tools/export_signals.py."""
    bot = next((c for c in (os.path.join(home, "projects", "margin_call-live", "bot"), "/opt/margin_call/bot")
                if os.path.exists(os.path.join(c, "trader.py"))), None)
    files = [os.path.join(home, ".config", "margin-call.env")]
    for sc in (["systemctl", "--user"], ["systemctl"]):
        for line in run(sc + ["show", "-p", "EnvironmentFiles", "margin-scanner"], 15).splitlines():
            path = line.split("=", 1)[-1].split(" (")[0].strip()
            if path and path not in files:
                files.append(path)
    if bot:
        files.append(os.path.join(bot, "..", ".env"))
    env = {}
    for f in files:
        env.update(read_env(f))
    key = os.environ.get("BINANCE_API_KEY") or env.get("BINANCE_API_KEY", "")
    secret = os.environ.get("BINANCE_API_SECRET") or env.get("BINANCE_API_SECRET", "")
    st = env.get("STATE_FILE") or "state.json"
    if not os.path.isabs(st):
        st = os.path.join(bot or os.getcwd(), st)
    return key, secret, os.path.dirname(st)


def get(url, key=None, timeout=30):
    """GET → разобранный JSON; ошибка — dict с code (и _http — код HTTP)."""
    h = {"User-Agent": "margin-call"}
    if key:
        h["X-MBX-APIKEY"] = key
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            j = json.loads(e.read().decode())
        except Exception:
            j = {"code": e.code, "msg": str(e)}
        if isinstance(j, dict):
            j["_http"] = e.code
        return j
    except Exception as e:
        return {"code": -1, "msg": repr(e)}


class Binance:
    def __init__(self, key, secret):
        self.key, self.secret, self.offset = key, secret, 0

    def sync(self):
        j = get(f"{SAPI}/api/v3/time")
        if isinstance(j, dict) and "serverTime" in j:
            self.offset = int(j["serverTime"]) - int(time.time() * 1000)

    def signed(self, path, params):
        q = dict(params, recvWindow=20000, timestamp=int(time.time() * 1000) + self.offset)
        qs = urllib.parse.urlencode(q)
        qs += "&signature=" + hmac.new(self.secret.encode(), qs.encode(), hashlib.sha256).hexdigest()
        return get(f"{SAPI}{path}?{qs}", self.key)

    def rates(self, asset, a, b, depth=0):
        """Ставки актива за [a, b] (сек) → ({время: дневная ставка}, ошибка). Если ответ не доходит до края окна
        (Binance мог обрезать длинный ответ) — дозапрашиваем недостающий кусок."""
        j = None
        for attempt in range(6):
            j = self.signed("/sapi/v1/margin/interestRateHistory",
                            {"asset": asset, "vipLevel": 0, "startTime": a * 1000, "endTime": b * 1000})
            if isinstance(j, list):
                break
            if j.get("code") == -1021:                      # часы разошлись
                self.sync()
                continue
            if j.get("_http") in (429, 418) or j.get("code") in (-1003, -1):
                time.sleep(20 * (attempt + 1))
                continue
            return {}, j
        if not isinstance(j, list):
            return {}, j
        res = {}
        for x in j:
            try:
                res[int(x["timestamp"]) // 1000] = float(x["dailyInterestRate"])
            except (KeyError, TypeError, ValueError):
                pass
        if res and len(j) >= 100 and depth < 6:
            lo, hi = min(res), max(res)
            if lo > a + 2 * DAY:
                r2, _ = self.rates(asset, a, lo - 1, depth + 1)
                res.update(r2)
            if hi < b - 2 * DAY:
                r2, _ = self.rates(asset, hi + 1, b, depth + 1)
                res.update(r2)
        return res, None


def fetch_history(bn, assets, now):
    """Глубина — по BTC (окна по 30 суток назад до двух пустых подряд), затем все активы на эту глубину параллельно."""
    p("# ГЛУБИНА ИСТОРИИ (BTC, окна по 30 суток назад)")
    depth, empty, allbtc = 0, 0, {}
    for k in range(MAX_WIN):
        b = now - k * WIN; a = b - WIN + 1
        res, err = bn.rates("BTC", a, b)
        if err:
            p(f"ошибка Binance: code {err.get('code')} {str(err.get('msg'))[:200]}")
            if err.get("code") in (-2014, -2015, -1022, -2008):
                p("ключ не подошёл для чтения маржи (нужно разрешение «чтение» и IP сервера в списке ключа) — дальше не иду")
                return None, 0
            break
        allbtc.update(res)
        p(f"  {fmt(a)}–{fmt(b)}: записей {len(res)}")
        if res:
            depth, empty = k + 1, 0
        else:
            empty += 1
            if empty >= 2:
                break
    if not allbtc:
        p("истории ставок нет даже по BTC — проверка невозможна")
        return None, 0
    ts = sorted(allbtc)
    step = statistics.median(b - a for a, b in zip(ts, ts[1:])) if len(ts) > 2 else 0
    p(f"BTC: {len(ts)} записей, {fmt(ts[0])} — {fmt(ts[-1])}, обычный шаг {step / 3600:.1f} ч; окон с данными {depth}")
    H, errs = {"BTC": allbtc}, {}

    def one(asset):
        res, empty = {}, 0
        for k in range(depth):
            b = now - k * WIN; a = b - WIN + 1
            r, err = bn.rates(asset, a, b)
            if err:
                errs[asset] = err
                break
            res.update(r)
            empty = 0 if r else empty + 1
            if empty >= 2:                                   # актив моложе — дальше пусто
                break
            time.sleep(0.05)
        return asset, res
    p()
    p(f"# ЗАГРУЗКА: {len(assets)} активов × до {depth} окон")
    t0 = time.time()
    with ThreadPoolExecutor(4) as ex:
        for i, (asset, res) in enumerate(ex.map(one, [a for a in assets if a != "BTC"])):
            if res:
                H[asset] = res
            if (i + 1) % 50 == 0:
                p(f"  {i + 1} активов, {time.time() - t0:.0f} с")
    p(f"загружено: активов с историей {len(H)}, записей {sum(len(v) for v in H.values())}, ошибок {len(errs)}"
      + (f" (пример: {next(iter(errs))} code {next(iter(errs.values())).get('code')})" if errs else ""))
    return H, step


def klines_1d(sym, start):
    """Дневные свечи фьючерса: {сутки (номер дня): (открытие, закрытие, объём $)}."""
    res = {}
    j = get(f"{FAPI}/fapi/v1/klines?symbol={sym}USDT&interval=1d&startTime={start * 1000}&limit=1500", timeout=30)
    if isinstance(j, list):
        for x in j:
            try:
                res[int(x[0]) // 1000 // DAY] = (float(x[1]), float(x[4]), float(x[7]))
            except (TypeError, ValueError, IndexError):
                pass
    return res


def mean(x):
    return sum(x) / len(x) if x else float("nan")


def tstat(x):
    return mean(x) / statistics.stdev(x) * len(x) ** 0.5 if len(x) > 2 and statistics.stdev(x) > 0 else float("nan")


def analyze(H, now):
    """Скачки ставок и уровень ставок против доходности фьючерсов (без фандинга и комиссий — первая прикидка)."""
    daily = {}
    for asset, recs in H.items():
        for ts in sorted(recs):
            daily.setdefault(asset, {})[ts // DAY] = recs[ts]          # ставка на конец суток UTC
    first = min(min(v) for v in daily.values())
    if (now // DAY) - first < 45:
        p(f"истории меньше 45 суток ({(now // DAY) - first}) — проверка будет, когда накопится")
        return
    ex = get(f"{FAPI}/fapi/v1/exchangeInfo")
    syms = (ex.get("symbols") or []) if isinstance(ex, dict) else []
    perp = {s["symbol"][:-4] for s in syms if s.get("contractType") == "PERPETUAL" and s.get("quoteAsset") == "USDT"}
    if not perp:
        p("Binance не отдал список фьючерсов — проверка не сделана")
        return
    fs = {a: next((pf + a for pf in ("", "1000", "10000", "100000", "1000000") if pf + a in perp), None) for a in daily}
    fs = {a: s for a, s in fs.items() if s}
    p()
    p(f"# ЦЕНЫ: дневные свечи {len(fs)} фьючерсов (из {len(daily)} активов с историей ставок; делистингованные не входят)")
    with ThreadPoolExecutor(6) as ex2:
        K = dict(zip(fs, ex2.map(lambda a: klines_1d(fs[a], (first - 70) * DAY), fs)))
    mid = first + ((now // DAY) - first) // 2

    def ret(k, d, n):                                              # вход на закрытии суток d, выход через n суток
        if d in k and d + n in k and k[d][1] > 0:
            return k[d + n][1] / k[d][1] - 1
        return None

    def vol7(k, d):
        v = [k[x][2] for x in range(d - 6, d + 1) if x in k]
        return mean(v) if len(v) >= 5 else 0.0
    # 1) скачок ставки: ставка за сутки ≥ 2× медианы прошлых 14 суток и ≥ 0,03%/сут; одно событие на актив за 7 суток
    p()
    p("# 1) РЕЗКИЙ РОСТ СТАВКИ («выкачка пула»): ставка ≥ X × медианы 14 суток и ≥ 0,03%/сут; вход на закрытии суток")
    base = {1: [], 3: [], 7: []}
    for a, k in K.items():
        for d in daily[a]:
            if vol7(k, d) >= 3e6:
                for n in base:
                    r = ret(k, d, n)
                    if r is not None:
                        base[n].append(r)
    p("  все сутки (объём ≥ 3 млн $/сут): " + "; ".join(f"{n} сут {mean(v) * 100:+.2f}% (в плюсе {mean([x > 0 for x in v]) * 100:.0f}%)"
                                                     for n, v in base.items() if v))
    for X, flat_only in ((2, False), (3, False), (2, True)):
        ev = []
        for a, dr in daily.items():
            k = K.get(a)
            if not k:
                continue
            last = -10**9
            for d in sorted(dr):
                prev = [dr[x] for x in range(d - 14, d) if x in dr]
                if len(prev) < 10 or d - last < 7:
                    continue
                med = statistics.median(prev)
                if med <= 0 or dr[d] < X * med or dr[d] < 0.0003 or vol7(k, d) < 3e6:
                    continue
                if flat_only:
                    r3b = ret(k, d - 3, 3)
                    if r3b is None or abs(r3b) > 0.05:
                        continue
                last = d
                ev.append((d, {n: ret(k, d, n) for n in (1, 3, 7)}))
        nm = f"×{X}" + (" во флэте (цена за 3 сут ±5%)" if flat_only else "")
        if not ev:
            p(f"  {nm}: событий нет")
            continue
        line = []
        for n in (1, 3, 7):
            v = [r[n] for _, r in ev if r[n] is not None]
            h1 = [r[n] for d, r in ev if r[n] is not None and d < mid]; h2 = [r[n] for d, r in ev if r[n] is not None and d >= mid]
            if v:
                line.append(f"{n} сут {mean(v) * 100:+.2f}% (медиана {statistics.median(v) * 100:+.2f}%, в плюсе "
                            f"{mean([x > 0 for x in v]) * 100:.0f}%; 1-я/2-я половина {mean(h1) * 100:+.2f}/{mean(h2) * 100:+.2f})")
        p(f"  {nm}: событий {len(ev)}; " + "; ".join(line))
    # 2) уровень ставки по неделям: квинтили (Q1 — дешёвый займ, Q5 — дорогой) → доход за следующие 7 суток
    p()
    p("# 2) УРОВЕНЬ СТАВКИ по понедельникам (объём ≥ 10 млн $/сут): квинтили → доход фьючерса за 7 суток")
    for nm, score in (("ставка за 7 суток", lambda dr, d: mean([dr[x] for x in range(d - 7, d) if x in dr])),
                      ("ставка за 7 суток к медиане 60 суток", lambda dr, d: (
                          mean([dr[x] for x in range(d - 7, d) if x in dr]) /
                          max(statistics.median([dr[x] for x in range(d - 60, d) if x in dr] or [0]), 1e-9)))):
        Q = {q: [] for q in range(5)}; spread = []; halves = {1: [], 2: []}
        for d in range(first + 60, now // DAY - 7):
            if datetime.datetime.fromtimestamp(d * DAY, datetime.timezone.utc).weekday() != 0:
                continue
            rows = []
            for a, dr in daily.items():
                k = K.get(a)
                if not k or sum(1 for x in range(d - 7, d) if x in dr) < 5 or sum(1 for x in range(d - 60, d) if x in dr) < 30:
                    continue
                r = ret(k, d - 1, 7)
                if r is None or vol7(k, d - 1) < 10e6:
                    continue
                rows.append((score(dr, d), r))
            if len(rows) < 25:
                continue
            rows.sort()
            qs = [rows[i * len(rows) // 5:(i + 1) * len(rows) // 5] for i in range(5)]
            for q in range(5):
                Q[q].append(mean([r for _, r in qs[q]]))
            s = mean([r for _, r in qs[0]]) - mean([r for _, r in qs[4]])
            spread.append(s); halves[1 if d < mid else 2].append(s)
        if not spread:
            p(f"  {nm}: мало данных")
            continue
        p(f"  {nm}: недель {len(spread)}; " + " ".join(f"Q{q + 1} {mean(v) * 100:+.2f}%" for q, v in Q.items())
          + f"; Q1−Q5 {mean(spread) * 100:+.2f}%/нед (t {tstat(spread):.2f}; 1-я/2-я {mean(halves[1]) * 100:+.2f}/{mean(halves[2]) * 100:+.2f})")
    p("(доходность без фандинга и комиссий; Q1−Q5 > 0 — монеты с дешёвым займом лучше дорогих)")


def main():
    now = int(time.time())
    p(f"MARGIN-RATES v1 | сейчас {datetime.datetime.now(datetime.timezone.utc):%d.%m.%Y %H:%M} UTC")
    key, secret, sdir = find_env()
    if not key or not secret:
        p("ключ Binance не найден в ~/.config/margin-call.env и файлах службы — нечего запрашивать")
        return
    p(f"ключ найден (не печатается); папка состояния бота: {sdir}")
    bn = Binance(key, secret)
    bn.sync()
    spec = get(SPEC_URL)
    assets = [a["assetName"] for a in (spec.get("data") or [])] if isinstance(spec, dict) else []
    if not assets:
        j = get(f"{SAPI}/sapi/v1/margin/allAssets", key)
        assets = [x.get("assetName") for x in j if x.get("assetName")] if isinstance(j, list) else []
    p(f"маржинальных активов: {len(assets)}")
    if not assets:
        return
    H, step = fetch_history(bn, assets, now)
    if not H:
        return
    rdir = os.path.join(sdir, "margin_rates")
    os.makedirs(rdir, exist_ok=True)
    fn = os.path.join(rdir, "history.csv.gz")
    with gzip.open(fn, "wt", encoding="utf-8") as f:
        for a, recs in H.items():
            for ts in sorted(recs):
                f.write(f"{a},{ts},{recs[ts]}\n")
    p(f"сохранено: {fn} ({os.path.getsize(fn) // 1024} КБ)")
    try:
        analyze(H, now)
    except Exception as e:
        p(f"проверка прервалась: {e!r}")


if __name__ == "__main__":
    try:
        main()
    finally:
        dest = os.path.join(home, "margin_rate_history.txt")
        try:
            with open(dest, "w") as f:
                f.write("\n".join(out) + "\n")
            print(f"\nкопия: {dest} ({len(out)} строк)")
        except OSError:
            pass
