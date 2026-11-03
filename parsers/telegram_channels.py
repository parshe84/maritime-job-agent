"""
Источник: публичные Telegram-каналы с вакансиями моряков.

Читаются через открытый веб-просмотр https://t.me/s/<канал> — без
аккаунта, логина и API-ключей (проверено 2026-11-03). Каждый пост канала =
одна "вакансия" (иногда в посте несколько позиций сразу — тогда фильтр
сработает, если среди них есть подходящая).

Список каналов — в config.yaml, ключ telegram_channels. Чтобы добавить
канал, допишите туда его имя (часть ссылки после t.me/), код менять не надо.
Закрытые каналы/группы так не читаются — для них нужен вход в Telegram.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

from .base import Vacancy, clean_text, fetch_html, matches_any, parse_salary_usd, polite_sleep

logger = logging.getLogger("maritime_job_agent")

SOURCE = "telegram"
PAGES_PER_CHANNEL = 2  # ~20 постов на странице; запуск каждый час — с запасом

# Строка похожа на "должность [- на] судно" — для распознавания постов-сборников
RANK_LINE_RE = re.compile(
    r"\b(master|captain|mst|chief\s+off\w*|c/o|chief\s+eng\w*|c/e|2nd|3rd|2/o|3/o|2/e|3/e|"
    r"second|third|bosun|ab|oiler|fitter|cook|eto|electrician|motorman|wiper|"
    r"капитан\w*|старпом\w*|помощник\w*|механик\w*|боцман\w*|матрос\w*|моторист\w*|"
    r"повар\w*|электромеханик\w*)\b",
    re.IGNORECASE,
)
VESSEL_WORD_RE = re.compile(
    r"\b(tanker|bulk\w*|container\w*|lng|lpg|cargo|ro-?ro|psv|ahts|vessel|ship|carrier|"
    r"reefer|mpp|coaster|tug|dredger|танкер\w*|балкер\w*|сухогруз\w*|контейнеровоз\w*|"
    r"судн\w*|газовоз\w*|рефрижератор\w*|буксир\w*)\b",
    re.IGNORECASE,
)
MASTER_RE = re.compile(r"\b(master|captain|mst|капитан\w*)\b", re.IGNORECASE)
ASSISTANT_RE = re.compile(r"\bпомощник\w*\s+капитан\w*|\bstaff\s+captain\b", re.IGNORECASE)


def _parse_page(channel: str, html: str, max_age_days: int = 10) -> tuple[list[Vacancy], int | None]:
    soup = BeautifulSoup(html, "html.parser")
    vacancies: list[Vacancy] = []
    min_id: int | None = None
    for msg in soup.select("div.tgme_widget_message[data-post]"):
        post = msg["data-post"]  # "marinejobz/194138"
        m = re.search(r"/(\d+)$", post)
        if m:
            pid = int(m.group(1))
            min_id = pid if min_id is None else min(min_id, pid)
        text_div = msg.select_one(".tgme_widget_message_text")
        if not text_div:
            continue  # пост без текста (только фото/стикер)
        text = clean_text(text_div.get_text(" "))
        if len(text) < 15:
            continue
        lines = [clean_text(x) for x in text_div.get_text("\n").split("\n") if clean_text(x)]
        # Пост-сборник ("Master - tanker / C/O - bulk / 2/E - container ..."):
        # проверяем только строки с капитаном, иначе "Master" из одной строки
        # и "bulk" из другой дали бы ложное совпадение.
        if sum(1 for ln in lines if RANK_LINE_RE.search(ln) and VESSEL_WORD_RE.search(ln)) >= 3:
            master_lines = [
                ln for ln in lines
                if MASTER_RE.search(ln) and not ASSISTANT_RE.search(ln)
            ]
            if not master_lines:
                continue
            text = " | ".join(master_lines)
        # Заголовок — строка с должностью капитана, иначе первая строка поста
        first_line = next(
            (ln for ln in lines if matches_any(ln, ["master", "captain", "капитан*"])),
            lines[0] if lines else text[:80],
        )
        posted = msg.select_one("time[datetime]")
        if posted and max_age_days:
            try:
                when = datetime.fromisoformat(posted["datetime"])
                if datetime.now(timezone.utc) - when > timedelta(days=max_age_days):
                    continue  # старый пост: вакансия, скорее всего, уже закрыта
            except ValueError:
                pass
        vacancies.append(
            Vacancy(
                source=f"telegram:{channel}",
                title=first_line[:120],
                url=f"https://t.me/{post}",
                salary_usd_month=parse_salary_usd(text),
                raw_text=text + (f" (опубликовано {posted['datetime'][:10]})" if posted else ""),
                vessel_type=text,
            )
        )
    return vacancies, min_id


def fetch_vacancies(config: dict) -> list[Vacancy]:
    channels = config.get("telegram_channels") or []
    result: list[Vacancy] = []
    for channel in channels:
        url = f"https://t.me/s/{channel}"
        got = 0
        try:
            for _ in range(PAGES_PER_CHANNEL):
                vacancies, min_id = _parse_page(
                    channel, fetch_html(url, config), config.get("telegram_max_age_days", 10)
                )
                result.extend(vacancies)
                got += len(vacancies)
                if not min_id:
                    break
                url = f"https://t.me/s/{channel}?before={min_id}"
                polite_sleep(config)
            if got == 0:
                logger.warning("[telegram:%s] постов с текстом не найдено — канал закрыт или переименован?", channel)
            logger.info("[telegram:%s] постов: %d", channel, got)
        except Exception:
            logger.exception("[telegram:%s] не удалось прочитать канал", channel)
    return result
