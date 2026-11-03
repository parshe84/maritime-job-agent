"""
Источник: OSM Thome (крупный судоменеджер) — https://jobs.osmthome.com/jobs

Проверено 2026-11-03: без логина, пагинация ?page=N, ссылка
/jobs/<id>/<slug>, тип судна в карточке ("Bulkcarrier").
"""
from __future__ import annotations

import logging

from .base import Vacancy, generic_html_job_scrape

logger = logging.getLogger("maritime_job_agent")

SOURCE = "osm_thome"
LISTING_URL = [f"https://jobs.osmthome.com/jobs?page={i}" for i in range(1, 4)]
HREF_PATTERNS = [r"re:/jobs/\d+/"]


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
