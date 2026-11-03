"""
Общие вещи для всех парсеров: модель вакансии, HTTP-клиент с ретраями,
парсинг зарплаты/типа судна из свободного текста, генерация ID для дедупликации.

Каждый файл в parsers/ должен экспортировать функцию:

    def fetch_vacancies(config: dict) -> list[Vacancy]:
        ...

Она обязана сама ловить все свои исключения (см. main.py, который тоже
оборачивает вызов в try/except — но парсер не должен полагаться только на это,
желательно логировать причину прямо на месте) и в худшем случае вернуть [].
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass, field

import requests

logger = logging.getLogger("maritime_job_agent")


@dataclass
class Vacancy:
    source: str                 # имя источника, напр. "martide"
    title: str                  # должность, напр. "Master / Captain"
    url: str                    # ссылка на вакансию (используется для дедупликации)
    vessel_type: str = ""       # тип судна как есть в объявлении
    salary_raw: str = ""        # зарплата как есть в объявлении ("" если не указана)
    salary_usd_month: float | None = None  # распарсенное число, если удалось
    flag: str = ""
    contract_length: str = ""
    company: str = ""
    location: str = ""
    raw_text: str = ""          # весь текст карточки — на случай если regex что-то пропустил
    vessel_class_unknown: bool = False  # True: "Bulk Carrier" без класса/DWT в карточке — проверить вручную

    @property
    def id(self) -> str:
        """Стабильный уникальный ID для дедупликации (по ссылке)."""
        # Query-строку отбрасываем: UkrCrewing, например, добавляет к ссылке
        # ?v_sort=0&v_sort_dir=0 — это та же вакансия, не новая.
        key = self.url.strip().split("?")[0].split("#")[0].rstrip("/").lower()
        if not key:
            key = f"{self.source}|{self.title}|{self.vessel_type}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


DEFAULT_HEADERS_TEMPLATE = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    # ВАЖНО: без "br" — стандартный requests не умеет распаковывать Brotli
    # без дополнительного пакета (brotli/brotlicffi), иначе resp.text будет
    # бинарной кашей и все селекторы молча перестанут находить ссылки.
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}


def http_get(url: str, config: dict, **kwargs) -> requests.Response:
    """GET с общим User-Agent, таймаутом и одним повтором при сетевой ошибке."""
    net_cfg = config.get("network", {})
    timeout = net_cfg.get("timeout_seconds", 25)
    headers = dict(DEFAULT_HEADERS_TEMPLATE)
    headers["User-Agent"] = net_cfg.get("user_agent", "Mozilla/5.0")
    headers.update(kwargs.pop("headers", {}) or {})

    last_exc = None
    for attempt in range(2):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last_exc = exc
            if attempt == 0:
                time.sleep(2)
    raise last_exc  # type: ignore[misc]


BLOCKED_STATUSES = {403, 429, 503}


def browser_get_html(url: str, config: dict) -> str:
    """Загрузка страницы настоящим headless-браузером (Playwright/Chromium).

    Нужна для сайтов, которые отдают 403 простому HTTP-клиенту (анти-бот
    защита вроде Cloudflare), но пускают обычный браузер. Если Playwright не
    установлен — бросает ImportError, и вызывающий код просто залогирует сбой.
    """
    from playwright.sync_api import sync_playwright  # импорт только по необходимости

    net_cfg = config.get("network", {})
    timeout_ms = int(net_cfg.get("timeout_seconds", 25) * 1000) * 2
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                user_agent=net_cfg.get("user_agent", "Mozilla/5.0"),
                locale="en-US",
            )
            resp = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            # Даём время на JS-челлендж анти-бота и подгрузку списка
            page.wait_for_timeout(5000)
            status = resp.status if resp else 0
            html = page.content()
        finally:
            browser.close()
    if status in BLOCKED_STATUSES and "vacanc" not in html.lower():
        raise RuntimeError(f"Браузер тоже получил HTTP {status} для {url}")
    return html


def fetch_html(url: str, config: dict) -> str:
    """HTML страницы: сначала быстрый requests, при блокировке (403/429/503) —
    резервная попытка через headless-браузер."""
    try:
        return http_get(url, config).text
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status not in BLOCKED_STATUSES:
            raise
        logger.info("HTTP %s для %s — пробую через headless-браузер", status, url)
        return browser_get_html(url, config)


def polite_sleep(config: dict) -> None:
    delay = config.get("network", {}).get("polite_delay_seconds", 1.5)
    if delay:
        time.sleep(delay)


# ---------------------------------------------------------------------------
# Извлечение зарплаты из свободного текста
# ---------------------------------------------------------------------------

_SALARY_PATTERNS = [
    # "$11,500", "USD 11500", "US$ 11 500"
    re.compile(r"(?:usd|us\$|\$)\s*([\d][\d,\.\s]{2,10})", re.IGNORECASE),
    # "11500 usd", "11,500 usd/month"
    re.compile(r"([\d][\d,\.\s]{2,10})\s*(?:usd|us\$|\$)", re.IGNORECASE),
]


def parse_salary_usd(text: str) -> float | None:
    """Best-effort извлечение месячной зарплаты в USD из текста объявления.

    Если найдено несколько чисел (диапазон "10000-13000") — берём МАКСИМАЛЬНОЕ,
    т.к. нас интересует, дотягивает ли вакансия вообще до порога.
    Возвращает None, если зарплата в тексте не найдена или не в USD.
    """
    if not text:
        return None
    candidates: list[float] = []
    for pattern in _SALARY_PATTERNS:
        for match in pattern.finditer(text):
            raw = match.group(1)
            cleaned = raw.strip().replace(" ", "").replace(",", "").rstrip(".")
            # "10.000" — точка как разделитель тысяч (часто в Telegram), не дробь
            if re.fullmatch(r"\d{1,3}(\.\d{3})+", cleaned):
                cleaned = cleaned.replace(".", "")
            # Отсекаем то, что похоже на дату/телефон, а не деньги
            try:
                value = float(cleaned)
            except ValueError:
                continue
            # Явно мусорные значения (например, год "2024") отбрасываем —
            # зарплата капитана не бывает < 1000 или > 100000 в месяц.
            if 1000 <= value <= 100000:
                candidates.append(value)
    if not candidates:
        return None
    return max(candidates)


def matches_any(text: str, keywords: list[str]) -> bool:
    """True, если хотя бы одно ключевое слово встречается в тексте как отдельное
    слово/фраза (регистронезависимо)."""
    if not text:
        return False
    lowered = text.lower()
    for kw in keywords:
        kw = kw.lower().strip()
        if not kw:
            continue
        if kw.endswith("*"):
            # "балкер*" — основа слова + любое окончание (балкер, балкере, балкеры)
            if re.search(rf"\b{re.escape(kw[:-1])}\w*", lowered):
                return True
        elif " " in kw:
            if kw in lowered:
                return True
        else:
            if re.search(rf"\b{re.escape(kw)}\b", lowered):
                return True
    return False


def _phrase_regex(phrase: str) -> str:
    """'помощник* капитан*' -> regex: слова через пробелы, '*' = любое окончание."""
    parts = []
    for w in phrase.lower().split():
        parts.append(re.escape(w[:-1]) + r"\w*" if w.endswith("*") else re.escape(w) + r"\b")
    return r"\b" + r"\s+".join(parts)


def position_matches(text: str, filters: dict) -> bool:
    """Должность подходит: есть слово из filters.positions ПОСЛЕ удаления
    фраз-исключений (filters.position_exclude), например "старший помощник
    капитана" — это не капитан, хотя слово "капитана" в тексте есть."""
    cleaned = (text or "").lower()
    for phrase in filters.get("position_exclude") or []:
        cleaned = re.sub(_phrase_regex(phrase), " ", cleaned)
    return matches_any(cleaned, filters.get("positions", []))


def extract_dwt(text: str) -> int | None:
    """Пытается найти дедвейт судна в тексте, например '180,000 DWT' -> 180000."""
    if not text:
        return None
    # "180,000 DWT", "55 875 двт" — число перед единицей...
    match = re.search(r"([\d][\d,\.\s]{3,10})\s*(?:dwt|двт|тдв)", text, re.IGNORECASE)
    # ...или "DWT 55875", "DWT: 55 875" — после
    if not match:
        match = re.search(r"(?:dwt|двт|тдв)\s*[:\-–—=]?\s*([\d][\d,\.\s]{3,10})", text, re.IGNORECASE)
    if not match:
        return None
    cleaned = match.group(1).strip().replace(" ", "").replace(",", "").rstrip(".")
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", cleaned):
        cleaned = cleaned.replace(".", "")
    try:
        return int(float(cleaned))
    except ValueError:
        return None


# По умолчанию; переопределяется filters.bulk_generic_keywords в config.yaml
GENERIC_BULK_CARRIER_KEYWORDS = ["bulk carrier", "bulker", "ore carrier"]


def evaluate_vessel(text: str, filters: dict) -> tuple[bool, bool]:
    """Проверка 'Bulk Carrier Capesize и выше'. Возвращает (matched, class_unknown).

    Правила:
    1. Явное упоминание класса (Capesize/Newcastlemax/VLOC/VLBC/...) из
       filters.vessel_types -> подходит, класс известен.
    2. Иначе, если в тексте есть просто "Bulk Carrier" / "Bulker" /
       "Ore Carrier" (без уточнения класса):
         a) указан DWT и он >= dwt_min -> подходит, класс известен (по DWT);
         b) указан DWT и он < dwt_min -> НЕ подходит (слишком маленькое судно);
         c) DWT в карточке вообще не указан -> подходит, но класс/DWT НЕИЗВЕСТНЫ
            (class_unknown=True) — письмо должно это явно пометить, чтобы
            получатель проверил вручную.
    3. Иначе (не Bulk Carrier вовсе) -> не подходит.
    """
    vessel_types = filters.get("vessel_types", [])
    if matches_any(text, vessel_types):
        return True, False

    if matches_any(text, filters.get("bulk_generic_keywords") or GENERIC_BULK_CARRIER_KEYWORDS):
        dwt_min = filters.get("dwt_min")
        dwt = extract_dwt(text)
        if dwt is not None:
            if dwt_min and dwt >= dwt_min:
                return True, False
            return False, False
        # DWT/класс не указаны вовсе — пропускаем с пометкой "проверить вручную"
        return True, True

    return False, False


def vessel_matches(text: str, filters: dict) -> bool:
    """Обратная совместимость: только да/нет, без пометки о неизвестном классе."""
    matched, _ = evaluate_vessel(text, filters)
    return matched


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


# ---------------------------------------------------------------------------
# Generic HTML "job card" scraper — используется как основа для парсеров
# сайтов с server-rendered HTML, у которых нет публичного API.
#
# Стратегия: ищем на странице все <a href="..."> ссылки, чей путь похож на
# ссылку на вакансию (совпадает с href_patterns), затем поднимаемся вверх по
# DOM до ближайшего "карточного" контейнера (article/li/div с разумным
# количеством текста) и берём текст этого контейнера целиком — из него потом
# regex-ами вытаскиваем зарплату/тип судна/должность. Это менее точно, чем
# ручные CSS-селекторы под конкретную вёрстку, но переживает мелкие изменения
# HTML лучше, чем жёстко прибитые классы.
# ---------------------------------------------------------------------------

from bs4 import BeautifulSoup, Tag  # noqa: E402  (после того как re/requests уже импортированы)


def find_job_links(soup: BeautifulSoup, href_patterns: list[str]) -> list[Tag]:
    links = []
    seen_hrefs = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Ссылки пагинации (/p2/, ?page=2, /page/2) — не вакансии
        if re.search(r"(/p\d+/?$|[?&]page=\d+|/page/\d+)", href.lower()):
            continue
        # Паттерн "re:..." — регулярное выражение, иначе — подстрока
        if any(
            re.search(p[3:], href, re.IGNORECASE) if p.startswith("re:") else p in href.lower()
            for p in href_patterns
        ):
            if href in seen_hrefs:
                continue
            seen_hrefs.add(href)
            links.append(a)
    return links


def nearest_card(a_tag: Tag, job_hrefs: set[str] | None = None, max_up: int = 8) -> Tag:
    """Карточка вакансии = НАИМЕНЬШИЙ контейнер вокруг ссылки, в котором ещё
    нет ссылок на ДРУГИЕ вакансии.

    Поднимаемся от <a> вверх, пока родитель содержит ссылку только на эту же
    вакансию. Как только родитель захватывает вторую вакансию (строку таблицы
    соседа, соседнюю карточку) — останавливаемся. Раньше брался самый большой
    контейнер до 2000 символов, и на UkrCrewing им оказывалась вся таблица:
    слово "Master" из одной строки приписывалось всем 30 вакансиям страницы.
    """
    own = a_tag.get("href")
    node = a_tag
    for _ in range(max_up):
        parent = node.parent
        if parent is None or parent.name in ("body", "html", "[document]"):
            break
        if job_hrefs is not None:
            hrefs_inside = {
                x.get("href") for x in parent.find_all("a", href=True) if x.get("href") in job_hrefs
            }
            if hrefs_inside - {own}:
                break  # родитель уже содержит другую вакансию
        if len(clean_text(parent.get_text(" "))) > 1500:
            break
        node = parent
    return node


def url_slug_words(url: str) -> str:
    """'https://x.com/jobs/abc-bulk-carriers-master-123/' -> 'jobs abc bulk carriers master 123'"""
    from urllib.parse import urlparse
    path = urlparse(url).path
    return re.sub(r"[-_/]+", " ", path).strip()


def posted_days_ago(text: str) -> int | None:
    """Возраст объявления, если в тексте есть 'Posted: 170 days ago' /
    '3 дня назад' / 'today'. None — если возраст не указан."""
    t = (text or "").lower()
    if re.search(r"\b(today|yesterday|сегодня|вчера|hours? ago|час\w* назад)\b", t):
        return 0
    m = re.search(r"(\d+)\s*(day|days|дн\w*|день)\s*(ago|назад)", t)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*(week|weeks|недел\w*)\s*(ago|назад)", t)
    if m:
        return int(m.group(1)) * 7
    m = re.search(r"(\d+)\s*(month|months|месяц\w*)\s*(ago|назад)", t)
    if m:
        return int(m.group(1)) * 30
    return None


def absolute_url(base_url: str, href: str) -> str:
    from urllib.parse import urljoin
    return urljoin(base_url, href)


def generic_html_job_scrape(
    source: str,
    listing_url: str | list[str],
    href_patterns: list[str],
    config: dict,
    title_hint_words: list[str] | None = None,
) -> list[Vacancy]:
    """Общий сценарий для сайтов без публичного API: скачать страницу(ы)
    листинга, найти карточки вакансий по ссылкам, вернуть список Vacancy.

    listing_url: один URL или список URL (несколько страниц пагинации /
    отфильтрованные разделы). Сбой одной страницы не мешает остальным;
    одинаковые вакансии с разных страниц склеиваются по ID.

    title_hint_words: если задано, берём как заголовок первую строку текста
    карточки, содержащую одно из этих слов (напр. ["master", "captain"]) —
    так надёжнее, чем просто текст ссылки, который часто это просто "Apply".
    """
    urls = [listing_url] if isinstance(listing_url, str) else list(listing_url)
    result: dict[str, Vacancy] = {}
    errors = 0
    for page_url in urls:
        try:
            for v in _scrape_one_page(source, page_url, href_patterns, config, title_hint_words):
                result.setdefault(v.id, v)
        except Exception as exc:  # noqa: BLE001 — одна страница не должна валить источник
            errors += 1
            logger.warning("[%s] Страница %s не загрузилась: %s", source, page_url, exc)
    if errors == len(urls):
        # Все страницы упали — пусть это будет видно как ошибка источника
        raise RuntimeError(f"[{source}] ни одна из {len(urls)} страниц листинга не загрузилась")
    return list(result.values())


def _scrape_one_page(
    source: str,
    listing_url: str,
    href_patterns: list[str],
    config: dict,
    title_hint_words: list[str] | None,
) -> list[Vacancy]:
    return parse_listing_html(
        source, listing_url, fetch_html(listing_url, config), href_patterns, title_hint_words
    )


def parse_listing_html(
    source: str,
    listing_url: str,
    html: str,
    href_patterns: list[str],
    title_hint_words: list[str] | None = None,
) -> list[Vacancy]:
    """Разбор уже загруженного HTML листинга (без сетевых запросов)."""
    soup = BeautifulSoup(html, "html.parser")
    links = find_job_links(soup, href_patterns)
    job_hrefs = {a.get("href") for a in links}

    if not links:
        logger.warning(
            "[%s] На странице %s не найдено ни одной ссылки на вакансию по паттернам %s. "
            "Возможно сайт рендерит список через JS/API, либо изменилась вёрстка — "
            "см. README, раздел 'Диагностика парсера'.",
            source, listing_url, href_patterns,
        )
        return []

    vacancies: list[Vacancy] = []
    for a in links:
        card = nearest_card(a, job_hrefs)
        card_text = clean_text(card.get_text(" "))
        if len(card_text) < 15:
            continue

        title = clean_text(a.get_text(" "))
        if title_hint_words:
            for line in card.get_text("\n").split("\n"):
                line_clean = clean_text(line)
                if line_clean and matches_any(line_clean, title_hint_words):
                    title = line_clean
                    break
        if not title:
            title = card_text[:80]

        url = absolute_url(listing_url, a["href"])
        salary = parse_salary_usd(card_text)
        salary_match = re.search(
            r"([^.]{0,15}(?:usd|us\$|\$)[^.]{0,25})", card_text, re.IGNORECASE
        )

        vacancies.append(
            Vacancy(
                source=source,
                title=title,
                url=url,
                salary_raw=clean_text(salary_match.group(1)) if salary_match else "",
                salary_usd_month=salary,
                raw_text=card_text,
                # Полный текст карточки + слова из адреса ссылки: у Martide и
                # Maritime Bell тип судна часто есть только в URL
                # (".../bulk-carriers-master-1778...").
                vessel_type=card_text + " " + url_slug_words(url),
            )
        )

    if not vacancies:
        logger.warning(
            "[%s] Найдены ссылки на вакансии (%d шт.), но не удалось собрать ни одной карточки "
            "с достаточным текстом — вероятно верстка сильно отличается от ожидаемой.",
            source, len(links),
        )

    return vacancies
