"""
Источник: UkrCrewing — https://ukrcrewing.com.ua/en/vacancy

URL найден через веб-поиск (в этой сессии не было прямого доступа для
проверки вживую при добавлении источника) — требует подтверждения через
workflow_dispatch на GitHub Actions, как и остальные источники (см. README,
раздел "Диагностика парсера").
"""
from __future__ import annotations

import logging

from .base import Vacancy, generic_html_job_scrape

logger = logging.getLogger("maritime_job_agent")

SOURCE = "ukrcrewing"
LISTING_URL = "https://ukrcrewing.com.ua/en/vacancy"
HREF_PATTERNS = ["/vacancy/", "/vacancies/", "/en/vacancy"]


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
