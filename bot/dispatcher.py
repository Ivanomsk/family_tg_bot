from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.client.default import DefaultBotProperties
from bot.config import BOT_TOKEN

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
dp = Dispatcher()

async def set_commands_global():
    commands = [
        BotCommand(command="start", description="🚀 Запустить бота / Получить справку"),
    ]
    await bot.set_my_commands(commands)
