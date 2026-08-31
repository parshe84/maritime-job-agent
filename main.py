#!/usr/bin/env python3
"""
Maritime Job Agent — точка входа.

Последовательно вызывает все парсеры из parsers/, фильтрует результаты по
config.yaml, дедуплицирует по seen_vacancies.json и, если есть новые
подходящие вакансии, отправляет ОДИН email-дайджест через mailer.py.

Падение одного парсера НЕ останавливает остальные — каждый вызов обёрнут
в try/except с логированием (см. run_all_parsers()).
"""
from __future__ import annotations

import importlib
import json
import logging
import pkgutil
import sys
from pathlib import Path

import yaml

import parsers as parsers_pkg
from parsers.base import Vacancy, matches_any, parse_salary_usd, polite_sleep, vessel_matches
from mailer import send_digest, MailerConfigError

ROOT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = ROOT_DIR / "config.yaml"
SEEN_PATH = ROOT_DIR / "seen_vacancies.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("maritime_job_agent")


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_seen() -> dict:
    if not SEEN_PATH.exists():
        return {}
    try:
        with open(SEEN_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Не удалось прочитать %s (%s) — начинаем с чистого списка.", SEEN_PATH, exc)
        return {}


def save_seen(seen: dict) -> None:
    with open(SEEN_PATH, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2, sort_keys=True)


def discover_parser_modules():
    """Находит все модули в пакете parsers/, кроме служебных (base, __init__)."""
    modules = []
    for _, name, is_pkg in pkgutil.iter_modules(parsers_pkg.__path__):
        if is_pkg or name in ("base",):
            continue
        modules.append(name)
    return sorted(modules)


def run_all_parsers(config: dict) -> list[Vacancy]:
    """Вызывает fetch_vacancies() каждого источника. Ошибка одного источника
    логируется и не мешает остальным (двойная защита: try/except тут И
    внутри каждого парсера)."""
    all_vacancies: list[Vacancy] = []
    sources_cfg = config.get("sources", {})

    for module_name in discover_parser_modules():
        source_cfg = sources_cfg.get(module_name, {})
        if source_cfg.get("enabled", True) is False:
            logger.info("[%s] Источник отключён в config.yaml — пропускаем.", module_name)
            continue

        logger.info("[%s] Запускаю парсер...", module_name)
        try:
            module = importlib.import_module(f"parsers.{module_name}")
            vacancies = module.fetch_vacancies(config)
            if vacancies is None:
                vacancies = []
            logger.info("[%s] Получено вакансий: %d", module_name, len(vacancies))
            all_vacancies.extend(vacancies)
        except Exception:
            logger.exception(
                "[%s] Парсер упал с ошибкой — пропускаем источник, остальные продолжают работу.",
                module_name,
            )
        finally:
            polite_sleep(config)

    return all_vacancies


def matches_filters(vacancy: Vacancy, config: dict) -> bool:
    filters = config.get("filters", {})
    haystack = " ".join([vacancy.title, vacancy.vessel_type, vacancy.raw_text])

    if not matches_any(haystack, filters.get("positions", [])):
        return False

    if not vessel_matches(haystack, filters):
        return False

    flags = filters.get("flags") or []
    if flags and not matches_any(haystack, flags):
        return False

    contract_lengths = filters.get("contract_lengths") or []
    if contract_lengths and not matches_any(haystack, contract_lengths):
        return False

    salary = vacancy.salary_usd_month
    if salary is None:
        salary = parse_salary_usd(haystack)
        vacancy.salary_usd_month = salary

    min_salary = filters.get("min_salary_usd", 0)
    if salary is not None:
        return salary >= min_salary

    return bool(filters.get("include_unknown_salary", True))


def main() -> int:
    config = load_config()
    seen = load_seen()

    logger.info("=== Maritime Job Agent: старт сбора ===")
    all_vacancies = run_all_parsers(config)
    logger.info("Всего собрано вакансий со всех источников: %d", len(all_vacancies))

    matched = [v for v in all_vacancies if matches_filters(v, config)]
    logger.info("Подходят под критерии фильтра: %d", len(matched))

    new_vacancies = [v for v in matched if v.id not in seen]
    logger.info("Из них новых (ещё не отправлялись ранее): %d", len(new_vacancies))

    if not new_vacancies:
        logger.info("Новых подходящих вакансий нет — письмо не отправляется. Тишина.")
        return 0

    try:
        send_digest(new_vacancies, config)
    except MailerConfigError as exc:
        logger.error("Не удалось отправить письмо: %s", exc)
        # Секреты не настроены — НЕ помечаем вакансии как отправленные,
        # чтобы при следующем запуске (после настройки секретов) они снова
        # попали в дайджест, а не потерялись.
        return 1
    except Exception:
        logger.exception("Не удалось отправить письмо по неожиданной причине.")
        return 1

    for v in new_vacancies:
        seen[v.id] = {
            "title": v.title,
            "source": v.source,
            "url": v.url,
        }
    save_seen(seen)
    logger.info("seen_vacancies.json обновлён (%d записей всего).", len(seen))

    return 0


if __name__ == "__main__":
    sys.exit(main())
