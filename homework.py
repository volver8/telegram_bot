import datetime
import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telebot
from dotenv import load_dotenv
from telebot import TeleBot

from exceptions import HomeworkStatusException, StatusCodeException

load_dotenv()


# Токены
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Кортеж токенов
SOURCE = ("PRACTICUM_TOKEN", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID")

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

# Формат записи для хендлера
# Добавил lineno
# _log_format получился длинным, есть более лучший способ исправить это?
format_1 = '%(asctime)s, %(levelname)s, %(funcName)s, %(lineno)d, %(message)s'
format_2 = '%(name)s'
_log_format = format_1 + format_2


def get_file_handler():
    """Хендлер для записи логов в файл."""
    file_handler = logging.FileHandler('program.log', 'w', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(_log_format))
    return file_handler


def get_stream_handler():
    """Хендлер StreamHandler."""
    stream_handler = logging.StreamHandler(sys.stdout)
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
    missing_tokens = []
    for token in SOURCE:
        if not globals()[token]:
            missing_tokens.append(token)
    if len(missing_tokens) != 0:
        logger.critical(f'Отсутвует токены: {missing_tokens}!')
        sys.exit(1)


def send_message(bot, message):
    """Отправка сообщения."""
    logger.debug('Начало отправки сообщения...')
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug('Сообщение отправлено')
    except telebot.apihelper.ApiException:
        logger.error('Ошибка отправки сообщения!')


def get_api_answer(timestamp):
    """Запрос к API."""
    logger.debug('Начало отправки запроса к API...')
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
    except requests.exceptions.RequestException as error:
        raise ConnectionError(f'Ошибка подключения! Ошибка: {error}')
    else:
        if response.status_code != HTTPStatus.OK:
            raise StatusCodeException(
                'Status code отличен от 200!'
                'Status_code: ', response.reason
            )
        logger.debug('Запрос к API успешно отправлен.')
        return response.json()


def check_response(response):
    """Проверка типа данных в ответе API."""
    logger.debug('Начало проверки ответа API...')
    if not isinstance(response, dict):
        raise TypeError(
            'В ответе API структура данных не соответствует ожиданиям'
            'Ожидается dict: ', type(response)
        )
    elif 'homeworks' not in response:
        raise KeyError('В ответе API отсутствует ключ homeworks')
    elif 'current_date' not in response:
        raise KeyError('В ответе API отсутствует ключ current_date')
    elif not isinstance(response.get('homeworks'), list):
        raise TypeError(
            'В ответе API домашки под ключом homeworks'
            'данные приходят не в виде списка!'
            'Ожидается list: ', type(response.get('homeworks'))
        )
    logger.debug('Проверка ответа API завершена.')


def parse_status(homework):
    """Проверка статуса ответа API."""
    logger.debug('Начало проверки статуса ответа API...')

    if homework.get('homework_name') is None:
        raise KeyError(
            'Отсутствует ключ homework_name!'
        )

    homework_name = homework.get('homework_name')

    if homework.get('status') is None:
        raise KeyError(
            'Отсутствует ключ status!'
        )

    status = homework.get('status')

    if status not in HOMEWORK_VERDICTS:
        raise HomeworkStatusException(
            f'API домашки возвращает недокументированный статус: {status}'
        )

    verdict = HOMEWORK_VERDICTS[status]
    logger.debug('Проверка статуса ответа API завершена.')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()

    # Создаем объект класса бота
    bot = TeleBot(token=TELEGRAM_TOKEN)

    # Создаем начало отсчета для format_date
    timestamp = int(datetime.datetime(2024, 6, 10, 0, 0, 0, 0).timestamp())

    # Начальные переменные для проверки
    last_message = None

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homeworks = response.get('homeworks')

            if homeworks is None:
                logger.debug('Список с домашками пуст.')

            else:
                homework = response.get('homeworks')[0]
                message = parse_status(homework)
                send_message(bot, message)
                last_message = message

            timestamp = response['current_date']

        except Exception as error:
            error_message = f'Сбой в работе программы: {error}'
            logger.error(error_message)
            if error_message != last_message:
                send_message(bot, error_message)
                last_message = error_message

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
