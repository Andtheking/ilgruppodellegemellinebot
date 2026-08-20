from telegram._utils.defaultvalue import DEFAULT_TRUE
from telegram.ext import MessageHandler
from bot.bot_config import bot_config
import telegram.ext.filters as tgfilters
import re

class CustomCommandHandler(MessageHandler):
    def __init__(self, command, callback, block = DEFAULT_TRUE, other=None, strict=True):
        filters = tgfilters.Regex(re.compile(rf"^[!.\/]{command}(?P<botSignature>@{bot_config.BOT_USERNAME})?{'( ' + other + ')?' if other is not None else ''}{'$' if strict else ''}",re.IGNORECASE))
        super().__init__(filters, callback, block)