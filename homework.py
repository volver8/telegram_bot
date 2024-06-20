import time
import datetime
import sys

import logging
import os
import requests  # type: ignore
from http import HTTPStatus
from dotenv import load_dotenv
from telebot import TeleBot  # type: ignore

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


class StatusCodeException(Exception):
    """Класс обработки исключений неправльного ответа API."""

    pass


class HomeworkStatusException(Exception):
    """Класс обработки исключений пустого статуса в домашке."""

    pass


_log_format = '%(asctime)s, %(levelname)s, %(message)s, %(name)s'


def get_file_handler():
    """Хендлер для записи логов в файл."""
    file_handler = logging.FileHandler('program.log')
    file_handler.setLevel(logging.WARNING)
    file_handler.setFormatter(logging.Formatter(_log_format))
    return file_handler


def get_stream_handler():
    """Хендлер StreamHandler."""
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(logging.Formatter(_log_format))
    return stream_handler


def get_logger(name):
    """Настройка хендлера."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(get_file_handler())
    logger.addHandler(get_stream_handler())
    return logger


# Установка настроек логгера
logger = get_logger(__name__)


def check_tokens():
    """Проверка токенов."""
    if None not in (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID):
        return False
    return True


def send_message(bot, message):
    """Отправка сообщения."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug(message)
    except Exception as error:
        logger.error('Ошибка при отправке сообщения в Телеграм.', error)


def get_api_answer(timestamp):
    """Запрос к API."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        response.raise_for_status()
        if response.status_code != HTTPStatus.OK:
            raise StatusCodeException
    except requests.exceptions.HTTPError as error:
        print("Http Error:", error)
    except requests.exceptions.ConnectionError as error:
        print("Error Connecting:", error)
    except requests.exceptions.Timeout as error:
        print("Timeout Error:", error)
    except requests.exceptions.RequestException as error:
        print("OOps: Something Else", error)
    else:
        return response.json()


def check_response(response):
    """Проверка типа данных в ответе API."""
    if type(response) is not dict:
        raise TypeError(
            'В ответе API структура данных не соответствует ожиданиям'
        )
    elif type(response.get('homeworks')) is not list:
        raise TypeError(
            'В ответе API домашки под ключом homeworks'
            'данные приходят не в виде списка.'
        )


def parse_status(homework):
    """Парсинг ответа от API."""
    homework_name = homework.get('homework_name')
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        raise HomeworkStatusException(
            'API домашки возвращает недокументированный статус'
        )
    elif homework_name is None:
        raise HomeworkStatusException(
            'API домашки возвращает недокументированный статус'
        )
    elif status is None:
        raise HomeworkStatusException(
            'API домашки возвращает недокументированный статус'
        )
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if check_tokens():
        logger.critical('Не найдены токены в глобальном окружении.')
        sys.exit()
    # Создаем объект класса бота
    bot = TeleBot(token=TELEGRAM_TOKEN)

    # Создаем начало отсчета для format_date
    timestamp = int(datetime.datetime(2024, 6, 10, 0, 0, 0, 0).timestamp())
    
    # Переменная для проверки изменения статуса
    last_status = None

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            # homeworks = response.get('homeworks')
            homework = response.get('homeworks')[0]
            status = homework.get('status')
            print(f'Вторая ДЗ: {homework}')
            print(f'Вторая ДЗ статус: {status}')
            if status != last_status:
                send_message(bot, parse_status(homework))
            last_status = status

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logger.error(message)

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
