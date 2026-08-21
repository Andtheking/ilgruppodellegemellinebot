import datetime

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes, 
    ConversationHandler,
    MessageHandler, 
    filters
)
import re

from bot.CustomCommandHandler import CustomCommandHandler
from bot.bot_config import bot_config
from bot.jobs.reminder import check_reminders_job, daily_sync_job
from utils.log import log

from bot.commands.admin import add_admin, remove_admin
from bot.commands.do_always import middleware
from bot.commands.subscription import list_series_command, subscription_callback_handler
from bot.jobs.initialize import initialize
from bot.jobs.send_logs import send_logs_channel

from bot.commands.create_series import create_series_handler


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f'Hai avviato il bot, congrats')

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("aiuto")

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log(f'Update "{update}" caused error "{context.error}"',context.bot, "error")

def cancel(action: str): 
    async def thing(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.effective_message.reply_text(f"Ok, azione \"{action}\" annullata")
        return ConversationHandler.END
    return thing

def message_handler_as_command(command, other=None, strict=True):
    return filters.Regex(re.compile(rf"^[!.\/]{command}(?P<botSignature>@{bot_config.BOT_USERNAME})?{'( ' + other + ')?' if other is not None else ''}{'$' if strict else ''}",re.IGNORECASE))


def start_bot():
    application = Application.builder().token(bot_config.TOKEN).build()
    
    handlers = {
        "start": CustomCommandHandler('start', middleware(start)),
        "help": CustomCommandHandler('help',middleware(help)),
        "addAdmin": CustomCommandHandler('addAdmin', other='(?P<candidate>.+)?', callback=middleware(add_admin)),
        "removeAdmin": CustomCommandHandler('removeAdmin', other='(?P<candidate>.+)?', callback=middleware(remove_admin)),
        "createSeries": create_series_handler,
        "getSeries": CustomCommandHandler("series", callback=middleware(list_series_command)),
        "subCallback": CallbackQueryHandler(middleware(subscription_callback_handler), pattern="^toggle_sub:"),
    }
    
    for v in handlers.values():
        application.add_handler(v,0)
    
    application.add_handler(MessageHandler(filters=filters.ALL, callback=middleware()),1)
    
    application.add_error_handler(error)
    
    jq = application.job_queue

    if (bot_config.CANALE_LOG):
        jq.run_repeating(
            callback=send_logs_channel,
            interval=60
        )

    jq.run_once(callback = initialize, when = 1)

    jq.run_repeating(check_reminders_job, interval=60, first=10)

    jq.run_once(daily_sync_job, when=10)
    jq.run_daily(daily_sync_job, time=datetime.time(hour=3, minute=0, second=0))
    
    application.run_polling()