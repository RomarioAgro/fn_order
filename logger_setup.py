import logging
import os
import tempfile
from datetime import datetime

def get_logger(name: str = None) -> logging.Logger:
    """
    Создаёт и возвращает настроенный логгер.
    Логи пишутся в temp-папку с именем файла вида app_YYYYMMDD.log
    и одновременно выводятся в консоль.
    """

    # Папка для логов — системная временная
    log_dir = os.path.join(tempfile.gettempdir(), "_fn_order")
    os.makedirs(log_dir, exist_ok=True)

    # Имя файла лога с датой
    log_filename = os.path.join(log_dir, f"app_{datetime.now():%Y%m%d}.log")

    # Формат логов
    log_format = (
        "%(asctime)s | %(levelname)-8s | "
        "module=%(module)s | path=%(pathname)s | line=%(lineno)d | "
        "msg=%(message)s"
    )

    # Создаём логгер
    logger = logging.getLogger(name or __name__)
    logger.setLevel(logging.INFO)

    # Чтобы не добавлять хендлеры повторно (иначе будет дублирование строк)
    if not logger.handlers:
        formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")

        # --- Файловый хендлер ---
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # --- Консольный хендлер ---
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger
