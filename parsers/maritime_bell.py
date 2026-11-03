"""
Источник: Maritime Bell — https://www.maritimebell.com/jobs/

Проверено 2026-11-03: раздел /jobs/bulk-carriers/master/ — ~109 вакансий
Master на балкерах, 50 на странице, пагинация /page/N/. Тип судна часто есть
только в адресе ссылки (".../bulk-carriers-master-1778..."). Много старых
объявлений ("Posted: 170 days ago") — их отсекает filters.max_age_days.
"""
from __future__ import annotations

import logging

from .base import Vacancy, generic_html_job_scrape

logger = logging.getLogger("maritime_job_agent")

SOURCE = "maritime_bell"
LISTING_URL = [
    "https://www.maritimebell.com/jobs/bulk-carriers/master/",
    "https://www.maritimebell.com/jobs/bulk-carriers/master/page/2/",
    "https://www.maritimebell.com/jobs/bulk-carriers/master/page/3/",
]
HREF_PATTERNS = [r"re:/jobs/[a-z0-9-]+-\d{6,}/?$"]


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
