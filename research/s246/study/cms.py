"""s246: архив объявлений Binance CMS (без ключа) — разделы 161 (Delisting) и 157 (Maintenance Updates).
Считает делистинги перпов (с телами статей), снятия маржи, обновления сетей и миграции по годам. Доходы не считаются.
Кэш — /home/user/mc_data/s246/."""
import json, re, time, datetime, collections, urllib.request, os
D = '/home/user/mc_data/s246/'
UA = {"User-Agent": "research-script/1.0"}
LIST = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query?type=1&pageNo={p}&pageSize=50&catalogId={c}"
DETAIL = "https://www.binance.com/bapi/composite/v1/public/cms/article/detail/query?articleCode={code}"

def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30) as r:
        return json.load(r)

def catalog(c):
    arts, p = [], 1
    while True:
        d = get(LIST.format(p=p, c=c))
        a = [x for cat in d['data']['catalogs'] for x in cat['articles']]
        if not a:
            return arts
        arts += a; p += 1; time.sleep(0.7)

def year(ts):
    return datetime.datetime.fromtimestamp(ts / 1000, datetime.UTC).year

if __name__ == '__main__':
    dl = catalog(161); mt = catalog(157)
    json.dump(dl, open(D + 'cms161.json', 'w')); json.dump(mt, open(D + 'cms157.json', 'w'))
    c = collections.Counter()
    perp_arts = [a for a in dl if re.search(r'Futures.*Delist|Perpetual', a['title'])]
    for a in perp_arts:
        body = re.sub(r'<[^>]+>', ' ', get(DETAIL.format(code=a['code']))['data'].get('body') or '')
        syms = set(re.findall(r'\b([0-9A-Z]{2,20}USDT)\b', a['title'] + ' ' + body)) - {'USDT'}
        c[(year(a['releaseDate']), 'перпы USDT-M (контракты)')] += len(syms); time.sleep(0.4)
    for a in dl:
        t = a['title']
        if re.search('Margin', t) and 'Removal of Margin Trading Pairs' not in t:
            c[(year(a['releaseDate']), 'маржа: делистинг актива')] += 1
    for a in mt:
        t = a['title']
        k = ('обновление сети / хардфорк' if re.search('Upgrade|Hard Fork', t) else
             'обслуживание кошелька' if 'Wallet Maintenance' in t else
             'своп / миграция' if re.search('Swap|Migration|Merge|Rebrand|Redenomination|Conversion', t) else 'прочее')
        c[(year(a['releaseDate']), k)] += 1
    for k in sorted(c):
        print(k, c[k])
