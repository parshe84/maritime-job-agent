"""
Источник: JobMarineMan — https://jobmarineman.com

Статус (2026-11-03): раздел /vacancies/ отдаёт 403 и простому HTTP-клиенту,
и headless-браузеру из GitHub Actions (анти-бот защита). Главная страница и
портал моряка https://seafarer.jobmarineman.com/login/ при этом открываются.

Порядок попыток:
1. Без логина: раздел "Master на Bulk Carrier" и общий список (requests,
   при 403 — headless-браузер, см. fetch_html в base.py).
2. Если ничего не получено И заданы переменные окружения JMM_LOGIN /
   JMM_PASSWORD (GitHub Secrets) — вход через портал моряка в браузере и
   повторная загрузка тех же страниц в залогиненной сессии.

Логин и пароль берутся ТОЛЬКО из окружения и никогда не пишутся в лог.
"""
from __future__ import annotations

import logging
import os

from .base import Vacancy, generic_html_job_scrape, parse_listing_html

logger = logging.getLogger("maritime_job_agent")

SOURCE = "jobmarineman"
LOGIN_URL = "https://seafarer.jobmarineman.com/login/"
LISTING_URL = [
    # Раздел из Telegram-дайджеста JobMarineMan: Master + Bulk Carrier
    "https://jobmarineman.com/vacancies/r-master-1_v-bulk-carrier-25",
    "https://jobmarineman.com/vacancies/",
    "https://jobmarineman.com/",
]
# Конкретная вакансия: /vacancy/2030/ (не категории /vacancies/r-...)
HREF_PATTERNS = [r"re:/vacancy/\d+"]
TITLE_HINTS = ["master", "captain", "капитан"]


def _fetch_with_login(config: dict) -> list[Vacancy]:
    login = os.environ.get("JMM_LOGIN")
    password = os.environ.get("JMM_PASSWORD")
    if not login or not password:
        logger.info("[%s] JMM_LOGIN/JMM_PASSWORD не заданы — вход не выполняется", SOURCE)
        return []

    from playwright.sync_api import sync_playwright

    timeout_ms = int(config.get("network", {}).get("timeout_seconds", 25) * 2000)
    result: dict[str, Vacancy] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_context(
                user_agent=config.get("network", {}).get("user_agent"), locale="en-US"
            ).new_page()
            resp = page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=timeout_ms)
            logger.info("[%s] страница входа: HTTP %s", SOURCE, resp.status if resp else "?")
            if resp is not None and resp.status in (403, 429, 503):
                # Сайт блокирует IP-адреса GitHub Actions целиком (проверено
                # 2026-11-03) — до формы входа не дойти, логин не поможет.
                logger.warning("[%s] сайт блокирует серверы GitHub (HTTP %s) — источник недоступен", SOURCE, resp.status)
                return []
            page.wait_for_timeout(3000)
            page.locator("input[type=email], input[name*=mail i], input[name*=login i]").first.fill(login)
            page.locator("input[type=password]").first.fill(password)
            page.locator("input[type=password]").first.press("Enter")
            page.wait_for_timeout(6000)
            still_on_login = "login" in page.url.lower()
            logger.info(
                "[%s] вход %s (адрес после входа: %s)",
                SOURCE, "НЕ удался" if still_on_login else "выполнен", page.url.split("?")[0],
            )
            # Портал моряка мог сам показать список вакансий — разберём и его
            pages = [(page.url, page.content())]
            for url in LISTING_URL:
                try:
                    r = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                    page.wait_for_timeout(4000)
                    logger.info("[%s] %s после входа: HTTP %s", SOURCE, url, r.status if r else "?")
                    pages.append((url, page.content()))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("[%s] %s после входа не загрузилась: %s", SOURCE, url, exc)
            for url, html in pages:
                for v in parse_listing_html(SOURCE, url, html, HREF_PATTERNS, TITLE_HINTS):
                    result.setdefault(v.id, v)
        finally:
            browser.close()
    return list(result.values())


def fetch_vacancies(config: dict) -> list[Vacancy]:
    vacancies: list[Vacancy] = []
    try:
        vacancies = generic_html_job_scrape(
            source=SOURCE,
            listing_url=LISTING_URL,
            href_patterns=HREF_PATTERNS,
            config=config,
            title_hint_words=TITLE_HINTS,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] без логина не получилось: %s", SOURCE, exc)
    if vacancies:
        return vacancies
    try:
        return _fetch_with_login(config)
    except Exception:
        logger.exception("[%s] не удалось получить вакансии через вход на портал", SOURCE)
        return []
