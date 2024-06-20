# Очень крутая тема с isort, спасибо!
import datetime
import logging
import os
import sys
import time
import telebot
from http import HTTPStatus

import requests  # type: ignore
from dotenv import load_dotenv
from telebot import TeleBot  # type: ignore

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
_log_format = '%(asctime)s, %(levelname)s, %(message)s, %(name)s'


def get_file_handler():
    """Хендлер для записи логов в файл."""
    file_handler = logging.FileHandler('program.log')
    file_handler.setLevel(logging.WARNING)
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
    for token in SOURCE:
        if not globals()[token]:
            logger.critical(f'Отсутвует токен: {token}!')
            sys.exit()


def send_message(bot, message):
    """Отправка сообщения."""
    try:
        logger.debug('Начало отправки сообщения...')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug('Сообщение отправлено')
    except telebot.apihelper.ApiException:
        logger.error('Ошибка отправки сообщения!')


def get_api_answer(timestamp):
    """Запрос к API."""
    try:
        logger.debug('Начало отправки запроса к API...')
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
    except requests.exceptions.RequestException as error:
        logger.critical(f'Ошибка отправки запроса! Ошибка: {error}')
        raise ConnectionError(f'Ошибка подключения! Ошибка: {error}')
    else:
        if response.status_code != HTTPStatus.OK:
            logger.critical(
                'Status code отличен от 200!'
                'Status_code: ', response.status_code
            )
            raise StatusCodeException(
                'Status code отличен от 200!'
                'Status_code: ', response.status_code
            )
        logger.debug('Запрос к API успешно отправлен.')
        return response.json()


def check_response(response):
    """Проверка типа данных в ответе API."""
    logger.debug('Начало проверки ответа API...')
    if not isinstance(response, dict):
        logger.error(
            'В ответе API структура данных не соответствует ожиданиям'
            'Ожидается dict: ', type(response)
        )
        raise TypeError(
            'В ответе API структура данных не соответствует ожиданиям'
        )
    elif 'homeworks'not in response:
        logger.error('В ответе API отсутствует ключ homeworks')
        raise KeyError('В ответе API отсутствует ключ homeworks')
    elif 'current_date'not in response:
        logger.error('В ответе API отсутствует ключ current_date')
        raise KeyError('В ответе API отсутствует ключ current_date')
    elif not isinstance(response.get('homeworks'), list):
        logger.error(
            'В ответе API домашки под ключом homeworks'
            'данные приходят не в виде списка.'
        )
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
        logger.error('Отсутствует ключ homework_name!')
        raise KeyError(
            'Отсутствует ключ homework_name!'
        )

    homework_name = homework.get('homework_name')

    if homework.get('status') is None:
        logger.error('Отсутствует ключ status!')
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
    last_error_message = None

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)

            if response.get('homeworks') is None:
                logger.debug('Список с домашками пуст.')

            else:
                homework = response.get('homeworks')[0]
                # Я так и не понял, нужно ли сравнивать что-то.
                if parse_status(homework) != last_message:
                    send_message(bot, parse_status(homework))
                last_message = parse_status(homework)

            timestamp = response['current_date']

        except Exception as error:
            error_message = f'Сбой в работе программы: {error}'
            if last_error_message != error_message:
                send_message(bot, error_message)
                logger.error(error_message)
                last_error_message = error_message

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
