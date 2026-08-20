import datetime
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
from models.models import Chat, EventSerie
from services.actualevent_manager import populate_rolling_events_for_series
from services.eventseries_manager import create_series_with_events

# conversation steps
(
    ASK_TITLE,
    ASK_DAY_OF_WEEK,
    ASK_EVENT_TIME,
    ASK_REMIND_TIME,
    ASK_START_DATE,
    ASK_END_DATE,
) = range(6)

DAYS_MAP = {
    "Lunedì": 0,
    "Martedì": 1,
    "Mercoledì": 2,
    "Giovedì": 3,
    "Venerdì": 4,
    "Sabato": 5,
    "Domenica": 6,
}


async def is_user_groupadmin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Verifica se l'utente che lancia il comando è amministratore della chat."""
    
    member = await context.bot.get_chat_member(
        chat_id=update.effective_chat.id,
        user_id=update.effective_user.id
    )
    
    return member.status in (telegram.ChatMember.OWNER, telegram.ChatMember.ADMINISTRATOR)


async def start_new_serie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inizio wizard: verifica admin e chiede il titolo."""

    if update.effective_chat.type == ChatType.PRIVATE:
        await update.message.reply_text("Usa questo comando in un gruppo...")
        return ConversationHandler.END

    if not await is_user_groupadmin(update, context):
        await update.message.reply_text("⛔ Solo gli admin del gruppo possono creare nuovi eventi.")
        return ConversationHandler.END

    context.user_data["new_serie"] = {"chat_id": update.effective_chat.id}

    await update.message.reply_text(
        "🗓️ <b>Creazione nuova Serie di Eventi</b>\n\n"
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

    context.user_data["new_serie"]["title"] = title

    keyboard = [["Lunedì", "Martedì", "Mercoledì"], ["Giovedì", "Venerdì"], ["Sabato", "Domenica"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    await update.message.reply_text(
        f"Titolo impostato: <b>{title}</b>\n\nIn quale <b>giorno della settimana</b> si terrà l'evento?",
        parse_mode="HTML",
        reply_markup=reply_markup
    )
    return ASK_DAY_OF_WEEK


async def set_day_of_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    day_text = update.message.text.strip().capitalize()
    if day_text not in DAYS_MAP:
        await update.message.reply_text("Giorno non valido. Selezionalo dalla tastiera sotto:")
        return ASK_DAY_OF_WEEK

    context.user_data["new_serie"]["day_of_week"] = DAYS_MAP[day_text]

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
        "Fino a quale <b>data di fine</b> deve durare la serie? (Formato YYYY-MM-DD, oppure scrivi <code>nessuna</code> per durata indefinita)",
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

    data = context.user_data["new_serie"]

    serie, eventi_creati = create_series_with_events(
        chat_id=data["chat_id"],
        title=data["title"],
        default_event_time=data["event_time"],
        default_remind_time=data["remind_time"],
        day_of_week=data["day_of_week"],
        start_date=data["start_date"],
        end_date=end_date,
        is_active=True
    )

    context.user_data.clear()

    end_date_str = end_date.strftime('%Y-%m-%d')
    await update.message.reply_text(
        f"✅ <b>Serie Creata con Successo!</b>\n\n"
        f"📌 <b>Titolo:</b> {serie.title}\n"
        f"⏰ <b>Orario:</b> {serie.default_event_time.strftime('%H:%M')} (Notifica: {serie.default_remind_time.strftime('%H:%M')})\n"
        f"📅 <b>Periodo:</b> {serie.start_date.strftime('%Y-%m-%d')} ➜ {end_date_str}\n\n"
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


create_series_handler = ConversationHandler(
    entry_points=[CustomCommandHandler('newserie', middleware(start_new_serie))],
    states={
        ASK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, middleware(set_title))],
        ASK_DAY_OF_WEEK: [MessageHandler(filters.TEXT & ~filters.COMMAND, middleware(set_day_of_week))],
        ASK_EVENT_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, middleware(set_event_time))],
        ASK_REMIND_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, middleware(set_remind_time))],
        ASK_START_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, middleware(set_start_date))],
        ASK_END_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, middleware(set_end_date))],
    },
    fallbacks=[CommandHandler("cancel", cancel_creation)],
    allow_reentry=True,
)