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
# Пагинация путём /en/vacancy/pN/ (проверено 2026-11-03: 1700+ вакансий,
# 30 на странице, новые сверху). Берём 10 первых страниц = 300 самых свежих.
LISTING_URL = [f"https://ukrcrewing.com.ua/en/vacancy/p{i}/" for i in range(1, 11)]
HREF_PATTERNS = [r"re:/en/vacancy/\d+"]


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
