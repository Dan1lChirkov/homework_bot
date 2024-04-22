import logging
import os
import requests
import time

import telegram
from http import HTTPStatus
from dotenv import load_dotenv
from logging import StreamHandler

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s, %(levelname)s, %(message)s',
    filename='homework.log',
    filemode='w'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = StreamHandler()
logger.addHandler(handler)
RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


class TokenIsMissing(Exception):
    """Ошибка отсутствия токена."""

    pass


class NoResponse(Exception):
    """Ошибка отсутствия ответа сервера."""

    pass


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка доступности переменных окружения."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID:': TELEGRAM_CHAT_ID
    }
    token_is_missing = False
    for key in tokens:
        if tokens.get(key) is None:
            message = f'Токен {key} не передан.'
            logger.critical(message, exc_info=False)
            token_is_missing = True
    if token_is_missing:
        raise TokenIsMissing('Некоторые токены не найдены')


def send_message(bot, message):
    """Отправка сообщения."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Сообщение {message} отправлено.')
    except telegram.error.TelegramError as error:
        logger.error(f'Сообщение не отправлено. Ошибка: {error}.')


def get_api_answer(timestamp):
    """Запрос к эндпоинту API сервиса."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        if response.status_code == HTTPStatus.OK:
            return response.json()
        raise Exception(f'Статус запроса: {response.status_code}')
    except requests.RequestException as error:
        logger.error(f'Ошибка при запросе к API сервиса. {error}')


def check_response(response):
    """Проверка ответа API."""
    if response is None:
        logger.error('Отсутствует ответ от сервера')
        raise NoResponse('Отсутствует ответ от сервера')
    elif isinstance(response, dict):
        homeworks = response.get('homeworks')
        if isinstance(homeworks, list):
            return response
        raise TypeError(
            'Тип данных под ключом "homeworks" должен быть списком'
        )
    elif isinstance(response, list):
        raise TypeError('Данные должны быть в виде словаря')
    elif response.status_code != HTTPStatus.OK:
        logger.error(f'Ошибка запроса к API: код: {response.status_code}')
        return None


def parse_status(homework):
    """Извлечение статуса работы."""
    for value in ('status', 'homework_name'):
        if value not in homework:
            raise KeyError(
                f'Значение {value} не зарегестрировано'
            )
    if homework['status'] not in HOMEWORK_VERDICTS:
        raise ValueError(
            f'Полученный статус {homework["status"]} не зарегестрирован'
        )
    name = homework['homework_name']
    status = homework['status']
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error_messsage = None
    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homeworks = response.get('homeworks')
            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot=bot, message=message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message != last_error_messsage:
                send_message(bot=bot, message=message)
                last_error_messsage = message
            logger.exception(message, exc_info=False)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
