"""
Источник: Oldendorff Carriers — карьерная страница для моряков (Sea Careers).

URL найден через веб-поиск (в песочнице сборки не было доступа для проверки
вживую): https://www.oldendorff.com/teamwork/sea-careers

Многие crewing-разделы судоходных компаний — это просто форма/описание без
списка конкретных открытых вакансий (найм идёт через собственную crew
database, а не публичный список позиций). Если так — generic-скрапер не
найдёт ссылок на вакансии и вернёт [] с понятным предупреждением в логе,
это не баг, а корректное поведение (нечего парсить).

Статус проверки: НЕ подтверждено вживую (см. README, "Диагностика парсера").
"""
from __future__ import annotations

import logging

from .base import Vacancy, generic_html_job_scrape

logger = logging.getLogger("maritime_job_agent")

SOURCE = "oldendorff"
LISTING_URL = "https://www.oldendorff.com/teamwork/sea-careers"
HREF_PATTERNS = ["/jobs/", "/vacanc", "/careers", "sea-careers"]


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
