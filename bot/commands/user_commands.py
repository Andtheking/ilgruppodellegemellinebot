from telegram import Update
from telegram.ext import ContextTypes
from models.models import User
from services.anilist_manager import verify_anilist_user


async def set_anilist_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """_Links or updates the caller's AniList username in the database with validation._

    Args:
        update (Update): _The incoming Telegram update._
        context (ContextTypes.DEFAULT_TYPE): _The execution context._
    """
    if not update.effective_user or not update.effective_message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    user_tg = update.effective_user
    args = context.args

    # Gestione parametri effimeri se il comando viene invocato in un gruppo
    raw_dict = update.effective_message.to_dict()
    ephemeral_id = raw_dict.get("ephemeral_message_id")
    extra_params = {"receiver_user_id": user_tg.id}
    if ephemeral_id:
        extra_params["reply_parameters"] = {"ephemeral_message_id": ephemeral_id}

    if not args:
        help_text = (
            "ℹ️ <b>Come collegare il tuo account AniList:</b>\n\n"
            "Usa il comando specificando il tuo username:\n"
            "<code>/setanilist TuoUsername</code>\n\n"
            "<i>Serve per tracciare automaticamente gli episodi che hai già visto!</i>"
        )
        await context.bot.send_message(
            chat_id=chat_id,
            text=help_text,
            parse_mode="HTML",
            api_kwargs=extra_params,
        )
        return

    input_username = args[0].strip()

    # Verifica l'esistenza su AniList
    canonical_username = verify_anilist_user(input_username)
    if not canonical_username:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ Utente AniList <b>{input_username}</b> non trovato. Controlla lo spelling e riprova.",
            parse_mode="HTML",
            api_kwargs=extra_params,
        )
        return

    # Salva o aggiorna l'utente nel DB
    user, _ = User.get_by_id(user_tg.id)
    user: User
    user.anilist_username = canonical_username
    if user_tg.username:
        user.username = user_tg.username
    user.save()

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"✅ Account AniList collegato con successo!\n\n"
            f"👤 <b>Profilo:</b> <a href=\"https://anilist.co/user/{canonical_username}\">{canonical_username}</a>"
        ),
        parse_mode="HTML",
        api_kwargs=extra_params,
    )