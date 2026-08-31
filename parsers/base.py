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

    @property
    def id(self) -> str:
        """Стабильный уникальный ID для дедупликации (по ссылке)."""
        key = self.url.strip().rstrip("/").lower()
        if not key:
            key = f"{self.source}|{self.title}|{self.vessel_type}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


DEFAULT_HEADERS_TEMPLATE = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
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
            cleaned = raw.replace(" ", "").replace(",", "")
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
        if " " in kw:
            if kw in lowered:
                return True
        else:
            if re.search(rf"\b{re.escape(kw)}\b", lowered):
                return True
    return False


def extract_dwt(text: str) -> int | None:
    """Пытается найти дедвейт судна в тексте, например '180,000 DWT' -> 180000."""
    if not text:
        return None
    match = re.search(r"([\d][\d,\.\s]{3,10})\s*dwt", text, re.IGNORECASE)
    if not match:
        return None
    cleaned = match.group(1).replace(" ", "").replace(",", "")
    try:
        return int(float(cleaned))
    except ValueError:
        return None


def vessel_matches(text: str, filters: dict) -> bool:
    """Проверка 'Bulk Carrier Capesize и выше' по названию класса ИЛИ по DWT."""
    vessel_types = filters.get("vessel_types", [])
    if matches_any(text, vessel_types):
        return True
    dwt_min = filters.get("dwt_min")
    if dwt_min:
        dwt = extract_dwt(text)
        if dwt is not None and dwt >= dwt_min and matches_any(text, ["bulk carrier", "bulker", "ore carrier"]):
            return True
    return False


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
        if any(p in href.lower() for p in href_patterns):
            if href in seen_hrefs:
                continue
            seen_hrefs.add(href)
            links.append(a)
    return links


def nearest_card(a_tag: Tag, max_up: int = 5) -> Tag:
    """Поднимается от <a> вверх, пока текст контейнера не станет 'достаточным'
    карточкой (не слишком коротким и не всей страницей целиком)."""
    node = a_tag
    best = a_tag
    for _ in range(max_up):
        if node.parent is None:
            break
        node = node.parent
        text_len = len(clean_text(node.get_text(" ")))
        if 20 <= text_len <= 2000:
            best = node
        if text_len > 2000:
            break
    return best


def absolute_url(base_url: str, href: str) -> str:
    from urllib.parse import urljoin
    return urljoin(base_url, href)


def generic_html_job_scrape(
    source: str,
    listing_url: str,
    href_patterns: list[str],
    config: dict,
    title_hint_words: list[str] | None = None,
) -> list[Vacancy]:
    """Общий сценарий для сайтов без публичного API: скачать страницу листинга,
    найти карточки вакансий по ссылкам, вернуть список Vacancy.

    title_hint_words: если задано, берём как заголовок первую строку текста
    карточки, содержащую одно из этих слов (напр. ["master", "captain"]) —
    так надёжнее, чем просто текст ссылки, который часто это просто "Apply".
    """
    resp = http_get(listing_url, config)
    soup = BeautifulSoup(resp.text, "html.parser")
    links = find_job_links(soup, href_patterns)

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
        card = nearest_card(a)
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
                vessel_type=card_text,  # оставляем полный текст — vessel_matches() сам найдёт ключевые слова
            )
        )

    if not vacancies:
        logger.warning(
            "[%s] Найдены ссылки на вакансии (%d шт.), но не удалось собрать ни одной карточки "
            "с достаточным текстом — вероятно верстка сильно отличается от ожидаемой.",
            source, len(links),
        )

    return vacancies
