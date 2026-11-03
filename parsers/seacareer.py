"""
Источник: SeaCareer — https://seacareer.com

Проверено 2026-11-03: разделы /master-sdpo-jobs/ и /deck-officer-jobs/
отдаются сервером, пагинация /N/, ссылка на вакансию /i<id>/<slug>/,
тип судна — после даты ("October 27, 2026 - PSV").
"""
from __future__ import annotations

import logging

from .base import Vacancy, generic_html_job_scrape

logger = logging.getLogger("maritime_job_agent")

SOURCE = "seacareer"
LISTING_URL = [
    "https://www.seacareer.com/master-sdpo-jobs/",
    "https://www.seacareer.com/master-sdpo-jobs/2/",
    "https://www.seacareer.com/master-sdpo-jobs/3/",
    "https://www.seacareer.com/deck-officer-jobs/",
    "https://www.seacareer.com/deck-officer-jobs/2/",
]
HREF_PATTERNS = [r"re:/i\d+/"]


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
