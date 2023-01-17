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
import quiz


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
async def quiz(message: types.Message):
    # logging.debug('QUIZ request userid={}'.format(userid))
    msg = await bot.send_poll(chat_id=message.chat.id, question="question?",
                                options=['1', '2', '3'],
                                is_anonymous=False,
                                type="quiz",
                                protect_content=True,
                                correct_option_id = 0)
    # async def send_poll(self,
    #                     chat_id: typing.Union[base.Integer, base.String],
    #                     question: base.String,
    #                     options: typing.List[base.String],
    #                     is_anonymous: typing.Optional[base.Boolean] = None,
    #                     type: typing.Optional[base.String] = None,
    #                     allows_multiple_answers: typing.Optional[base.Boolean] = None,
    #                     correct_option_id: typing.Optional[base.Integer] = None,
    #                     explanation: typing.Optional[base.String] = None,
    #                     explanation_parse_mode: typing.Optional[base.String] = None,
    #                     explanation_entities: typing.Optional[typing.List[types.MessageEntity]] = None,
    #                     open_period: typing.Optional[base.Integer] = None,
    #                     close_date: typing.Union[
    #                         base.Integer,
    #                         datetime.datetime,
    #                         datetime.timedelta,
    #                         None] = None,
    #                     is_closed: typing.Optional[base.Boolean] = None,
    #                     message_thread_id: typing.Optional[base.Integer] = None,
    #                     disable_notification: typing.Optional[base.Boolean] = None,
    #                     protect_content: typing.Optional[base.Boolean] = None,
    #                     reply_to_message_id: typing.Optional[base.Integer] = None,
    #                     allow_sending_without_reply: typing.Optional[base.Boolean] = None,
    #                     reply_markup: typing.Union[types.InlineKeyboardMarkup,
    #                     types.ReplyKeyboardMarkup,
    #                     types.ReplyKeyboardRemove,
    #                     types.ForceReply, None] = None,
    #                     )
    # await message.reply('Quiz.')


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
    executor.start_polling(dp, on_startup=startup, on_shutdown=shutdown, skip_updates=True)
