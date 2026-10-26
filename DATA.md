# Данные исследований margin_call (сохранены 26.10.2026)

Ветка только с данными, без общей истории с кодом. Скрипты и выводы — в ветке `main`, папка `research/`. Боту ветка
не нужна: сервер забирает только `main`.

Всё — открытые данные: свечи, фандинг и премии Binance, объявления Binance, ставки маржи Binance, архив публичного
канала MarginData. Файлы — pickle (Python 3, numpy) и CSV, сжаты xz; крупные порезаны на части по 45 МБ.

| После распаковки | Что внутри | Период |
|---|---|---|
| `s2/k2y.pkl` (1,4 ГБ) | 15-мин свечи 869 бессрочных фьючерсов USDT-M Binance, включая снятые с торгов: `{монета: {"t": начало свечи, с (int64); "o", "h", "l", "c": цены; "qv": объём в USDT; "tb": покупки тейкеров; "n": число сделок}}` (кроме `t` — float32) | 01.10.2024 – 18.10.2026 |
| `s2/fund2y.pkl` | фандинг: `{монета: массив [время, с; интервал, ч; ставка за интервал]}` | 01.10.2024 – 30.09.2026 |
| `s12/prem.pkl` (414 МБ) | премия фьючерса к индексу, 15 мин: `{монета: (время, с; значение)}` | 01.10.2024 – 18.10.2026 |
| `s7/margin.pkl` | архив канала MarginData: `{"G": {монета: массив [время, займ, отдача, B/R, CHNG]}, "PT": время всех 174 205 постов}`, 497 монет | 20.02.2025 – 21.10.2026 |
| `s10/ann.pkl` | 7192 объявления Binance (разделы 48 — листинги, 49 — новости, 161 — делистинг): `{код: {"cat", "code", "title", "ts" — мс}}` | 07.2017 – 22.10.2026 |
| `s12/perp_kind.pkl`, `s12/ann_perp.pkl` | какие фьючерсы — TradFi (акции, металлы); тексты объявлений о запуске фьючерсов | |
| `s11/rates/*.csv` | ставки маржи Binance VIP 0 по 1032 активам: строки «время, с; дневная ставка» в моменты изменения | с 01.09.2024 |

## Как восстановить

Скрипты `research/s10` … `research/s12` ищут данные по путям `s2/…`, `s7/…`, `s10/…`, `s12/…` от папки, из которой
их запускают. В эту папку и распаковываем:

```
git clone --branch data --single-branch https://github.com/alexxmiasoedov-beep/margin_call.git mc_data_src
mkdir -p mc_data/s2 mc_data/s12 && cd mc_data
cat ../mc_data_src/k2y.pkl.xz.part-* > k2y.pkl.xz && cat ../mc_data_src/prem.pkl.xz.part-* > prem.pkl.xz
cp ../mc_data_src/small.tar.xz . && sha256sum -c ../mc_data_src/SHA256SUMS
xz -d < k2y.pkl.xz > s2/k2y.pkl && xz -d < prem.pkl.xz > s12/prem.pkl && tar -xJf small.tar.xz
rm k2y.pkl.xz prem.pkl.xz small.tar.xz
```

`small.tar.xz` даёт `s2/fund2y.pkl`, `s7/margin.pkl`, `s10/ann.pkl`, `s12/perp_kind.pkl`, `s12/ann_perp.pkl`
и `s11/rates/`. Скриптам `research/s12` нужны ещё их модули: скопируйте `research/s12/*.py` в `mc_data/s12/`
(и создайте пустой `mc_data/s12/__init__.py`), запускайте из `mc_data`: `python3 s12/firstborrow.py`.

Остальные данные исследований (стаканы, сделки, Корея и Турция, посты CryptoCode, позиции) сюда не вошли — их
скачивают заново скрипты в `research/` (источники — data.binance.vision, публичные API бирж, t.me).
