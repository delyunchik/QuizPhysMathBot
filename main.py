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
from aiogram.types import ReplyKeyboardRemove
from aiogram.types import ParseMode
from emoji import emojize
from quiz_example import *
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


class Question:
    text: str  # текст вопроса
    len: int  # число вариантов
    formula: str  # формула
    options: str  # многострочный текст
    correct_option_id: int  # 0z-index


class Quiz:
    name: str  # Название викторины
    time: int  # время на викторину в минутах
    len: int  # чисто вопросов
    questions: list[Question] = []  # вопросы викторины


class User:
    full_name: str
    correct_answers: int = 0

    def __init__(self, full_name: str) -> None:
        self.full_name = full_name


class Test:  # Тест = экземпляр викторины
    close_dt: datetime  # время закрытия теста
    quiz_id: str  # ID теста из библиотеки тестов, quiz_id=0 встроенный
    poll_ids: list[int] = []  # идентификаторы poll_id
    user_id: int  # владелец теста
    chat_id: int  # id чата, в котором был запущен тест
    users: dict[int, User] = {}  # пользователи, участвовшие в ответах на вопросы теста


class Poll:
    test_id: int  # родительский ID (uuid) экземпляра теста с quiz_id
    correct_option_id: int  # номер правильного ответа

    def __init__(self, test_id: int, correct_option_id: int) -> None:
        self.test_id = test_id
        self.correct_option_id = correct_option_id


tests: dict[str, Test] = {}  # словарь экземпляров проведенных тестов, {test_id: Test}
polls: dict[int, Poll] = {}  # словарь вопросов проведенных тестов, {poll_id: Poll}
quizzes: list[Quiz] = [Quiz()]  # список викторин


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


async def parse_quiz(quiz_src: list[str]):
    k = 2  # число общих параметров
    qz = Quiz()
    qz.len = (len(quiz_src)-k) // 4  # число вопросов
    qz.name = quiz_src[0]
    qz.time = int(quiz_src[1])

    # добавим вопросы
    for i in range(qz.len):
        q = Question()
        q.text = quiz_src[i*4+k]
        q.formula = quiz_src[i*4+k+1]
        q.options = quiz_src[i*4+k+3]
        q.len = q.options.count('\n')+1
        q.correct_option_id = int(quiz_src[i*4+k+2])-1
        qz.questions.append(q)
    quizzes.append(qz)


async def start_test(quiz_id: int, chat_id: int, user_id: int):
    logging.info('Starting test with quiz_id={}'.format(quiz_id))
    test_id = uuid4()  # уникальный ID экземпляра теста
    close_dt = datetime.now() + timedelta(seconds=quizzes[quiz_id].time)
    test = Test()
    test.close_dt = close_dt
    test.quiz_id = quiz_id
    test.user_id = user_id
    test.chat_id = chat_id
    tests[test_id] = test
    msg = await bot.send_message(
        text=text(
            bold(quizzes[quiz_id].name),
            'Время окончания теста: {}'.format(
                close_dt.strftime('%X')),
            sep='\n'
        ),
        parse_mode=ParseMode.MARKDOWN,
        chat_id=chat_id,
    )
    # отправим вопросы
    for i in range(quizzes[quiz_id].len):
        q = quizzes[quiz_id].questions[i]
        msg = await bot.send_message(
            chat_id=chat_id,
            text=r'[{}/{}] {}'.format(i+1, quizzes[quiz_id].len, q.text),
        )
        msg = await bot.send_photo(
            chat_id=chat_id,
            photo=formula(q.formula),
        )
        msg = await bot.send_photo(
            chat_id=chat_id,
            photo=formula(q.options),
        )
        msg = await bot.send_poll(
            chat_id=chat_id,
            question='Выберите номер ответа:',
            options=[str(j+1) for j in range(q.len)],
            is_anonymous=False,
            type='quiz',
            close_date=close_dt,
            protect_content=True,
            correct_option_id=q.correct_option_id,
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
        chat_id=chat_id)


@dp.message_handler(commands=['quiz'])
async def command_quiz(message: types.Message):
    pass


@dp.poll_answer_handler()
async def handle_poll_answer(quiz_answer: types.PollAnswer):
    """
    Это хендлер на новые ответы в викторинах (Quiz)
    Реагирует на изменение голоса. В случае отзыва голоса тоже срабатывает!

    :param quiz_answer: объект PollAnswer с информацией о голосующем
    """
    logging.info(quiz_answer.as_json())
    username = quiz_answer.user.username
    poll_id = quiz_answer.poll_id
    test_id = polls[poll_id].test_id
    users = tests[test_id].users
    if username not in users:  # пользователь еще не участвовал в этом тесте
        users[username] = User(quiz_answer.user.full_name)
    if quiz_answer.option_ids[0] == polls[poll_id].correct_option_id:
        users[username].correct_answers += 1


# обработчик команды start
@dp.message_handler(commands=['start'])
async def command_start(message: types.Message):
    logging.info('START command msg={}'.format(message.as_json()))
    if ' ' in message.text:  # старт с параметром запуска теста
        quiz_id = int(message.text.split()[1])  # номер теста параметром
        await start_test(quiz_id, message.chat.id, message.from_id)
    else:
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
async def unknown_message(message: types.Message):
    logging.info('Unknown command msg={}'.format(message.as_json()))
    # дежурный текст
    message_text = text(
        emojize('К сожалению, я не знаю, что с этим делать :astonished_face:'),
        italic('\nПросто напомню,'), 'что есть',
        code('команда'), '/help'
    )
    # отправим его пользователю
    await message.reply(message_text, parse_mode=ParseMode.MARKDOWN)


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
    # загрузим демо викторину
    await parse_quiz(quiz_trigo_example)


# Обработчик завершения работы
async def shutdown(dispatcher: Dispatcher):
    # завершающие процедуры
    logging.info('Завершение работы бота!')


if __name__ == '__main__':
    # начать опрос API Telegram
    executor.start_polling(
        dp, on_startup=startup,
        on_shutdown=shutdown,
        skip_updates=True)  # пропускать сообщения при остановленном
