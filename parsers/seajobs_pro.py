"""
Источник: SeaJobs.pro — https://seajobs.pro/

Проверено 2026-11-03: /jobs/rank/master/bulk-carrier — Master на балкерах,
/jobs/vessel/bulk-carrier — все балкерные вакансии (~112). Пагинации нет.
Ссылка на вакансию: /jobs/<slug>-<uuid>.
"""
from __future__ import annotations

import logging

from .base import Vacancy, generic_html_job_scrape

logger = logging.getLogger("maritime_job_agent")

SOURCE = "seajobs_pro"
LISTING_URL = [
    "https://seajobs.pro/jobs/rank/master/bulk-carrier",
    "https://seajobs.pro/jobs/vessel/bulk-carrier",
]
HREF_PATTERNS = [r"re:/jobs/[a-z0-9-]+-[0-9a-f]{8}-[0-9a-f]{4}-"]


def fetch_vacancies(config: dict) -> list[Vacancy]:
    try:
        return generic_html_job_scrape(
            source=SOURCE,
            listing_url=LISTING_URL,
            href_patterns=HREF_PATTERNS,
            config=config,
            title_hint_words=["master", "captain", "mst"],
        )
    except Exception:
        logger.exception("[%s] Не удалось получить вакансии", SOURCE)
        return []
