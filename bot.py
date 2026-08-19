from telegram import Update
from telegram.ext import (
    Application,
    ContextTypes, 
    ConversationHandler,
    MessageHandler, 
    filters
)
import re

from config import config
from utils.log import log

from commands.admin import addAdmin, removeAdmin
from commands.doAlways import middleware
from jobs.initialize import initialize
from jobs.send_logs import send_logs_channel

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
    return filters.Regex(re.compile(rf"^[!.\/]{command}(?P<botSignature>@{config.BOT_USERNAME})?{'( ' + other + ')?' if other is not None else ''}{'$' if strict else ''}",re.IGNORECASE))

def main():
    application = Application.builder().token(config.TOKEN).build() 

    handlers = {
        "start": MessageHandler(message_handler_as_command('start'),middleware(start)),
        "help": MessageHandler(message_handler_as_command('help'),middleware(help)),
        "addAdmin": MessageHandler(message_handler_as_command('addAdmin','(?P<candidate>.+)?'), middleware(addAdmin)),
        "removeAdmin": MessageHandler(message_handler_as_command('removeAdmin','(?P<candidate>.+)?'), middleware(removeAdmin))
    }
    
    for v in handlers.values():
        application.add_handler(v,0)
    
    application.add_handler(MessageHandler(filters=filters.ALL, callback=middleware()),1)
    
    application.add_error_handler(error)
    
    jq = application.job_queue

    if (config.CANALE_LOG):
        jq.run_repeating(
            callback=send_logs_channel,
            interval=60
        )

    jq.run_once(
        callback = initialize,
        when = 1
    )
    
    application.run_polling()
    
if __name__ == '__main__':
    main()