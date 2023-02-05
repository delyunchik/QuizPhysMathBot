import config
import logging
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


@dp.message_handler(commands=['quiz'])
async def command_quiz(message: types.Message):
    # logging.debug('QUIZ request userid={}'.format(userid))
    n = (len(quiz)-1) // 4  # число вопросов
    close_dt = datetime.now() + timedelta(minutes=int(quiz[0]))
    for i in range(n):
        msg = await bot.send_message(
            chat_id=message.chat.id,
            text='[{}/{}] {}'.format(i+1, n, quiz[i*4+1]),
        )
        msg = await bot.send_photo(
            chat_id=message.chat.id,
            photo=formula(quiz[i*4+2]),
        )
        q = quiz[i*4+4].count('\n')+1  # число ответов
        msg = await bot.send_photo(
            chat_id=message.chat.id,
            photo=formula(quiz[i*4+4]),
        )
        msg = await bot.send_poll(
            chat_id=message.chat.id,
            question='Выберите номер ответа:',
            options=[str(j+1) for j in range(q)],
            is_anonymous=False,
            type='quiz',
            close_date=close_dt,
            protect_content=True,
            correct_option_id=quiz[i*4+3]-1,
        )
    logging.info('i={} msg={}'.format(i, msg.as_json()))


@dp.poll_answer_handler()
async def handle_poll_answer(quiz_answer: types.PollAnswer):
    """
    Это хендлер на новые ответы в опросах (Poll) и викторинах (Quiz)
    Реагирует на изменение голоса. В случае отзыва голоса тоже срабатывает!

    Чтобы не было путаницы:
    * quiz_answer - ответ на активную викторину
    * saved_quiz - викторина, находящаяся в нашем "хранилище" в памяти

    :param quiz_answer: объект PollAnswer с информацией о голосующем
    """
    logging.info(quiz_answer.as_json())


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


# Обработчик начала работы бота
async def startup(_):
    logging.info('Старт работы бота!')


# Обработчик завершения работы
async def shutdown(dispatcher: Dispatcher):
    # завершающие процедуры
    logging.info('Завершение работы бота!')


if __name__ == '__main__':
    # начать опрос API Telegram
    executor.start_polling(
        dp, on_startup=startup,
        on_shutdown=shutdown,
        skip_updates=True)
