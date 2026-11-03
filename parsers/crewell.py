"""
Источник: Crewell.net — https://crewell.net/en/vacancies/

Статус проверки: НЕ подтверждено вживую (см. README, "Диагностика парсера").
"""
from __future__ import annotations

import logging

from .base import Vacancy, generic_html_job_scrape

logger = logging.getLogger("maritime_job_agent")

SOURCE = "crewell"
# Пагинация ?page=N (проверено 2026-11-03), 20 вакансий на странице.
LISTING_URL = [f"https://crewell.net/en/vacancies/?page={i}" for i in range(1, 6)]
HREF_PATTERNS = [r"re:/en/vacancies/\d+"]


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
