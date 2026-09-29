from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatType, ParseMode
from bot.bot_config import bot_config
from bot.ephimeral_patch.EphemeralContext import EphemeralContext
from models.models import EventSerie, SharedEventSerie
from bot.utils.checks import is_user_groupadmin
from bot.ephimeral_patch.EphemeralUtils import build_ephemeral_reply_context

async def handle_group_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gestisce il payload /start quando il bot viene aggiunto a un nuovo gruppo tramite deep link."""
    # Assicuriamoci che sia un gruppo
    if update.effective_chat.type == ChatType.PRIVATE:
        return

    args = context.args
    if not args or not args[0].startswith("share_"):
        return # Non è un link di condivisione, ignoriamo o gestiamo il /start normale

    if not await is_user_groupadmin(update, context):
        await update.message.reply_text("⛔ Solo un admin di questo gruppo può accettare l'invito a una serie condivisa.")
        return

    try:
        serie_id = int(args[0].replace("share_", ""))
    except ValueError:
        return

    serie = EventSerie.get_or_none(EventSerie.id == serie_id)
    if not serie:
        await update.message.reply_text("❌ La serie che stai cercando di importare non esiste più.")
        return

    chat_id = update.effective_chat.id
    
    # Se il gruppo prova ad autoinvitarsi alla propria serie
    if serie.chat_id == chat_id:
        await update.message.reply_text("Questo gruppo è già il proprietario originale della serie!")
        return

    # FIXME: export service
    SharedEventSerie.get_or_create(
        event_serie=serie,
        chat=chat_id
    )

    await update.message.reply_text(
        f"🤝 <b>Serie Condivisa Collegata!</b>\n\n"
        f"Gli eventi di <b>{serie.title}</b> appariranno ora nel palinsesto di questo gruppo.\n"
        f"I membri possono iscriversi usando /series.",
        parse_mode="HTML"
    )

async def share_link_callback(update: Update, context: EphemeralContext) -> None:
    """Intercetta il pulsante di condivisione e risponde con il link da copiare in effimero."""
    query = update.callback_query
    if not query or not update.effective_user or not update.effective_chat:
        return

    await query.answer()

    try:
        serie_id = int(query.data.split(":")[1])
    except (IndexError, ValueError):
        return

    serie = EventSerie.get_or_none(EventSerie.id == serie_id)
    if not serie:
        return

    deep_link = f"https://t.me/{bot_config.BOT_USERNAME}?startgroup=share_{serie.id}"

    text = (
        f"🔗 <b>Ecco il link di condivisione!</b>\n\n"
        f"Per condividere <b>{serie.title}</b>, copia il link qui sotto e invialo all'admin dell'altro gruppo:\n\n"
        f"<code>{deep_link}</code>\n\n"
        f"<i>L'admin dovrà cliccarlo dal suo dispositivo per aggiungere l'evento al suo gruppo.</i>"
    )

    eph, repl = build_ephemeral_reply_context(update)
    await context.bot.send_ephemeral_message(
        chat_id=update.effective_chat.id,
        text=text,
        parse_mode=ParseMode.HTML,
        ephemeral_parameters=eph,
        reply_parameters=repl
    )

