from telegram.ext import (
    CallbackContext,
    ContextTypes,
    ApplicationBuilder,
    ExtBot,
)

from bot.ephimeral_patch.EphemeralBot import EphemeralExtBot

class EphemeralContext(CallbackContext[EphemeralExtBot, dict, dict, dict]):
    pass

EphemeralContextTypes = ContextTypes[
    EphemeralContext,
    dict,
    dict,
    dict
]