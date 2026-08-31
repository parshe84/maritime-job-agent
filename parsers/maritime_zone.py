"""
Источник: Maritime-Zone — https://maritime-zone.com/en

У Maritime-Zone нет единой страницы "все вакансии" в духе job-board — сайт в
основном каталог судоходных/crewing компаний, а вакансии живут на страницах
конкретных компаний (напр. maritime-zone.com/en/crewing/<id>-<company>).
Поэтому в качестве листинга берём их собственный раздел поиска вакансий,
если он существует ("/en/vacancies" или аналог) — если 404/редирект,
парсер залогирует это и вернёт [].

Статус проверки: НЕ подтверждено вживую (см. README, "Диагностика парсера").
"""
from __future__ import annotations

import logging

from .base import Vacancy, generic_html_job_scrape

logger = logging.getLogger("maritime_job_agent")

SOURCE = "maritime_zone"
LISTING_URL = "https://maritime-zone.com/en/vacancies"
HREF_PATTERNS = ["/vacanc", "/jobs/"]


def fetch_vacancies(config: dict) -> list[Vacancy]:
    try:
        return generic_html_job_scrape(
            source=SOURCE,
            listing_url=LISTING_URL,
            href_patterns=HREF_PATTERNS,
            config=config,
            title_hint_words=["master", "captain"],
        )
    except Exception:
        logger.exception("[%s] Не удалось получить вакансии", SOURCE)
        return []
