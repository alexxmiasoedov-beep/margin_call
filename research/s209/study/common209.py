"""s209: общий помощник для проб внутренних эндпоинтов бирж.

Правила этапа: User-Agent только «research-script/1.0», без ключей, куки и регистрации; капчи и Cloudflare
не обходим — такой ответ просто записывается. Каждый ответ сохраняется в /home/user/mc_data/s209/raw/<метка>.json[.gz].
"""
import gzip, json, os, time, urllib.error, urllib.parse, urllib.request

DATA = "/home/user/mc_data/s209"
UA = "research-script/1.0"
os.makedirs(DATA + "/raw", exist_ok=True)

_last = {}


def _pause(host, gap):
    t = _last.get(host, 0)
    d = time.time() - t
    if d < gap:
        time.sleep(gap - d)
    _last[host] = time.time()


def fetch(url, params=None, method="GET", body=None, headers=None, timeout=30, gap=0.4, tries=2):
    """Возвращает (код, заголовки, байты). Сетевые ошибки — пауза и не больше `tries` попыток."""
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params, doseq=True)
    h = {"User-Agent": UA, "Accept": "application/json, text/plain, */*"}
    if headers:
        h.update(headers)
    data = None
    if body is not None:
        data = json.dumps(body).encode() if not isinstance(body, (bytes, str)) else (
            body.encode() if isinstance(body, str) else body)
        h.setdefault("Content-Type", "application/json")
    host = urllib.parse.urlparse(url).netloc
    err = None
    for k in range(tries):
        _pause(host, gap)
        try:
            req = urllib.request.Request(url, data=data, headers=h, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return r.status, dict(r.headers), raw
        except urllib.error.HTTPError as e:
            raw = e.read() or b""
            try:
                if e.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
            except Exception:
                pass
            return e.code, dict(e.headers or {}), raw
        except Exception as e:  # сеть: пауза, без циклов вхолостую
            err = e
            time.sleep(3 * (k + 1))
    return -1, {}, repr(err).encode()


def jget(url, params=None, **kw):
    c, h, b = fetch(url, params, **kw)
    try:
        return c, json.loads(b)
    except Exception:
        return c, b[:500].decode("utf-8", "replace")


def save(tag, obj, gz=False):
    p = f"{DATA}/raw/{tag}.json" + (".gz" if gz else "")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    op = gzip.open if gz else open
    with op(p, "wt", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    return p


def short(obj, n=400):
    s = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
    return s[:n].replace("\n", " ")


def perp_bases():
    """Тикеры перпов Binance из ключей s2/k2y (869), без приставок 1000/1M — для сопоставления."""
    keys = json.load(open("/home/user/mc_data/s205/keys_s2_k2y.pkl.json"))
    out = {}
    for k in keys:
        b = k
        for p in ("1000000", "1000", "1M"):
            if b.startswith(p) and len(b) > len(p):
                b = b[len(p):]
                break
        out[b] = k
    return out
