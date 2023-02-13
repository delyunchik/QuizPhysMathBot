import logging
import asyncio
from datetime import datetime, timedelta
import aioschedule
import config
from emoji import emojize
from formula import formula
import quiz_example
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor
from aiogram.utils.markdown import text, bold, italic, code
from aiogram.types import ReplyKeyboardRemove, ParseMode, User

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


# Класс вопроса викторины
class Question:
    text: str  # текст вопроса
    len: int  # число вариантов
    formula: str  # формула
    options: str  # многострочный текст
    correct_option_id: int  # 0z-index


# Класс викторины, состоит из вопросов
class Quiz:
    name: str  # Название викторины
    time: int  # время на викторину в минутах
    len: int  # чисто вопросов
    questions: list[Question]  # вопросы викторины

    def __init__(self) -> None:
        self.questions = []


class UserInfo:
    full_name: str
    correct_answers: int = 0

    def __init__(self, full_name: str) -> None:
        self.full_name = full_name


# Класс Теста, экземпляра викторины, состоит из отдельных опросов
class Test:
    close_dt: datetime  # время закрытия теста
    owner_fullname: str  # владелец теста (fullname)
    owner_username: str  # владелец теста (username)
    quiz_id: int  # ID теста из библиотеки тестов, quiz_id=0 встроенный
    poll_ids: list[int]  # идентификаторы poll_id
    chat_id: int  # id чата, в котором был запущен тест
    users: dict[int, UserInfo]  # участники {username: UserInfo}

    def __init__(self) -> None:
        self.poll_ids = []
        self.users = {}


# Класс опросов, входящих в тест
class Poll:
    owner_id: int  # автор теста (id) с данным вопросом
    test_id: int  # номер родительского теста данного пользователя
    correct_option_id: int  # номер правильного ответа

    def __init__(self, user_id: int, test_id: int,
                 correct_option_id: int) -> None:
        self.user_id = user_id
        self.test_id = test_id
        self.correct_option_id = correct_option_id


tests: dict[int, list[Test]] = {}  # экземпляры тестов, {user_id: Test[]}
polls: dict[int, Poll] = {}  # вопросы проведенных тестов, {poll_id: Poll}
quizzes: list[Quiz] = [Quiz()]  # список викторин, 1z-индекс


async def print_results(user_id: int, test_id: int, chat_id: int):
    # logging.debug('schedule userid={}'.format(userid))
    if user_id not in tests:
        txt = 'Вы еще не создали ни одного теста!'
    else:
        if len(tests[user_id])-1 < test_id:
            txt = 'Вы еще не запускали тест номер ' + str(test_id)
        else:
            users = tests[user_id][test_id].users
            quiz_name = quizzes[tests[user_id][test_id].quiz_id].name
            txt = bold('Результаты теста "{}"\n'.format(quiz_name)) + \
                'номер {} от {} @{}:\n'.format(
                    test_id,
                    tests[user_id][test_id].owner_fullname,
                    tests[user_id][test_id].owner_username)
            if len(users) == 0:
                txt += 'Никто не ответил ни на один вопрос теста!'
            else:
                num_polls = len(tests[user_id][test_id].poll_ids)
                for user in users:
                    txt += '{} @{} {}/{}'.format(
                        users[user].full_name,
                        user,
                        users[user].correct_answers,
                        num_polls
                    )
    await bot.send_message(
        chat_id=chat_id,
        text=txt,
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


async def start_test(quiz_id: int, chat_id: int, owner_id: int, owner: User):
    logging.info('Starting test with quiz_id=%d', quiz_id)
    if len(quizzes)-1 < quiz_id:
        msg = await bot.send_message(
            chat_id=chat_id,
            text='В каталоге отсутствует викторина номер {}'.format(quiz_id))
    else:
        close_dt = datetime.now() + timedelta(seconds=quizzes[quiz_id].time)
        test = Test()
        test.close_dt = close_dt
        test.quiz_id = quiz_id
        test.chat_id = chat_id
        test.owner_fullname = owner.full_name
        test.owner_username = owner.username
        if owner_id in tests:
            tests[owner_id].append(test)
        else:
            tests[owner_id] = [Test(), test]  # 1z-index
        test_id = len(tests[owner_id])-1
        msg = await bot.send_message(
            text=text(
                bold('Тест "' + quizzes[quiz_id].name + '"'),
                'Номер теста: {}'.format(test_id),
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
            polls[msg.poll.id] = Poll(owner_id, test_id,
                                      msg.poll.correct_option_id)
            tests[owner_id][test_id].poll_ids.append(msg.poll.id)
            logging.info('i=%d msg=%s', i, msg.as_json())
        # заведем таймер на окончание теста для вывода результатов
        results_dt = close_dt + timedelta(minutes=1)
        tm = results_dt.strftime('%H:%M')
        aioschedule.every().day.at(tm).do(
            print_results,
            user_id=owner_id,
            test_id=test_id,
            chat_id=chat_id)


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
    user_id = polls[poll_id].user_id
    test_id = polls[poll_id].test_id
    users = tests[user_id][test_id].users
    if username not in users:  # пользователь еще не участвовал в этом тесте
        users[username] = UserInfo(quiz_answer.user.full_name)
    if quiz_answer.option_ids[0] == polls[poll_id].correct_option_id:
        users[username].correct_answers += 1


# обработчик команды results
@dp.message_handler(commands=['results'])
async def command_quiz(message: types.Message):
    logging.info('RESULTS command msg=%s', message.as_json())
    if ' ' in message.text:  # с параметром запуска теста
        test_id = int(message.text.split()[1])  # номер теста параметром
        user_id = message.from_id
        await print_results(user_id, test_id, message.chat.id)
    else:
        # ответим приветственным сообщением
        await message.reply('Используйте /results <номер_теста>, '
                            'чтобы узнать результаты теста!',
                            reply_markup=ReplyKeyboardRemove())


# обработчик команды start
@dp.message_handler(commands=['start'])
async def command_start(message: types.Message):
    logging.info('START command msg=%s', message.as_json())
    if ' ' in message.text:  # старт с параметром запуска теста
        quiz_id = int(message.text.split()[1])  # номер теста параметром
        await start_test(quiz_id, message.chat.id, message.from_id,
                         message.from_user)
    else:
        # ответим приветственным сообщением
        await message.reply('Привет!\nИспользуйте /help, '
                            'чтобы узнать список доступных команд!',
                            reply_markup=ReplyKeyboardRemove())


# обработчик команды help
@dp.message_handler(commands=['help'])
async def command_help(message: types.Message):
    logging.info('HELP command msg=%s', message.as_json())
    # сформируем текст сообщения
    msg = text(
        'Запустить тест /start <номер_викторины>',
        'Результаты теста /results <номер_теста>',
        'Могу повторить данную справку /help',
        sep='\n')
    # ответим подготовленным текстом
    await message.reply(msg)


# если не подошел ни один из предыдущих обработчиков
@dp.message_handler(content_types=types.ContentType.ANY)
async def unknown_message(message: types.Message):
    logging.info('Unknown command msg=%s', message.as_json())
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
    # загрузим демо викторину
    await parse_quiz(quiz_example.quiz_trigo_example)
    asyncio.create_task(scheduler())


# Обработчик завершения работы
async def shutdown(_):
    # завершающие процедуры
    logging.info('Завершение работы бота!')


if __name__ == '__main__':
    # начать опрос API Telegram
    executor.start_polling(
        dp, on_startup=startup,
        on_shutdown=shutdown,
        skip_updates=True)  # пропускать сообщения при остановленном
