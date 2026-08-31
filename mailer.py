"""
Отправка email-дайджеста через Gmail SMTP.

Секреты берутся ТОЛЬКО из переменных окружения / GitHub Secrets:
  GMAIL_ADDRESS      — адрес Gmail-аккаунта, от имени которого шлём письма
  GMAIL_APP_PASSWORD — пароль приложения Gmail (НЕ обычный пароль аккаунта!)
  MAIL_TO            — (опционально) адрес получателя; если не задан,
                        письмо уходит на тот же адрес, что в GMAIL_ADDRESS

Никогда не хардкодьте эти значения в коде — см. README, раздел
"Как обновить Gmail app password".
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from parsers.base import Vacancy

logger = logging.getLogger("maritime_job_agent")

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


class MailerConfigError(RuntimeError):
    """Секреты для отправки почты не настроены."""


def _get_credentials() -> tuple[str, str, str]:
    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD")
    mail_to = os.environ.get("MAIL_TO") or gmail_address

    if not gmail_address or not gmail_password:
        raise MailerConfigError(
            "Не заданы переменные окружения GMAIL_ADDRESS / GMAIL_APP_PASSWORD. "
            "Добавьте их в GitHub Secrets репозитория (Settings -> Secrets and "
            "variables -> Actions) — см. README."
        )
    return gmail_address, gmail_password, mail_to  # type: ignore[return-value]


def build_digest_html(vacancies: list[Vacancy], config: dict) -> str:
    filters = config.get("filters", {})
    min_salary = filters.get("min_salary_usd")

    rows = []
    for v in vacancies:
        salary_note = v.salary_raw or "не указана"
        if v.salary_usd_month is None and filters.get("include_unknown_salary", True):
            salary_note = f"{salary_note} — [зарплата не указана, уточнить у работодателя]"
        rows.append(
            f"""
            <tr>
              <td style="padding:8px;border-bottom:1px solid #ddd;"><b>{v.title}</b><br>
                  <span style="color:#666;font-size:12px;">{v.source}</span></td>
              <td style="padding:8px;border-bottom:1px solid #ddd;">{v.vessel_type[:200]}</td>
              <td style="padding:8px;border-bottom:1px solid #ddd;">{salary_note}</td>
              <td style="padding:8px;border-bottom:1px solid #ddd;">
                  <a href="{v.url}">Открыть вакансию</a></td>
            </tr>
            """
        )

    return f"""
    <html>
    <body style="font-family:Arial,sans-serif;">
      <h2>Новые вакансии Captain/Master — Bulk Carrier Capesize+ (от ${min_salary}/мес)</h2>
      <p>Найдено новых подходящих вакансий: <b>{len(vacancies)}</b></p>
      <table style="border-collapse:collapse;width:100%;">
        <thead>
          <tr style="background:#f0f0f0;text-align:left;">
            <th style="padding:8px;">Должность / источник</th>
            <th style="padding:8px;">Тип судна</th>
            <th style="padding:8px;">Зарплата</th>
            <th style="padding:8px;">Ссылка</th>
          </tr>
        </thead>
        <tbody>
          {"".join(rows)}
        </tbody>
      </table>
    </body>
    </html>
    """


def send_digest(vacancies: list[Vacancy], config: dict) -> None:
    """Отправляет ОДНО письмо-дайджест. Если vacancies пуст — вызывающий код
    (main.py) не должен вообще звать эту функцию (тишина в этот день)."""
    if not vacancies:
        logger.info("send_digest вызван с пустым списком — письмо отправляться не должно.")
        return

    gmail_address, gmail_password, mail_to = _get_credentials()

    subject_prefix = config.get("email", {}).get("subject_prefix", "Maritime Jobs Digest")
    subject = f"{subject_prefix}: {len(vacancies)} новых вакансий"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = mail_to
    msg.attach(MIMEText(build_digest_html(vacancies, config), "html", "utf-8"))

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.login(gmail_address, gmail_password)
        server.sendmail(gmail_address, [mail_to], msg.as_string())

    logger.info("Письмо отправлено на %s (%d вакансий).", mail_to, len(vacancies))
