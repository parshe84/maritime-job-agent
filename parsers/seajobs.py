"""
Источник: SeaJobs.ru — https://www.seajobs.ru/ru/vacancies

Проверено 2026-11-03: открывается без логина, ~370 открытых вакансий,
новые сверху, пагинация ?page=N, ссылка на вакансию /ru/vacancy/<id>/<slug>.
"""
from __future__ import annotations

import logging

from .base import Vacancy, generic_html_job_scrape

logger = logging.getLogger("maritime_job_agent")

SOURCE = "seajobs"
LISTING_URL = [f"https://www.seajobs.ru/ru/vacancies?page={i}" for i in range(1, 6)]
HREF_PATTERNS = [r"re:/ru/vacancy/\d+"]


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
