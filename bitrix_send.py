import requests
from config_loader import ConfigLoader
from typing import Dict


def bitrix_start_bp(config: ConfigLoader = None,
                    data_about_fn: Dict = None):
    """
    запуск БП по замене ФН
    :param config: конфиг для связи с битриксом
    :param data_about_fn: dict данные по ФН, адрес, магазин, дедлайн в рабочих днях
    :return:
    """
    url_start = config.get('bitrix', 'url_start', as_type=str)
    url_finish = config.get('bitrix', 'url_finish', as_type=str)
    webhook = config.get('bitrix', 'webhook')
    url = f"{url_start}/{webhook}/{url_finish}"
    r = requests.post(url, json=data_about_fn, timeout=20)
    r.raise_for_status()
    print(r.text)
    return r.status_code


def main():
    config = ConfigLoader("config.ini")
    payload = {
        "REST_USER_ID": config.get('bitrix', 'user_id', as_type=int),
        "TITLE_TASK": 'замена ФН тест',
        "ADDRESS": 'Пермь, Ленина 60',
        "DESCRIPTION_TASK": "заменить фн PM1, PM2",
        "LOCATION": 'Пермь, Ленина 60',
        "DAYS_DEADLINE": "1"
    }

    bitrix_start_bp(config=config, data_about_fn=payload)


if __name__ == '__main__':
    main()