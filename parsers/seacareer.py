"""
Источник: SeaCareer — https://seacareer.com

Статус проверки: НЕ подтверждено вживую (см. README, "Диагностика парсера").
"""
from __future__ import annotations

import logging

from .base import Vacancy, generic_html_job_scrape

logger = logging.getLogger("maritime_job_agent")

SOURCE = "seacareer"
# Подтверждено прогоном через GitHub Actions 2026-08-31: /vacancies/ -> 404,
# правильный путь - /jobs/sea-career/.
LISTING_URL = "https://www.seacareer.com/jobs/sea-career/"
HREF_PATTERNS = ["/vacanc", "/job"]


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
