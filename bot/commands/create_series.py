import datetime
from typing import Dict
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
import telegram
from telegram.constants import ChatType
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
)
from bot.CustomCommandHandler import CustomCommandHandler
from bot.commands.do_always import middleware
from bot.utils.constants import DAYS
from bot.utils.checks import is_user_groupadmin
from models.models import AnilistAnime, Chat
from services.anilist_manager import fetch_anime_info_by_id
from services.eventseries_manager import create_series_with_events
from bot.bot_config import bot_config

# conversation steps
(
    ASK_TITLE,
    ASK_ANILIST_ID,
    ASK_START_EPISODE,
    ASK_DAY_OF_WEEK,
    ASK_EVENT_TIME,
    ASK_REMIND_TIME,
    ASK_START_DATE,
    ASK_END_DATE,
) = range(8)


from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from bot.utils.checks import is_user_groupadmin


async def new_serie_group_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_user_groupadmin(update, context):
        return

    chat_id = update.effective_chat.id
    deep_link = f"https://t.me/{bot_config.BOT_USERNAME}?start=newserie_{chat_id}"

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("⚙️ Avvia configurazione in privato", url=deep_link)
    ]])

    raw_dict = update.effective_message.to_dict()
    ephemeral_id = raw_dict.get("ephemeral_message_id")
    extra_params = {"receiver_user_id": update.effective_user.id}
    if ephemeral_id:
        extra_params["reply_parameters"] = {"ephemeral_message_id": ephemeral_id}

    await context.bot.send_message(
        chat_id=chat_id,
        text="🎬 Per creare una nuova serie ed evitare spam nel gruppo, proseguiamo in chat privata:",
        reply_markup=keyboard,
        api_kwargs=extra_params
    )


async def start_new_serie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inizio wizard: verifica admin e chiede il titolo."""

    if update.effective_chat.type != ChatType.PRIVATE:
        return ConversationHandler.END

    args = context.args  # Contiene ['newserie_-10012345678']
    if not args or not args[0].startswith("newserie_"):
        return ConversationHandler.END

    group_chat_id = int(args[0].replace("newserie_", ""))

    context.user_data.clear()
    context.user_data["new_serie"] = {"chat_id": group_chat_id}

    await update.message.reply_text(
        f"🗓️ <b>Creazione nuova Serie di Eventi</b> per il gruppo <i><b>{Chat.get_by_id(group_chat_id).title}</b></i>\n\n"
        "Inserisci il <b>titolo</b> della serie (es. <i>🎬 Watchparty Yani Neko</i>):\n"
        "(Scrivi /cancel per annullare in qualsiasi momento)",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )
    return ASK_TITLE


async def set_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    title = update.message.text.strip()
    if not title:
        await update.message.reply_text("Il titolo non può essere vuoto. Riprova:")
        return ASK_TITLE

    context.user_data["new_serie"]["title"] = update.message.text.strip()

    await update.message.reply_text(
        "🔗 Inserisci l'<b>ID AniList</b> (o il link dell'anime su AniList).\n"
        "<i>Invia /skip se non vuoi collegarlo ad AniList.</i>",
        parse_mode="HTML"
    )
    return ASK_ANILIST_ID

async def serie_anilist_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    input_text = update.message.text.strip()
    parsed_id = input_text.strip()

    if not parsed_id:
        await update.message.reply_text("⚠️ ID non valido. Invia un ID numerico o scrivi /skip:")
        return ASK_ANILIST_ID

    anime_data = fetch_anime_info_by_id(parsed_id)
    if not anime_data:
        await update.message.reply_text("⚠️ Anime non trovato su AniList. Riprova o scrivi /skip:")
        return ASK_ANILIST_ID

    # FIXME: export service
    anime_record, _ = AnilistAnime.get_or_create(
        anilist_media_id=anime_data["anilist_id"],
        defaults={
            "total_episodes": anime_data["total_episodes"],
            "cover_image_url": anime_data["cover_image"],
        }
    )
    context.user_data["new_serie"]["anilist_anime"] = anime_record

    await update.message.reply_text(
        f"✅ Trovato: <b>{anime_data['title']}</b>. Da quale <b>episodio</b> si parte? (Default: <code>1</code>)\n"
        "<i>Invia il numero o scrivi /skip per partire da 1:</i>",
        parse_mode="HTML"
    )
    return ASK_START_EPISODE


async def serie_anilist_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["new_serie"]["anilist_anime"] = None

    await update.message.reply_text(
        "✅ Trovato: <b>{anime_data['title']}</b>. Da quale <b>episodio</b> si parte? (Default: <code>1</code>)\n"
        "<i>Invia il numero o scrivi /skip per partire da 1:</i>",
        parse_mode="HTML"
    )
    return ASK_START_EPISODE


async def set_start_episode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """_Saves starting episode and finalizes series creation._"""
    if not update.message or not update.message.text:
        return ASK_START_EPISODE

    raw_input = update.message.text.strip()
    try:
        current_ep = max(1, int(raw_input))
    except ValueError:
        await update.message.reply_text("⚠️ Inserisci un numero intero valido (es. <code>1</code>) oppure /skip:")
        return ASK_START_EPISODE

    context.user_data["new_serie"]["current_episode"] = current_ep

    keyboard = [DAYS[:3], DAYS[3:5], DAYS[5:]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    await update.message.reply_text(
        f"In quale <b>giorno della settimana</b> si terrà l'evento?",
        parse_mode="HTML",
        reply_markup=reply_markup
    )
    return ASK_DAY_OF_WEEK


async def skip_start_episode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """_Defaults starting episode to 1 and finalizes series creation._"""

    keyboard = [DAYS[:3], DAYS[3:5], DAYS[5:]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        f"Va bene, inizierà dall'episodio 1. In quale <b>giorno della settimana</b> si terrà l'evento?",
        parse_mode="HTML",
        reply_markup=reply_markup
    )
    return ASK_DAY_OF_WEEK


async def set_day_of_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    day_text = update.message.text.strip().capitalize()
    if day_text not in DAYS:
        await update.message.reply_text("Giorno non valido. Selezionalo dalla tastiera sotto:")
        return ASK_DAY_OF_WEEK

    context.user_data["new_serie"]["day_of_week"] = DAYS.index(day_text)

    await update.message.reply_text(
        f"Giorno: <b>{day_text}</b>\n\nA che <b>orario</b> inizia l'evento? (Formato HH:MM, es. <code>21:30</code>)",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )
    
    return ASK_EVENT_TIME


async def set_event_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        parsed_time = datetime.datetime.strptime(update.message.text.strip(), "%H:%M").time()
        context.user_data["new_serie"]["event_time"] = parsed_time
    except ValueError:
        await update.message.reply_text("Formato orario non valido. Usa HH:MM (es. <code>21:30</code>):", parse_mode="HTML")
        return ASK_EVENT_TIME

    await update.message.reply_text(
        f"Orario inizio: <b>{parsed_time.strftime('%H:%M')}</b>\n\n"
        "A che ora deve scattare il <b>promemoria/tag</b>? (Formato HH:MM, es. <code>20:30</code>)",
        parse_mode="HTML"
    )
    return ASK_REMIND_TIME


async def set_remind_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        parsed_time = datetime.datetime.strptime(update.message.text.strip(), "%H:%M").time()
        context.user_data["new_serie"]["remind_time"] = parsed_time
    except ValueError:
        await update.message.reply_text("Formato orario non valido. Usa HH:MM (es. <code>20:30</code>):", parse_mode="HTML")
        return ASK_REMIND_TIME

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    await update.message.reply_text(
        f"Promemoria: <b>{parsed_time.strftime('%H:%M')}</b>\n\n"
        f"Da quale <b>data di inizio</b> deve partire la serie? (Formato YYYY-MM-DD, es. <code>{today_str}</code>)",
        parse_mode="HTML"
    )
    return ASK_START_DATE


async def set_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        parsed_date = datetime.datetime.strptime(update.message.text.strip(), "%Y-%m-%d").date()
        context.user_data["new_serie"]["start_date"] = parsed_date
    except ValueError:
        await update.message.reply_text("Formato data non valido. Usa YYYY-MM-DD (es. <code>2026-09-01</code>):", parse_mode="HTML")
        return ASK_START_DATE

    await update.message.reply_text(
        f"Data inizio: <b>{parsed_date.strftime('%Y-%m-%d')}</b>\n\n"
        "Fino a quale <b>data di fine</b> deve durare la serie? (Formato YYYY-MM-DD)",
        parse_mode="HTML"
    )
    return ASK_END_DATE


async def set_end_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw_input = update.message.text.strip().lower()
    end_date = None

    try:
        end_date = datetime.datetime.strptime(raw_input, "%Y-%m-%d").date()
        if end_date < context.user_data["new_serie"]["start_date"]:
            await update.message.reply_text("La data di fine non può essere precedente alla data di inizio. Riprova:")
            return ASK_END_DATE
    except ValueError:
        await update.message.reply_text("Formato data non valido. Usa YYYY-MM-DD oppure scrivi <code>nessuna</code>:", parse_mode="HTML")
        return ASK_END_DATE

    data: Dict = context.user_data["new_serie"]

    serie, eventi_creati = create_series_with_events(
        chat_id=data["chat_id"],
        title=data["title"],
        event_time=data["event_time"],
        remind_time=data["remind_time"],
        day_of_week=data["day_of_week"],
        start_date=data["start_date"],
        end_date=end_date,
        anilist_anime=data.get("anilist_anime"),
        current_episode=data.get("current_episode", 1),
    )

    context.user_data.clear()

    end_date_str = end_date.strftime('%Y-%m-%d')
    anilist_str = f"\n🔗 <b>AniList:</b> Collegato" if serie.anilist_anime else ""
    ep_str = f"\n🔢 <b>Episodio di partenza:</b> {serie.current_episode}"
    
    await update.message.reply_text(
        f"✅ <b>Serie Creata con Successo!</b>\n\n"
        f"📌 <b>Titolo:</b> {serie.title}\n"
        f"⏰ <b>Orario:</b> {serie.default_event_time.strftime('%H:%M')} (Notifica: {serie.default_remind_time.strftime('%H:%M')})\n"
        f"📅 <b>Periodo:</b> {serie.start_date.strftime('%Y-%m-%d')} ➜ {end_date_str}"
        f"{ep_str}"
        f"{anilist_str}\n\n"
        f"🚀 <i>Generati subito {eventi_creati} appuntamenti nel calendario!</i>",
        parse_mode="HTML"
    )
    return ConversationHandler.END


async def cancel_creation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Annulla la creazione guidata."""
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Creazione della serie annullata.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


import re

create_series_handler = ConversationHandler(
    entry_points=[
        # Si avvia solo in chat privata quando si clicca sul link generato dal gruppo
        CommandHandler(
            "start",
            middleware(start_new_serie),
            filters=filters.ChatType.PRIVATE & filters.Regex(r"^/start newserie_"),
        )
    ],
    states={
        ASK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, middleware(set_title))],
        ASK_ANILIST_ID: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, middleware(serie_anilist_received)),
            CommandHandler("skip", middleware(serie_anilist_skip)),
        ],
        ASK_START_EPISODE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, middleware(set_start_episode)),
            CommandHandler("skip", middleware(skip_start_episode)),
        ],
        ASK_DAY_OF_WEEK: [MessageHandler(filters.TEXT & ~filters.COMMAND, middleware(set_day_of_week))],
        ASK_EVENT_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, middleware(set_event_time))],
        ASK_REMIND_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, middleware(set_remind_time))],
        ASK_START_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, middleware(set_start_date))],
        ASK_END_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, middleware(set_end_date))],
    },
    fallbacks=[CommandHandler("cancel", cancel_creation)],
    allow_reentry=True,
)