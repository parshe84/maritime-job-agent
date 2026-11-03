"""
Источник: Martide — https://www.martide.com/en/jobs

Примечание: Martide исторически отдаёт список вакансий как server-rendered
HTML с карточками-ссылками на /en/jobs/<slug>. Если сайт перешёл на
полностью JS-рендеринг (SPA без HTML в первом ответе), эта функция вернёт
пустой список и залогирует предупреждение — тогда см. README, раздел
"Диагностика парсера" (там же — как проверить через network-таб браузера,
не отдаёт ли сайт JSON API, который можно дёргать напрямую вместо HTML).

Статус проверки: НЕ подтверждено вживую (песочница сборки не имела доступа
в интернет) — требует прогона через GitHub Actions workflow_dispatch и
разбора логов перед тем, как считать источник рабочим.
"""
from __future__ import annotations

import logging

from .base import Vacancy, generic_html_job_scrape

logger = logging.getLogger("maritime_job_agent")

SOURCE = "martide"
# Martide фильтрует путём (проверено 2026-11-03): /en/jobs/master — все
# вакансии Master, /en/jobs/bulk-carriers/master — Master на балкерах.
# Плюс две общие страницы как подстраховка.
LISTING_URL = [
    "https://www.martide.com/en/jobs/bulk-carriers/master",
    "https://www.martide.com/en/jobs/master",
    "https://www.martide.com/en/jobs",
    "https://www.martide.com/en/jobs/page/2",
]
# Ссылка на конкретную вакансию всегда заканчивается числовым ID
HREF_PATTERNS = [r"re:/en/jobs/[a-z0-9-]+-\d+/?$"]


def fetch_vacancies(config: dict) -> list[Vacancy]:
    try:
        return generic_html_job_scrape(
            source=SOURCE,
            listing_url=LISTING_URL,
            href_patterns=HREF_PATTERNS,
            config=config,
            title_hint_words=["master", "captain", "chief", "officer", "engineer"],
        )
    except Exception:
        logger.exception("[%s] Не удалось получить вакансии", SOURCE)
        return []
