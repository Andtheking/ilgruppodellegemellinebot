import html
from typing import List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from models.models import User, EventSerie
from services.subscribe_to_eventseries import (
    force_subscribe_user,
    force_unsubscribe_user,
    search_active_series_for_chat,
)
from bot.utils.checks import is_user_groupadmin


async def force_sub_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """_Allows administrators to manually subscribe a user to an event series._"""
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat:
        return

    if not await is_user_groupadmin(update, context):
        await message.reply_text("⛔ Solo gli amministratori possono usare questo comando.")
        return

    target_user_id: Optional[int] = None
    target_user_name: Optional[str] = None
    args = context.args
    if args is None:
        raw_text = message.text or ""
        tokens = raw_text.split()
        args = tokens[1:] if len(tokens) > 1 else []

    if message.reply_to_message and message.reply_to_message.from_user:
        replied_user = message.reply_to_message.from_user
        target_user_id = replied_user.id
        target_user_name = replied_user.name
        series_query = " ".join(args).strip()
    else:
        if not args:
            await message.reply_text(
                "ℹ️ <b>Uso del comando:</b>\n\n"
                "• In risposta a un messaggio dell'utente:\n"
                "  <code>/force_sub [NomeSerie]</code>\n\n"
                "• Oppure specificando l'utente:\n"
                "  <code>/force_sub NomeSerie @username</code>\n"
                "  <code>/force_sub NomeSerie 123456789</code>",
                parse_mode="HTML"
            )
            return

        candidate = args[-1]
        other_tokens = args[:-1]

        if (args[0].startswith("@") or args[0].isdigit()) and len(args) > 1:
            candidate = args[0]
            other_tokens = args[1:]

        clean_candidate = candidate.lstrip("@")
        db_user = None
        if candidate.isdigit():
            db_user = User.get_or_none(User.id == int(candidate))
        if not db_user:
            db_user = User.get_or_none(
                (User.username == candidate) |
                (User.username == f"@{clean_candidate}") |
                (User.username == clean_candidate)
            )

        if not db_user:
            await message.reply_text(
                f"⚠️ Non ho trovato l'utente <b>{html.escape(candidate)}</b> nel database.\n"
                "Assicurati che abbia già inviato almeno un messaggio nel gruppo, oppure rispondi direttamente a un suo messaggio con <code>/force_sub</code>.",
                parse_mode="HTML"
            )
            return

        target_user_id = db_user.id
        target_user_name = db_user.username or f"ID {db_user.id}"
        series_query = " ".join(other_tokens).strip()

    active_series = search_active_series_for_chat(chat.id, series_query if series_query else None)

    if not active_series:
        if series_query:
            await message.reply_text(f"❌ Nessuna serie attiva trovata con il nome '<b>{html.escape(series_query)}</b>'.", parse_mode="HTML")
        else:
            await message.reply_text("❌ Non ci sono serie attive in questo gruppo.", parse_mode="HTML")
        return

    if len(active_series) == 1:
        serie = active_series[0]
        created, title = force_subscribe_user(target_user_id, serie.id)
        escaped_user = html.escape(target_user_name or f"ID {target_user_id}")
        escaped_title = html.escape(title)
        if created:
            await message.reply_text(
                f"✅ <b>{escaped_user}</b> è stato iscritto a <b>{escaped_title}</b>!",
                parse_mode="HTML"
            )
        else:
            await message.reply_text(
                f"ℹ️ <b>{escaped_user}</b> era già iscritto a <b>{escaped_title}</b>.",
                parse_mode="HTML"
            )
        return

    buttons = []
    for s in active_series:
        buttons.append([InlineKeyboardButton(f"🎬 {s.title}", callback_data=f"force_sub_pick:{s.id}:{target_user_id}")])

    await message.reply_text(
        f"🎯 Seleziona a quale serie vuoi iscrivere <b>{html.escape(target_user_name or f'ID {target_user_id}')}</b>:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="HTML"
    )


async def force_unsub_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """_Allows administrators to manually unsubscribe a user from an event series._"""
    message = update.effective_message
    chat = update.effective_chat
    if not message or not chat:
        return

    if not await is_user_groupadmin(update, context):
        await message.reply_text("⛔ Solo gli amministratori possono usare questo comando.")
        return

    target_user_id: Optional[int] = None
    target_user_name: Optional[str] = None
    args = context.args
    if args is None:
        raw_text = message.text or ""
        tokens = raw_text.split()
        args = tokens[1:] if len(tokens) > 1 else []

    if message.reply_to_message and message.reply_to_message.from_user:
        replied_user = message.reply_to_message.from_user
        target_user_id = replied_user.id
        target_user_name = replied_user.name
        series_query = " ".join(args).strip()
    else:
        if not args:
            await message.reply_text(
                "ℹ️ <b>Uso del comando:</b>\n\n"
                "• In risposta a un messaggio dell'utente:\n"
                "  <code>/force_unsub [NomeSerie]</code>\n\n"
                "• Oppure specificando l'utente:\n"
                "  <code>/force_unsub NomeSerie @username</code>\n"
                "  <code>/force_unsub NomeSerie 123456789</code>",
                parse_mode="HTML"
            )
            return

        candidate = args[-1]
        other_tokens = args[:-1]

        if (args[0].startswith("@") or args[0].isdigit()) and len(args) > 1:
            candidate = args[0]
            other_tokens = args[1:]

        clean_candidate = candidate.lstrip("@")
        db_user = None
        if candidate.isdigit():
            db_user = User.get_or_none(User.id == int(candidate))
        if not db_user:
            db_user = User.get_or_none(
                (User.username == candidate) |
                (User.username == f"@{clean_candidate}") |
                (User.username == clean_candidate)
            )

        if not db_user:
            await message.reply_text(
                f"⚠️ Non ho trovato l'utente <b>{html.escape(candidate)}</b> nel database.",
                parse_mode="HTML"
            )
            return

        target_user_id = db_user.id
        target_user_name = db_user.username or f"ID {db_user.id}"
        series_query = " ".join(other_tokens).strip()

    active_series = search_active_series_for_chat(chat.id, series_query if series_query else None)

    if not active_series:
        if series_query:
            await message.reply_text(f"❌ Nessuna serie attiva trovata con il nome '<b>{html.escape(series_query)}</b>'.", parse_mode="HTML")
        else:
            await message.reply_text("❌ Non ci sono serie attive in questo gruppo.", parse_mode="HTML")
        return

    if len(active_series) == 1:
        serie = active_series[0]
        removed, title = force_unsubscribe_user(target_user_id, serie.id)
        escaped_user = html.escape(target_user_name or f"ID {target_user_id}")
        escaped_title = html.escape(title)
        if removed:
            await message.reply_text(
                f"✅ <b>{escaped_user}</b> è stato disiscritto da <b>{escaped_title}</b>.",
                parse_mode="HTML"
            )
        else:
            await message.reply_text(
                f"ℹ️ <b>{escaped_user}</b> non era iscritto a <b>{escaped_title}</b>.",
                parse_mode="HTML"
            )
        return

    buttons = []
    for s in active_series:
        buttons.append([InlineKeyboardButton(f"🎬 {s.title}", callback_data=f"force_unsub_pick:{s.id}:{target_user_id}")])

    await message.reply_text(
        f"🎯 Seleziona da quale serie vuoi disiscrivere <b>{html.escape(target_user_name or f'ID {target_user_id}')}</b>:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="HTML"
    )


async def force_sub_pick_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """_Handles interactive series selection for manual subscription or unsubscription._"""
    query = update.callback_query
    if not query or not update.effective_user or not update.effective_chat:
        return

    if not await is_user_groupadmin(update, context):
        await query.answer("Solo gli amministratori possono eseguire questa azione.", show_alert=True)
        return

    action, serie_id_str, user_id_str = query.data.split(":")
    serie_id = int(serie_id_str)
    target_user_id = int(user_id_str)

    user = User.get_or_none(User.id == target_user_id)
    name = user.username if user and user.username else f"ID {target_user_id}"
    escaped_user = html.escape(name)

    if action == "force_sub_pick":
        created, title = force_subscribe_user(target_user_id, serie_id)
        escaped_title = html.escape(title)
        if created:
            text = f"✅ <b>{escaped_user}</b> è stato iscritto a <b>{escaped_title}</b>!"
        else:
            text = f"ℹ️ <b>{escaped_user}</b> era già iscritto a <b>{escaped_title}</b>."
    else:
        removed, title = force_unsubscribe_user(target_user_id, serie_id)
        escaped_title = html.escape(title)
        if removed:
            text = f"✅ <b>{escaped_user}</b> è stato disiscritto da <b>{escaped_title}</b>."
        else:
            text = f"ℹ️ <b>{escaped_user}</b> non era iscritto a <b>{escaped_title}</b>."

    await query.answer()
    await query.edit_message_text(text=text, parse_mode="HTML")
