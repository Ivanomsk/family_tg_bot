import asyncio
import os
from dotenv import load_dotenv
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

async def clear():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
    await bot.delete_my_commands()
    print("✅ Кнопка 'Меню' успешно удалена из кэша Telegram!")
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(clear())
