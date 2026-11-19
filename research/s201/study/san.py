"""s201: клиент Santiment GraphQL без ключа (тариф SANAPI FREE) с кэшем, журналом вызовов и жёстким бюджетом.

- Каждый запрос — ровно один GraphQL-запрос верхнего уровня (Santiment считает вызовом каждый такой запрос).
- Кэш: /home/user/mc_data/s201/cache/<sha1 запроса>.json — повторный запрос из кэша вызов не тратит.
- Журнал: /home/user/mc_data/s201/calls.jsonl — время, метка, метрика, число монет, интервал, окно, статус, остатки
  x-ratelimit-remaining-month/hour/minute, размер ответа, первая ошибка.
- Бюджет этапа: не больше 350 вызовов; стоп, если последний известный остаток за месяц < 450.
- User-Agent "research-script/1.0", без ключей, без личных данных.
"""
import hashlib
import json
import os
import time
import urllib.error
import urllib.request

URL = "https://api.santiment.net/graphql"
D = "/home/user/mc_data/s201"
CACHE = f"{D}/cache"
LOG = f"{D}/calls.jsonl"
BUDGET = 350
FLOOR = 450
UA = "research-script/1.0"
os.makedirs(CACHE, exist_ok=True)


class Budget(Exception):
    pass


def stats():
    """(число настоящих вызовов этапа, наименьший виденный остаток за месяц).
    Остаток в заголовках скачет (813 → 1000 → 914 за три вызова подряд — похоже, у прокси несколько внешних адресов
    со своими счётчиками), поэтому для стопа берётся наименьший виденный остаток — осторожный вариант."""
    n, rem = 0, None
    if os.path.exists(LOG):
        for ln in open(LOG):
            r = json.loads(ln)
            if r.get("cached"):
                continue
            n += 1
            if r.get("rem_month") is not None:
                v = int(r["rem_month"])
                rem = v if rem is None else min(rem, v)
    return n, rem


def gql(query, tag, meta=None, force=False, dry=False):
    """Выполнить один GraphQL-запрос. Возвращает разобранный JSON (dict с data/errors)."""
    meta = meta or {}
    key = hashlib.sha1(query.encode()).hexdigest()
    path = f"{CACHE}/{key}.json"
    qpath = f"{CACHE}/{key}.graphql"                 # текст запроса: какие монеты, метрика, окно — для журнала
    if os.path.exists(path) and not force:
        if not os.path.exists(qpath):
            open(qpath, "w").write(query)
        return json.load(open(path))
    if os.environ.get("SAN_CACHE_ONLY"):
        raise Budget("SAN_CACHE_ONLY: запроса нет в кэше, вызов не делается")
    n, rem = stats()
    if n >= BUDGET:
        raise Budget(f"бюджет этапа исчерпан: {n} вызовов")
    if rem is not None and rem < FLOOR:
        raise Budget(f"остаток за месяц {rem} < {FLOOR}")
    if dry:
        return None
    req = urllib.request.Request(URL, data=json.dumps({"query": query}).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": UA,
                                          "Accept": "application/json"})
    t0 = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=180)
        body, hdr, status = resp.read(), resp.headers, resp.status
    except urllib.error.HTTPError as e:
        body, hdr, status = e.read(), e.headers, e.code
    sec = round(time.time() - t0, 2)
    try:
        js = json.loads(body)
    except Exception:
        js = {"errors": [{"message": "не JSON: " + body[:300].decode("utf-8", "replace")}]}
    err = None
    if js.get("errors"):
        err = str(js["errors"][0].get("message", js["errors"][0]))[:300]
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "tag": tag, **meta, "status": status,
           "rem_month": hdr.get("x-ratelimit-remaining-month"), "rem_hour": hdr.get("x-ratelimit-remaining-hour"),
           "rem_minute": hdr.get("x-ratelimit-remaining-minute"), "limit_month": hdr.get("x-ratelimit-limit-month"),
           "bytes": len(body), "sec": sec, "err": err, "key": key}
    with open(LOG, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    open(qpath, "w").write(query)
    if status == 200:
        json.dump(js, open(path, "w"))
    print(f"[san] {tag} {meta.get('metric', '')} slugs={meta.get('n_slugs', '')} {meta.get('interval', '')} "
          f"→ {status}, остаток мес/час/мин {rec['rem_month']}/{rec['rem_hour']}/{rec['rem_minute']}, "
          f"{len(body)} Б, {sec} с" + (f", ОШИБКА: {err}" if err else ""))
    if status == 429:
        raise Budget("429 — лимит Santiment")
    return js


def per_slug(metric, slugs, frm, to, interval="1d", tag="data", extra_selector="", aggregation=None,
             computed_at=False, force=False):
    """timeseriesDataPerSlugJson для списка монет одним вызовом. Возвращает (json, query)."""
    sl = json.dumps(list(slugs))
    sel = f"selector: {{slugs: {sl}{(', ' + extra_selector) if extra_selector else ''}}}"
    agg = f"\n      aggregation: {aggregation}" if aggregation else ""
    ca = "\n      includeComputedAt: true" if computed_at else ""
    q = (f'{{\n  getMetric(metric: "{metric}") {{\n    timeseriesDataPerSlugJson(\n      {sel}\n'
         f'      from: "{frm}"\n      to: "{to}"\n      interval: "{interval}"{agg}{ca}\n    )\n  }}\n}}')
    js = gql(q, tag, {"metric": metric, "n_slugs": len(slugs), "interval": interval, "from": frm, "to": to,
                      "selector": extra_selector or None}, force=force)
    return js, q


def per_slug_frame(js):
    """Ответ timeseriesDataPerSlugJson → длинная таблица (datetime, slug, value[, computedAt])."""
    import pandas as pd
    rows = []
    data = (((js or {}).get("data") or {}).get("getMetric") or {}).get("timeseriesDataPerSlugJson") or []
    for p in data:
        dt = p["datetime"]
        for x in p["data"]:
            rows.append((dt, x["slug"], x.get("value"), x.get("computedAt")))
    df = pd.DataFrame(rows, columns=["datetime", "slug", "value", "computedAt"])
    if len(df):
        df["datetime"] = pd.to_datetime(df.datetime, utc=True)
    return df


if __name__ == "__main__":
    n, rem = stats()
    print(f"вызовов этапа: {n}, последний остаток за месяц: {rem}")
