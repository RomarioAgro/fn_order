#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
скрипт для поиска касс которым скоро ФН менять, имя файла от кассы хранится в таком виде:
KH1_kassir3_08.10.2025_0642640006114926.txt, делаем поиск файлов
Рекурсивно обходит все файлы в папке и строит список словарей:
  {'inn': ИНН, 'org': Название(я) организации, 'count': кол-во уникальных ZN,
   'indexes': [уникальные первые 2 символа названий файлов], 'adresses': [адреса]}
Группировка по ИНН (все организации с одинаковым INN складываются).
Сохраняет текстовый файл, где каждая строка:
  INN, ORG, COUNT, IDX, адрес1; адрес2; адрес3

Примечания:
- "count" — число уникальных значений из строк 'ZN ...'.
- Название организации берётся из строк 'ORG ...'; при нескольких вариантах объединяется через " / ".
- 'indexes' — уникальные первые 2 символа имени файла (basename).
- Ищутся строки: INN / ORG / ADR / ZN (чувствительно к регистру).
- Кодировки: utf-8 → cp1251 → utf-8(errors='ignore').
"""

from pathlib import Path
import re
from pprint import pprint
from config_loader import ConfigLoader
from datetime import datetime
import telebot
from typing import Dict, List
from bitrix_send import bitrix_start_bp
from logger_setup import get_logger

logger = get_logger(__name__)


# >>> Настройки <<<
PRINT_LIST_TO_CONSOLE = True            # вывести список словарей в консоль

# Регулярные выражения для парсинга
RE_INN = re.compile(r'^\s*INN\s+(\d+)\s*$')
RE_ORG = re.compile(r'^\s*ORG\s+(.+?)\s*$')
RE_ADR = re.compile(r'^\s*ADR\s+(.+?)\s*$')
RE_ZN  = re.compile(r'^\s*ZN\s+(\S+)\s*$')
RE_SROK  = re.compile(r'^\s*SROK\s+(\S+)\s*$')

def iter_lines(path: Path):
    """Итератор по строкам с попытками декодировки: utf-8 → cp1251 → utf-8(errors=ignore)."""
    try:
        with path.open('r', encoding='utf-8') as f:
            for line in f:
                yield line.rstrip('\n')
        return
    except UnicodeDecodeError:
        pass
    try:
        with path.open('r', encoding='cp1251') as f:
            for line in f:
                yield line.rstrip('\n')
        return
    except UnicodeDecodeError:
        pass
    with path.open('r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            yield line.rstrip('\n')

def parse_file(path: Path):
    """
    Парсит один файл и возвращает кортеж:
      (inn, org_set, zn_set, adr_set, prefix2)
    где prefix2 — первые 2 символа от имени файла (basename).
    """
    inn = 'no_inn'
    zn = 'no_zn'
    adr = 'no_adr'
    org = 'no_org'
    srok = '??.??.????'
    prefix2 = path.name[:2].upper() if path.name else "no_prefix"

    for raw in iter_lines(path):
        line = raw.strip()
        if not line:
            continue
        m = RE_INN.match(line)
        if m:
            inn = m.group(1)
            continue
        m = RE_ORG.match(line)
        if m:
            org = m.group(1).replace('\"', '').upper()
            continue
        m = RE_ADR.match(line)
        if m:
            adr = m.group(1)
            continue
        m = RE_ZN.match(line)
        if m:
            zn = m.group(1)
            continue
        m = RE_SROK.match(line)
        if m:
            srok = m.group(1)
            continue
    dict_out = {
        'inn': inn,
        'org': org,
        'zn': zn,
        'adr': adr,
        'prefix': prefix2,
        'srok':srok
    }

    return dict_out

def pattern_file_name() -> str:
    """
    формируем шаблон поиска файлов касс, у которых фн кончается
    :return: str шаблон
    """
    current_time = datetime.now()
    month = current_time.month + 1
    year = current_time.year
    # если сейчас декабрь — перейти на январь следующего года
    if month > 12:
        month = 1
        year += 1
    pattern = f"*.{month:02d}.{year}_*.txt"
    return pattern

def build_summary_by_inn(root: Path):
    """
    Рекурсивно обходит ВСЕ файлы и агрегирует по INN:
      - org_names: множество встреченных ORG
      - zn: множество уникальных ZN (для подсчёта)
      - adresses: множество адресов
      - prefixes: множество первых 2 символов имён файлов
    Возвращает список словарей нужного формата.
    """
    groups = {}  # inn -> {'org_names': set(), 'zn': set(), 'adresses': set(), 'prefixes': set()}
    # ищем примерно такое '4f1_kassir1_25.03.2026_0422010007047405.txt'
    pattern = pattern_file_name()
    result = []
    for p in root.rglob(pattern):
        if not p.is_file():
            continue

        # inn, org_set, zn_set, adr_set, prefix2 = parse_file(p)
        squeeze_fn = parse_file(p)
        squeeze_fn['path'] = str(p)
        result.append(squeeze_fn)
    # Сортируем по INN и ORG
    result.sort(key=lambda r: (r['inn'], r['org']))
    return result

def save_text(result, out_path: Path):
    """
    Сохраняет в текстовый файл строки вида:
      INN, ORG, COUNT, адрес1; адрес2; адрес3
    (indexes по ТЗ в файл не записываются)
    """
    with open(out_path, 'w', encoding='utf-8') as f:
        for row in result:
            addresses_part = "; ".join(row['adresses']) if row['adresses'] else ""
            line = f"{row['inn']}, {row['org']}, {row['count']} шт., {row['indexes']}"
            if addresses_part:
                line += f", {addresses_part}"
            f.write(line + "\n")

def send_order_to_tg(result: Dict = None,
                     config=None):
    my_bot = telebot.TeleBot(config.get('telegram', 'tg_token'))
    id_roman = config.get('telegram', 'tg_roman')
    work_id = config.get('telegram', 'tg_id')
    for row in result:
        addresses_part = "; ".join(row['adresses']) if row['adresses'] else ""
        line = f"{row['inn']}, {row['org']}, {row['count']} шт., {row['prefix']}"
        if addresses_part:
            line += f", {addresses_part}"
            my_mess = f'заказ ФН:\n{line}'
            try:
                my_bot.send_message(id_roman, f'<b>{my_mess}</b>', parse_mode='html')
                my_bot.send_message(work_id, f'<b>{my_mess}</b>', parse_mode='html')
            except Exception as exs:
                print(exs)

def bitrix_groupe_result(list_in: List = None):
    """
    группируем результат по префиксам магазинов чтобы задачи поставить в битрикс
    :param list_in: список словарей с данными ФН
    :return:
    список словарей с данными ФН сгруппированные по торговым точкам
    """
    list_out = []
    prefix_groups = {}
    for item in list_in:
        prefix = item['prefix']
        if prefix not in prefix_groups:
            prefix_groups[prefix] = {
                'prefix': prefix,
                'inn': item['inn'],
                'org': item['org'],
                'adresses': [],
            }
        prefix_groups[prefix]['adresses'].append(item['adr'])
    for prefix, info in prefix_groups.items():
        info['count'] = len(info['adresses'])
        list_out.append(info)
    print(list_out)
    return list_out

def make_task_bitrix(list_in: List = None, config: ConfigLoader = None):
    """
    проход по списку
    :param list_in:
    :param config:
    :return:
    """
    for elem in list_in:
        data = {
            "REST_USER_ID": config.get('bitrix', 'user_id', as_type=int),
            "TITLE_TASK": f'замена ФН {elem["prefix"]} - {elem["count"]} шт.',
            "ADDRESS": f'{elem["adresses"][0]}',
            "DESCRIPTION_TASK": f'заменить ФН {elem["prefix"]} - {elem["count"]} шт.',
            "LOCATION": f'{elem["adresses"][0]}',
            "DAYS_DEADLINE": "1"
        }
        result_req_bitrix = bitrix_start_bp(config=config, data_about_fn=data)
        logger.info(f'реультат обращения к битриксу {result_req_bitrix}')


def main():
    logger.info(f'запустили скрипт')
    config = ConfigLoader("config.ini")
    logger.info(f'прочитали конфиг')
    ROOT = Path(config.get('local', 'path'))
    OUTPUT_TXT = "summary_by_inn.txt"
    result = build_summary_by_inn(ROOT)
    logger.info(f'собрали инфу по нужныи ФН {result}')
    if PRINT_LIST_TO_CONSOLE:
        pprint(result, width=120, compact=True)
    list_for_bitrix = bitrix_groupe_result(list_in=result)
    logger.info(f'преобразовали инфу для битрикса')
    # make_task_bitrix(list_in=list_for_bitrix, config=config)
    logger.info(f'преобразовали инфу для битрикса')
    send_order_to_tg(result=list_for_bitrix, config=config)
    print(f"\nГотово: {OUTPUT_TXT} (записано строк: {len(result)})")

if __name__ == "__main__":
    main()

