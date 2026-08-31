"""
Источник: TURTLE — https://go-turtle.com (раздел vacancy/jobs)

Статус проверки: НЕ подтверждено вживую (см. README, "Диагностика парсера").
"""
from __future__ import annotations

import logging

from .base import Vacancy, generic_html_job_scrape

logger = logging.getLogger("maritime_job_agent")

SOURCE = "turtle"
# Подтверждено прогоном через GitHub Actions 2026-08-31: /vacancy -> 404,
# правильный путь - /vacancies (множественное число), на www.go-turtle.com.
LISTING_URL = "https://www.go-turtle.com/vacancies"
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
