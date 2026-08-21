from typing import List, Dict, Any
from telegram import Bot
from telegram.ext import ContextTypes
from utils.log import log

async def set_bot_commands(bot: Bot, commands_data: List[Dict[str, Any]]) -> None:
    """_Registers all bot commands with custom API attributes in a single request._

    Args:
        bot (Bot): _The Telegram bot instance._
        commands_data (List[Dict[str, Any]]): _The list of command dictionaries containing command, description, and custom flags._
    """
    await bot._post(
        endpoint="setMyCommands",
        data={"commands": commands_data}
    )


async def initialize(context: ContextTypes.DEFAULT_TYPE) -> None:
    """_Post-initialization callback to register bot commands and log startup status._

    Args:
        context (ContextTypes.DEFAULT_TYPE): _The execution context provided by python-telegram-bot._
    """
    log("Setting up commands...")

    commands_list = [
        {
            "command": "series",
            "description": "Vedi gli eventi del gruppo",
            "is_ephemeral": True,
        },
        {
            "command": "newserie",
            "description": "ADMIN: Crea un nuovo evento",
        },
    ]

    await set_bot_commands(context.bot, commands_list)

    bot_info = await context.bot.get_me()
    log(f"Bot online at: https://t.me/{bot_info.username}")