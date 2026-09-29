from telegram import Update
from telegram.ext import ContextTypes
from models.models import User
from services.anilist_manager import verify_anilist_user
from bot.ephimeral_patch.EphemeralUtils import build_ephemeral_reply_context
from bot.ephimeral_patch.EphemeralContext import EphemeralContext

async def set_anilist_command(update: Update, context: EphemeralContext) -> None:
    """_Links or updates the caller's AniList username in the database with validation._

    Args:
        update (Update): _The incoming Telegram update._
        context (ContextTypes.DEFAULT_TYPE): _The execution context._
    """
    if not update.effective_user or not update.effective_message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    user_tg = update.effective_user
    anilist_username = context.match.groupdict().get('profile', None)

    eph, repl = build_ephemeral_reply_context(update)

    if not anilist_username:
        help_text = (
            "ℹ️ <b>Come collegare il tuo account AniList:</b>\n\n"
            "Usa il comando specificando il tuo username:\n"
            "<code>/set_anilist TuoUsername</code>\n\n"
            "<i>Serve per tracciare automaticamente gli episodi che hai già visto!</i>"
        )
        await context.bot.send_ephemeral_message(
            chat_id=chat_id,
            text=help_text,
            parse_mode="HTML",
            ephemeral_parameters=eph,
            reply_parameters=repl
        )
        return

    input_username = anilist_username.strip()

    # Verifica l'esistenza su AniList
    canonical_username = verify_anilist_user(input_username)
    if not canonical_username:
        await context.bot.send_ephemeral_message(
            chat_id=chat_id,
            text=f"⚠️ Utente AniList <b>{input_username}</b> non trovato. Controlla lo spelling e riprova.",
            parse_mode="HTML",
            ephemeral_parameters=eph,
            reply_parameters=repl
        )
        return

    # Salva o aggiorna l'utente nel DB
    user = User.get_by_id(user_tg.id)
    user: User
    user.anilist_username = canonical_username
    if user_tg.username:
        user.username = user_tg.username
    user.save()

    await context.bot.send_ephemeral_message(
        chat_id=chat_id,
        text=(
            f"✅ Account AniList collegato con successo!\n\n"
            f"👤 <b>Profilo:</b> <a href=\"https://anilist.co/user/{canonical_username}\">{canonical_username}</a>"
        ),
        parse_mode="HTML",
        ephemeral_parameters=eph,
        reply_parameters=repl
    )