"""
Источник: JobMarineMan — https://jobmarineman.com/vacancies/

Статус проверки (прогон через GitHub Actions 2026-08-31): URL листинга
правильный (подтверждено веб-поиском — реальные страницы вакансий вида
/vacancies/r-chief-officer-2 существуют), но сам GET на /vacancies/
возвращает 403 Forbidden уже на первом запросе — похоже на анти-бот
защиту (Cloudflare WAF/rate-limit), а не на изменение вёрстки.

Если после добавления более "браузерных" заголовков (см. base.py,
DEFAULT_HEADERS_TEMPLATE) 403 сохраняется — это подтверждённая защита от
скрапинга, и надёжной альтернативы в виде RSS у сайта не найдено. Публичный
Telegram-канал сайта (t.me/s/marineman_ltd) отдаёт HTML без JS и не защищён
Cloudflare — при необходимости можно реализовать отдельный парсер под него
как временную замену. До этого момента источник считается "нерабочим по
объективной причине" (см. README) — рекомендуется либо оставить как есть
(будет просто регулярно логировать 403 и не мешать остальным источникам),
либо выключить в config.yaml: sources.jobmarineman.enabled: false.
"""
from __future__ import annotations

import logging

from .base import Vacancy, generic_html_job_scrape

logger = logging.getLogger("maritime_job_agent")

SOURCE = "jobmarineman"
LISTING_URL = "https://jobmarineman.com/vacancies/"
HREF_PATTERNS = ["/vacancies/", "/vacancy/"]


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
