"""
Отправка новых вакансий в Telegram через вашего личного бота.

Секреты (GitHub Secrets), только из окружения:
  TELEGRAM_BOT_TOKEN — токен бота от @BotFather ("123456:ABC-...")
  TELEGRAM_CHAT_ID   — ваш числовой chat id (куда бот пишет)

Если секреты не заданы — функция ничего не делает (Telegram выключен).
Кейпсайзы приходят первыми, отдельным сообщением с пометкой 🟢.
"""
from __future__ import annotations

import logging
import os
from html import escape

import requests

from parsers.base import Vacancy

logger = logging.getLogger("maritime_job_agent")

API = "https://api.telegram.org/bot{token}/sendMessage"
MAX_LEN = 3800  # лимит Telegram — 4096 символов на сообщение, оставляем запас


def telegram_configured() -> bool:
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"))


def _item(v: Vacancy) -> str:
    if v.salary_usd_month:
        salary = f"${v.salary_usd_month:,.0f}".replace(",", " ")
    else:
        salary = "зарплата не указана"
    lines = [
        f"<b>{escape(v.title[:100])}</b>",
        f"{escape(v.raw_text[:220])}",
        f"💰 {salary} · 📍 {escape(v.source)}",
    ]
    if v.vessel_class_unknown and not v.is_capesize:
        lines.append("⚠️ класс судна не указан — проверьте вручную")
    lines.append(f'<a href="{escape(v.url, quote=True)}">Открыть вакансию</a>')
    return "\n".join(lines)


def _messages(vacancies: list[Vacancy], config: dict) -> list[str]:
    filters = config.get("filters", {})
    cape = [v for v in vacancies if v.is_capesize]
    other = [v for v in vacancies if not v.is_capesize]
    blocks: list[tuple[str, list[Vacancy]]] = []
    if cape:
        blocks.append((f"🟢 <b>КЕЙПСАЙЗ — {len(cape)}</b> (DWT ≥ "
                       f"{filters.get('capesize_dwt_min', 170000):,} / GT ≥ "
                       f"{filters.get('capesize_gt_min', 80000):,})".replace(",", " "), cape))
    if other:
        blocks.append((f"⚓ <b>Балкеры — {len(other)}</b> (от ${filters.get('min_salary_usd')})", other))

    messages: list[str] = []
    for header, items in blocks:
        current = header
        for v in items:
            piece = "\n\n" + _item(v)
            if len(current) + len(piece) > MAX_LEN:
                messages.append(current)
                current = header + " (продолжение)"
            current += piece
        messages.append(current)
    return messages


def send_telegram(vacancies: list[Vacancy], config: dict) -> None:
    """Бросает исключение, если Telegram настроен, но отправка не удалась."""
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    for text in _messages(vacancies, config):
        resp = requests.post(
            API.format(token=token),
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            # Токен в лог не попадает: печатаем только ответ Telegram
            raise RuntimeError(f"Telegram ответил {resp.status_code}: {resp.text[:300]}")
    logger.info("Telegram: отправлено %d вакансий.", len(vacancies))
