import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
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
from bot.commands.set_anilist import set_anilist_command
from bot.jobs.reminder import check_reminders_job, daily_sync_job
from utils.log import log

from bot.commands.admin import add_admin, remove_admin
from bot.commands.do_always import middleware
from bot.commands.series_list import list_series_command, subscription_callback_handler
from bot.commands.event_sharing import handle_group_start, share_link_callback
from bot.jobs.initialize import initialize
from bot.jobs.send_logs import send_logs_channel

# TEMPORARY PATCH FOR EPHIMERAL MESSAGES
from bot.ephimeral_patch.EphemeralBot import EphemeralExtBot
from bot.ephimeral_patch.EphemeralContext import EphemeralContext, EphemeralContextTypes

from bot.commands.create_series import create_series_handler, new_serie_group_entry


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    testo = (
        "👋 <b>Ciao! Sono il bot dei Watchparty!</b> 🍿\n\n"
        "Sono stato creato per aiutarti a organizzare le visioni di gruppo: tengo traccia "
        "degli episodi, ti ricordo quando iniziare e mi sincronizzo con AniList.\n\n"
        "👇 <b>Da dove iniziamo?</b>\n"
        "Il mio habitat naturale sono i gruppi. Aggiungimi a una chat di gruppo per creare "
        "un palinsesto, oppure usa /help per scoprire di più."
    )
    
    tastiera = InlineKeyboardMarkup([[
        InlineKeyboardButton("➕ Aggiungimi a un gruppo", url=f"https://t.me/{bot_config.BOT_USERNAME}?startgroup=true")
    ]])
    
    await update.message.reply_text(text=testo, reply_markup=tastiera, parse_mode=ParseMode.HTML)

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Invia il messaggio di aiuto del bot."""
    help_text = (
        "🎬 <b>BENVENUTO NEL BOT DEI WATCHPARTY!</b>\n"
        "Gestisco i palinsesti, tengo traccia degli episodi e ti avviso quando è ora di premere play. 🍿\n\n"
        "👤 <b>COMANDI PER TUTTI</b>\n"
        "• /series — Mostra il palinsesto settimanale del gruppo diviso per giorni. Da qui puoi navigare tra le giornate e iscriverti (🔔) o disiscriverti (🔕) dai singoli eventi.\n"
        "• <code>/set_anilist &lt;nome_utente&gt;</code> — Collega il tuo account AniList per il tracciamento episodi.\n\n"
        "⚙️ <b>FUNZIONI PER GLI ADMIN</b>\n"
        "• <b>Condivisione:</b> Usando /series, vedrai un pulsante <b>🔗 Condividi</b> accanto agli eventi di proprietà del gruppo.\n\n"
        "🤝 <b>EVENTI CONDIVISI</b>\n"
        "Gli admin possono inviare il link di condivisione ad altri gruppi. Gli eventi ospitati saranno segnati con l'icona 🤝 nel palinsesto. L'avanzamento degli episodi rimane sincronizzato per tutti i gruppi partecipanti!\n\n"
        "🔔 I promemoria arriveranno in automatico, taggando chi è in pari 🟢 e chi è indietro 🟡.\n\n"
        "⚠️ Il bot è ancora in fase di sviluppo, per qualsiasi problema scrivi pure a @Andtheking."
    )
    
    await update.message.reply_text(
        text=help_text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )

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
    application = ApplicationBuilder().bot(EphemeralExtBot(bot_config.TOKEN)).context_types(ContextTypes(context=EphemeralContext)).build()
    
    handlers = {
        "start": CommandHandler("start", middleware(start), filters=~filters.Regex(r"share_") & ~filters.ChatType.GROUPS),
        "start_group": CommandHandler('start', middleware(handle_group_start), filters=filters.ChatType.GROUPS & filters.Regex(r"share_")),
        "help": CustomCommandHandler('help',middleware(help)),
        "addAdmin": CustomCommandHandler('addAdmin', other='(?P<candidate>.+)?', callback=middleware(add_admin)),
        "removeAdmin": CustomCommandHandler('removeAdmin', other='(?P<candidate>.+)?', callback=middleware(remove_admin)),
        "createSeriesPublic": CustomCommandHandler('newserie', callback=middleware(new_serie_group_entry)),
        "createSeriesPrivate": create_series_handler,
        "getSeries": CustomCommandHandler("series", callback=middleware(list_series_command)),
        "subCallback": CallbackQueryHandler(middleware(subscription_callback_handler), pattern=r"^(show_day|toggle_sub):"),
        "setAnilist": CustomCommandHandler("set_anilist", other="(?P<profile>.+)", callback=middleware(set_anilist_command)),
        "share_callback": CallbackQueryHandler(share_link_callback, pattern=r"^share_link:",),
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

    jq.run_once(daily_sync_job, when=1)
    jq.run_daily(daily_sync_job, time=datetime.time(hour=3, minute=0, second=0))
    
    application.run_polling()