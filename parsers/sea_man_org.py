"""
Источник: Sea-Man.org (crew) — https://crew.sea-man.org/

Проверено 2026-11-03: страница /vacancies рендерится JS, но главная отдаёт
сервером 6 последних вакансий; ссылка /vac/<id>/.
"""
from __future__ import annotations

import logging

from .base import Vacancy, generic_html_job_scrape

logger = logging.getLogger("maritime_job_agent")

SOURCE = "sea_man_org"
LISTING_URL = ["https://crew.sea-man.org/"]
HREF_PATTERNS = [r"re:/vac/\d+"]


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
