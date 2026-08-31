"""
Источник: Berge Bulk — карьерная страница (морские вакансии).

URL найден через веб-поиск (в песочнице сборки не было доступа для проверки
вживую): https://www.bergebulk.com/jobs/
Альтернативная страница на случай редиректа/структуры без листинга:
https://www.bergebulk.com/careers-with-berge-bulk/careers-at-sea/

Крупные судоходные компании часто используют сторонние ATS-системы
(Workday, SmartRecruiters, iCIMS и т.п.) для карьерных страниц — если это
окажется так, generic-скрапер вернёт [] с предупреждением в логе, и тогда
самый надёжный путь — узнать, какой ATS используется (это будет видно в
логах/URL при реальном прогоне), и обращаться к его публичному API вместо
скрапинга HTML.

Статус проверки: НЕ подтверждено вживую (см. README, "Диагностика парсера").
"""
from __future__ import annotations

import logging

from .base import Vacancy, generic_html_job_scrape

logger = logging.getLogger("maritime_job_agent")

SOURCE = "berge_bulk"
LISTING_URL = "https://www.bergebulk.com/jobs/"
HREF_PATTERNS = ["/jobs/", "/vacanc", "/careers"]


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
