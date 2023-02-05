import config
import logging
import aioschedule
import asyncio
from uuid import uuid4
from datetime import datetime, timedelta
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor
from aiogram.utils.markdown import text, bold, italic, code
from aiogram.types import ReplyKeyboardRemove, \
    ReplyKeyboardMarkup, KeyboardButton, \
    InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import ParseMode, \
    InputMediaPhoto, InputMediaVideo, ChatActions
from emoji import emojize
from quiz import quiz
from formula import formula

# Настраиваем журналирование
logging.basicConfig(
    # filename='TrigoTgBot.log',
    level=config.LOG_LEVEL,
    format='%(asctime)s [%(levelname)s] ' +
           '%(module)s - %(funcName)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    )

# инициализация бота
bot = Bot(token=config.API_TOKEN, proxy=config.PROXY_URL)
# за хэндлеры отвечает специальный Диспетчер
dp = Dispatcher(bot)

tests = {}  # экземпляры проведенных тестов, состоят из polls
polls = {}  # отдельные вопросы


class Test:
    close_dt: datetime
    quiz_id: str
    poll_ids: list() = []  # идентификаторы poll_id
    user_id: int
    chat_id: int
    users: dict() = {}


class Poll:
    test_id: int
    correct_option_id: int

    def __init__(self, test_id: int, correct_option_id: int) -> None:
        self.test_id = test_id
        self.correct_option_id = correct_option_id


class User:
    full_name: str
    correct_answers: int = 0

    def __init__(self, full_name: str) -> None:
        self.full_name = full_name


async def print_results(test_id, chat_id):
    # logging.debug('schedule userid={}'.format(userid))
    text = bold('Результаты:\n')
    users = tests[test_id].users
    num_polls = len(tests[test_id].poll_ids)
    for user in users:
        text += '{} @{} {}/{}'.format(
            users[user].full_name,
            user,
            users[user].correct_answers,
            num_polls
        )
    await bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.MARKDOWN,
    )
    return aioschedule.CancelJob


@dp.message_handler(commands=['quiz'])
async def command_quiz(message: types.Message):
    quiz_id = 0  # id теста из библиотеки тестов
    logging.info('QUIZ command msg={}'.format(message.as_json()))
    k = 2  # число общих параметров
    n = (len(quiz)-k) // 4  # число вопросов
    test_id = uuid4()  # уникальный ID экземпляра теста
    close_dt = datetime.now() + timedelta(seconds=int(quiz[1]))
    test = Test()
    test.close_dt = close_dt
    test.quiz_id = quiz_id
    test.user_id = message.from_id
    test.chat_id = message.chat.id
    tests[test_id] = test
    msg = await bot.send_message(
        chat_id=message.chat.id,
        text=text(
            bold(quiz[0]),
            'Время окончания теста: {}'.format(
                close_dt.strftime('%X')),
            sep='\n'
        ),
        parse_mode=ParseMode.MARKDOWN,
    )
    # отправим вопросы
    for i in range(n):
        msg = await bot.send_message(
            chat_id=message.chat.id,
            text=r'[{}/{}] {}'.format(i+1, n, quiz[i*4+k]),
        )
        msg = await bot.send_photo(
            chat_id=message.chat.id,
            photo=formula(quiz[i*4+k+1]),
        )
        q = quiz[i*4+k+3].count('\n')+1  # число ответов
        msg = await bot.send_photo(
            chat_id=message.chat.id,
            photo=formula(quiz[i*4+k+3]),
        )
        msg = await bot.send_poll(
            chat_id=message.chat.id,
            question='Выберите номер ответа:',
            options=[str(j+1) for j in range(q)],
            is_anonymous=False,
            type='quiz',
            close_date=close_dt,
            protect_content=True,
            correct_option_id=quiz[i*4+k+2]-1,
        )
        polls[msg.poll.id] = Poll(test_id, msg.poll.correct_option_id)
        tests[test_id].poll_ids.append(msg.poll.id)
        logging.info('i={} msg={}'.format(i, msg.as_json()))
    # заведем таймер на окончание теста для вывода результатов
    results_dt = close_dt + timedelta(minutes=1)
    tm = results_dt.strftime('%H:%M')
    aioschedule.every().day.at(tm).do(
        print_results,
        test_id=test_id,
        chat_id=message.chat.id)


@dp.poll_answer_handler()
async def handle_poll_answer(quiz_answer: types.PollAnswer):
    """
    Это хендлер на новые ответы в опросах (Poll) и викторинах (Quiz)
    Реагирует на изменение голоса. В случае отзыва голоса тоже срабатывает!

    :param quiz_answer: объект PollAnswer с информацией о голосующем
    """
    logging.info(quiz_answer.as_json())
    username = quiz_answer.user.username
    poll_id = quiz_answer.poll_id
    test_id = polls[poll_id].test_id
    users = tests[test_id].users
    if username not in users:
        users[username] = User(quiz_answer.user.full_name)
    if quiz_answer.option_ids[0] == polls[poll_id].correct_option_id:
        users[username].correct_answers += 1


# обработчик команды start
@dp.message_handler(commands=['start'])
async def command_start(message: types.Message):
    # ответим приветственным сообщением
    await message.reply('Привет!\nИспользуй /help, '
                        'чтобы узнать список доступных команд!',
                        reply_markup=ReplyKeyboardRemove())


# обработчик команды help
@dp.message_handler(commands=['help'])
async def process_help_command(message: types.Message):
    logging.info('HELP command msg={}'.format(message.as_json()))
    # сформируем текст сообщения
    msg = text(
        'Создать викторину /quiz',
        'Могу повторить данную справку /help',
        sep='\n')
    # ответим подготовленным текстом
    await message.reply(msg, parse_mode=ParseMode.MARKDOWN)


# если не подошел ни один из предыдущих обработчиков
@dp.message_handler(content_types=types.ContentType.ANY)
async def unknown_message(msg: types.Message):
    # дежурный текст
    message_text = text(
        emojize('К сожалению, я не знаю, что с этим делать :astonished_face:'),
        italic('\nПросто напомню,'), 'что есть',
        code('команда'), '/help'
    )
    # отправим его пользователю
    await msg.reply(message_text, parse_mode=ParseMode.MARKDOWN)


# Обработчик заданий по расписанию
async def scheduler():
    logging.info('Старт Scheduler()')
    while True:
        await aioschedule.run_pending()
        await asyncio.sleep(5)


# Обработчик начала работы бота
async def startup(_):
    logging.info('Старт работы бота!')
    asyncio.create_task(scheduler())


# Обработчик завершения работы
async def shutdown(dispatcher: Dispatcher):
    # завершающие процедуры
    logging.info('Завершение работы бота!')


if __name__ == '__main__':
    # начать опрос API Telegram
    executor.start_polling(
        dp, on_startup=startup,
        on_shutdown=shutdown,
        skip_updates=True)  # не обрабатывать сообщения
                            # присланные при остановленном боте
