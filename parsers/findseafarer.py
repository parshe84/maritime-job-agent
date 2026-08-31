"""
Источник: FindSeafarer — https://findseafarer.com

Статус проверки: НЕ подтверждено вживую (см. README, "Диагностика парсера").
"""
from __future__ import annotations

import logging

from .base import Vacancy, generic_html_job_scrape

logger = logging.getLogger("maritime_job_agent")

SOURCE = "findseafarer"
# Подтверждено прогоном через GitHub Actions 2026-08-31: /jobs -> 404.
# Веб-поиск не дал точного пути к листингу вакансий (сайт мог не
# индексировать этот раздел, либо список подгружается через JS/API).
# Временно берём главную страницу — если после реального прогона источник
# снова вернёт 0 без явной причины, откройте findseafarer.com в браузере,
# найдите реальный путь до листинга (или JSON-эндпоинт в DevTools -> Network)
# и обновите LISTING_URL/HREF_PATTERNS здесь.
LISTING_URL = "https://findseafarer.com/"
HREF_PATTERNS = ["/job", "/vacanc", "/position"]


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
