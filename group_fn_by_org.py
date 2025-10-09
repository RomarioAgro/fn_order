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
from typing import Dict


# >>> Настройки <<<
PRINT_LIST_TO_CONSOLE = True            # вывести список словарей в консоль

# Регулярные выражения для парсинга
RE_INN = re.compile(r'^\s*INN\s+(\d+)\s*$')
RE_ORG = re.compile(r'^\s*ORG\s+(.+?)\s*$')
RE_ADR = re.compile(r'^\s*ADR\s+(.+?)\s*$')
RE_ZN  = re.compile(r'^\s*ZN\s+(\S+)\s*$')

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
    inn = None
    zn_set, adr_set = set(), set()
    org = ''
    prefix2 = path.name[:2].upper() if path.name else ""

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
            # org_set.add(m.group(1).replace('\"', '').upper())
            org = m.group(1).replace('\"', '').upper()
            continue

        m = RE_ADR.match(line)
        if m:
            adr_set.add(m.group(1))
            continue

        m = RE_ZN.match(line)
        if m:
            zn_set.add(m.group(1))
            continue

    return inn, org, zn_set, adr_set, prefix2

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
    for p in root.rglob(pattern):
        if not p.is_file():
            continue

        inn, org_set, zn_set, adr_set, prefix2 = parse_file(p)
        if not inn:
            continue

        bucket = groups.setdefault(inn, {
            'org_names': str(),
            'zn': set(),
            'adresses': set(),
            'prefixes': set(),
            'paths': set()
        })
        bucket['org_names'] = org_set
        bucket['zn'].update(zn_set)
        bucket['adresses'].update(adr_set)
        if prefix2:
            bucket['prefixes'].add(prefix2)
        bucket['paths'].add(str(p))
    # Преобразуем в список словарей
    result = []
    for inn, data in groups.items():
        org_display = data['org_names']
        adrs = sorted(a.strip() for a in data['adresses'] if a and a.strip())
        idxs = sorted(x.strip() for x in data['prefixes'] if x and x.strip())
        paths = data['paths']

        result.append({
            'inn': inn,
            'org': org_display,
            'count': len(data['zn']),
            'indexes': idxs,          # список первых 2 символов имён файлов
            'adresses': adrs,         # оставляю ключ как вы просили
            'paths': paths
        })

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
        line = f"{row['inn']}, {row['org']}, {row['count']} шт., {row['indexes']}"
        if addresses_part:
            line += f", {addresses_part}"
            my_mess = f'заказ ФН:\n{line}'
            try:
                my_bot.send_message(id_roman, f'<b>{my_mess}</b>', parse_mode='html')
                my_bot.send_message(work_id, f'<b>{my_mess}</b>', parse_mode='html')
            except Exception as exs:
                print(exs)


def main():
    config = ConfigLoader("config.ini")
    ROOT = Path(config.get('local', 'path'))
    OUTPUT_TXT = "summary_by_inn.txt"
    result = build_summary_by_inn(ROOT)
    if PRINT_LIST_TO_CONSOLE:
        pprint(result, width=120, compact=True)
    save_text(result, OUTPUT_TXT)
    send_order_to_tg(result=result, config=config)
    print(f"\nГотово: {OUTPUT_TXT} (записано строк: {len(result)})")

if __name__ == "__main__":
    main()

