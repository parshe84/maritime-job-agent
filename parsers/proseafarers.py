"""
Источник: ProSeafarers — https://proseafarers.com/

Проверено 2026-11-03: раздел /jobs/master/ отдаётся сервером (главная — JS),
ссылка на вакансию /jobs/<slug>-<8 hex>/.
"""
from __future__ import annotations

import logging

from .base import Vacancy, generic_html_job_scrape

logger = logging.getLogger("maritime_job_agent")

SOURCE = "proseafarers"
LISTING_URL = ["https://proseafarers.com/jobs/master/"]
HREF_PATTERNS = [r"re:/jobs/[a-z0-9-]+-[0-9a-f]{8}/?$"]


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
