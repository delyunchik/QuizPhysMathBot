import config
import logging
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


# Настраиваем журналирование
logging.basicConfig(
    filename='TrigoTgBot.log',
    level=config.LOG_LEVEL,
    format='%(asctime)s [%(levelname)s] ' +
           '%(module)s - %(funcName)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    )


# Инициализация бота
bot = Bot(token=config.API_TOKEN, proxy=config.PROXY_URL)
dp = Dispatcher(bot)


# обработчик команды start
@dp.message_handler(commands=['start'])
async def process_start_command(message: types.Message):
    # ответим приветственным сообщением
    await message.reply('Привет!\nИспользуй /help, '
                        'чтобы узнать список доступных команд!',
                        reply_markup=ReplyKeyboardRemove())


# обработчик команды help
@dp.message_handler(commands=['help'])
async def process_help_command(message: types.Message):
    # сформируем текст сообщения
    msg = text(
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


async def startup(_):
    logging.info('Старт работы бота!')


# Обработчик завершения работы
async def shutdown(dispatcher: Dispatcher):
    # завершающие процедуры
    logging.info('Завершение работы бота!')


# начать опрос API Telegram
if __name__ == '__main__':
    executor.start_polling(dp, on_startup=startup, on_shutdown=shutdown, skip_updates=True)
