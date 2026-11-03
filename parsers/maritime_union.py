"""
Источник: Maritime Union — https://maritime-union.com/jobs

Проверено 2026-11-03: открывается без логина, 30 вакансий на странице,
пагинация ?p=N, ссылка на вакансию /job/<id>.
"""
from __future__ import annotations

import logging

from .base import Vacancy, generic_html_job_scrape

logger = logging.getLogger("maritime_job_agent")

SOURCE = "maritime_union"
LISTING_URL = [f"https://maritime-union.com/jobs?p={i}" for i in range(1, 6)]
HREF_PATTERNS = [r"re:/job/\d+"]


def fetch_vacancies(config: dict) -> list[Vacancy]:
    try:
        return generic_html_job_scrape(
            source=SOURCE,
            listing_url=LISTING_URL,
            href_patterns=HREF_PATTERNS,
            config=config,
            title_hint_words=["master", "captain", "капитан"],
        )
    except Exception:
        logger.exception("[%s] Не удалось получить вакансии", SOURCE)
        return []
