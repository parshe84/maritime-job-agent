"""
Источник: Columbia Shipmanagement — страница морских вакансий.

URL найден через веб-поиск (в песочнице сборки не было доступа для проверки
вживую): https://columbia-shipmanagement.com/sea-job-opportunities/

Внимание: у многих крюинговых порталов такого типа список вакансий рендерится
через встроенный crew-portal/iframe (иногда с формой логина), что для
простого HTTP GET будет выглядеть как пустая страница без ссылок. Если при
реальном прогоне окажется так — это будет ясно из лога ("не найдено ни одной
ссылки"), и тогда нужно либо найти отдельный публичный API этого виджета,
либо использовать headless-браузер (Playwright) вместо requests — см. README,
раздел "Если сайт защищён от простого скрапинга".

Статус проверки: НЕ подтверждено вживую (см. README, "Диагностика парсера").
"""
from __future__ import annotations

import logging

from .base import Vacancy, generic_html_job_scrape

logger = logging.getLogger("maritime_job_agent")

SOURCE = "columbia_shipmanagement"
LISTING_URL = "https://columbia-shipmanagement.com/sea-job-opportunities/"
HREF_PATTERNS = ["/job", "/vacanc", "/career"]


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
