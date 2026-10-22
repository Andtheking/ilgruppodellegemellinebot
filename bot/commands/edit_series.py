import datetime
import html
import re
import warnings
from typing import Dict, Tuple

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ChatType
from telegram.warnings import PTBUserWarning
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.commands.do_always import middleware
from bot.utils.constants import DAYS
from models.models import AnilistAnime, EventSerie
from services.anilist_manager import fetch_anime_info_by_id
from services.eventseries_manager import (
    update_series_anilist,
    update_series_end_date,
    update_series_episode,
    update_series_times,
    update_series_title,
)
from utils.log import log

warnings.filterwarnings("ignore", category=PTBUserWarning, message=".*per_message=False.*")

(
    SELECTING_FIELD,
    EDIT_TITLE,
    EDIT_EVENT_TIME,
    EDIT_REMIND_TIME,
    EDIT_EPISODE,
    EDIT_ANILIST,
    EDIT_END_DATE,
) = range(7)

DAYS_NAME = DAYS


def build_edit_dashboard(serie: EventSerie) -> Tuple[str, InlineKeyboardMarkup]:
    """_Builds the HTML overview and inline keyboard for editing a series._"""
    escaped_title = html.escape(serie.title)
    chat_title = html.escape(serie.chat.title or "Chat")
    time_str = serie.default_event_time.strftime("%H:%M")
    remind_str = serie.default_remind_time.strftime("%H:%M")
    day_name = DAYS_NAME[serie.day_of_week]

    tot_str = (
        f"/{serie.anilist_anime.total_episodes}"
        if serie.anilist_anime and serie.anilist_anime.total_episodes
        else ""
    )
    ep_str = f"Episodio {serie.current_episode}{tot_str}"

    if serie.anilist_anime:
        anilist_str = f'<a href="https://anilist.co/anime/{serie.anilist_anime.anilist_media_id}">Collegato (ID {serie.anilist_anime.anilist_media_id})</a>'
    else:
        anilist_str = "<i>Non collegato</i>"

    start_str = serie.start_date.strftime("%d/%m/%Y")
    end_str = serie.end_date.strftime("%d/%m/%Y") if serie.end_date else "<i>Nessuna</i>"

    text = (
        f"✏️ <b>PANNELLO MODIFICA SERIE</b>\n"
        f"🎬 <b>{escaped_title}</b> (Gruppo: <i>{chat_title}</i>)\n\n"
        f"• <b>Titolo:</b> {escaped_title}\n"
        f"• <b>Orario inizio:</b> <code>{time_str}</code>\n"
        f"• <b>Orario notifica:</b> <code>{remind_str}</code>\n"
        f"• <b>Cadenza:</b> Ogni {day_name}\n"
        f"• <b>Episodio attuale:</b> {ep_str}\n"
        f"• <b>AniList:</b> {anilist_str}\n"
        f"• <b>Periodo:</b> {start_str} ➜ {end_str}\n\n"
        f"👇 <i>Tocca un'opzione qui sotto per modificarla:</i>"
    )

    buttons = [
        [
            InlineKeyboardButton("📝 Titolo", callback_data="edit_field:title"),
            InlineKeyboardButton("⏰ Orari (Inizio/Notifica)", callback_data="edit_field:times"),
        ],
        [
            InlineKeyboardButton("🔢 Episodio attuale", callback_data="edit_field:episode"),
            InlineKeyboardButton("🔗 AniList", callback_data="edit_field:anilist"),
        ],
        [
            InlineKeyboardButton("📅 Data di fine", callback_data="edit_field:end_date"),
        ],
        [
            InlineKeyboardButton("🏁 Termina modifiche", callback_data="edit_field:done"),
        ],
    ]

    return text, InlineKeyboardMarkup(buttons)


async def send_or_edit_dashboard(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    serie: EventSerie,
    notice: str = ""
) -> None:
    """_Helper to display the updated dashboard to the user._"""
    text, reply_markup = build_edit_dashboard(serie)
    if notice:
        text = f"{notice}\n\n{text}"

    if update.callback_query and update.callback_query.message:
        try:
            await update.callback_query.edit_message_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            return
        except Exception:
            pass

    chat_id = update.effective_chat.id if update.effective_chat else None
    if chat_id:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )


async def start_edit_serie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """_Entry point for editing an event series via private deep link._"""
    if not update.effective_chat or update.effective_chat.type != ChatType.PRIVATE:
        return ConversationHandler.END

    args = context.args
    if not args or not args[0].startswith("editserie_"):
        return ConversationHandler.END

    try:
        serie_id = int(args[0].replace("editserie_", ""))
    except ValueError:
        return ConversationHandler.END

    serie = EventSerie.get_or_none(EventSerie.id == serie_id)
    if not serie:
        await update.message.reply_text("⚠️ Serie non trovata.")
        return ConversationHandler.END

    # Verify that the user is an admin of the owner chat
    try:
        member = await context.bot.get_chat_member(serie.chat_id, update.effective_user.id)
        if member.status not in ["creator", "administrator"]:
            await update.message.reply_text("⛔ Solo gli amministratori del gruppo proprietario possono modificare questa serie.")
            return ConversationHandler.END
    except Exception as error:
        log(f"Errore get_chat_member in start_edit_serie: {error}")
        await update.message.reply_text("⛔ Impossibile verificare i tuoi permessi nel gruppo.")
        return ConversationHandler.END

    context.user_data.clear()
    context.user_data["edit_serie"] = {"serie_id": serie.id, "chat_id": serie.chat_id}

    text, reply_markup = build_edit_dashboard(serie)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")
    return SELECTING_FIELD


async def edit_field_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """_Handles inline button clicks in the edit series dashboard._"""
    query = update.callback_query
    if not query:
        return SELECTING_FIELD

    field = query.data.split(":")[1]
    serie_id = context.user_data.get("edit_serie", {}).get("serie_id")
    serie = EventSerie.get_or_none(EventSerie.id == serie_id) if serie_id else None

    if not serie:
        await query.answer("Serie non trovata o sessione scaduta.", show_alert=True)
        return ConversationHandler.END

    if field == "done":
        await query.answer("Modifiche salvate!")
        escaped_title = html.escape(serie.title)
        await query.edit_message_text(
            f"🏁 <b>Modifiche completate!</b>\nLa serie <b>{escaped_title}</b> è aggiornata.",
            parse_mode="HTML"
        )
        context.user_data.clear()
        return ConversationHandler.END

    elif field == "title":
        await query.answer()
        await query.message.reply_text(
            "📝 Invia il <b>nuovo titolo</b> per la serie (oppure /cancel per annullare):",
            parse_mode="HTML"
        )
        return EDIT_TITLE

    elif field == "times":
        await query.answer()
        await query.message.reply_text(
            "⏰ Invia il nuovo <b>orario di inizio evento</b> (formato HH:MM, es. <code>21:30</code>) oppure /cancel per annullare:",
            parse_mode="HTML"
        )
        return EDIT_EVENT_TIME

    elif field == "episode":
        await query.answer()
        await query.message.reply_text(
            f"🔢 Invia il <b>numero del prossimo episodio</b> da guardare (attuale: <code>{serie.current_episode}</code>) oppure /cancel per annullare:",
            parse_mode="HTML"
        )
        return EDIT_EPISODE

    elif field == "anilist":
        await query.answer()
        await query.message.reply_text(
            "🔗 Invia il nuovo <b>ID o link AniList</b> per collegare l'anime, oppure /skip per rimuovere il collegamento (o /cancel):",
            parse_mode="HTML"
        )
        return EDIT_ANILIST

    elif field == "end_date":
        await query.answer()
        await query.message.reply_text(
            "📅 Invia la nuova <b>data di fine</b> (formato YYYY-MM-DD, es. <code>2026-12-31</code>), oppure scrivi <code>nessuna</code> / invia /skip per rimuoverla (o /cancel):",
            parse_mode="HTML"
        )
        return EDIT_END_DATE

    await query.answer()
    return SELECTING_FIELD


async def save_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """_Saves the updated series title._"""
    serie_id = context.user_data.get("edit_serie", {}).get("serie_id")
    new_title = update.message.text.strip() if update.message and update.message.text else ""

    if not new_title:
        await update.message.reply_text("⚠️ Il titolo non può essere vuoto. Riprova o scrivi /cancel:")
        return EDIT_TITLE

    updated = update_series_title(serie_id, new_title)
    if not updated:
        await update.message.reply_text("⚠️ Errore durante l'aggiornamento. Riprova o scrivi /cancel:")
        return EDIT_TITLE

    await send_or_edit_dashboard(update, context, updated, notice=f"✅ Titolo aggiornato a: <b>{html.escape(updated.title)}</b>")
    return SELECTING_FIELD


async def save_event_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """_Validates event start time and prompts for remind time._"""
    raw_time = update.message.text.strip() if update.message and update.message.text else ""
    try:
        parsed_time = datetime.datetime.strptime(raw_time, "%H:%M").time()
        context.user_data["edit_serie"]["temp_event_time"] = parsed_time
    except ValueError:
        await update.message.reply_text("⚠️ Formato orario non valido. Usa HH:MM (es. <code>21:30</code>) o scrivi /cancel:", parse_mode="HTML")
        return EDIT_EVENT_TIME

    await update.message.reply_text(
        f"Inizio evento impostato alle <b>{parsed_time.strftime('%H:%M')}</b>.\n\n"
        "⏰ A che ora deve scattare il <b>promemoria/tag</b>? (Formato HH:MM, es. <code>20:30</code>) oppure /cancel:",
        parse_mode="HTML"
    )
    return EDIT_REMIND_TIME


async def save_remind_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """_Validates remind time and commits both event and remind times._"""
    raw_time = update.message.text.strip() if update.message and update.message.text else ""
    try:
        parsed_remind = datetime.datetime.strptime(raw_time, "%H:%M").time()
    except ValueError:
        await update.message.reply_text("⚠️ Formato orario non valido. Usa HH:MM (es. <code>20:30</code>) o scrivi /cancel:", parse_mode="HTML")
        return EDIT_REMIND_TIME

    serie_id = context.user_data.get("edit_serie", {}).get("serie_id")
    event_time = context.user_data.get("edit_serie", {}).get("temp_event_time")

    updated, count = update_series_times(serie_id, event_time, parsed_remind)
    if not updated:
        await update.message.reply_text("⚠️ Errore durante l'aggiornamento. Riprova o scrivi /cancel:")
        return SELECTING_FIELD

    notice = (
        f"✅ <b>Orari aggiornati!</b>\n"
        f"Nuovo orario: <code>{event_time.strftime('%H:%M')}</code> (Notifica: <code>{parsed_remind.strftime('%H:%M')}</code>)\n"
        f"Appuntamenti futuri riprogrammati: {count}"
    )
    await send_or_edit_dashboard(update, context, updated, notice=notice)
    return SELECTING_FIELD


async def save_episode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """_Saves the updated current episode index._"""
    raw_text = update.message.text.strip() if update.message and update.message.text else ""
    try:
        current_ep = int(raw_text)
        if current_ep < 1:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("⚠️ Inserisci un numero intero positivo (es. <code>1</code>) o scrivi /cancel:", parse_mode="HTML")
        return EDIT_EPISODE

    serie_id = context.user_data.get("edit_serie", {}).get("serie_id")
    updated = update_series_episode(serie_id, current_ep)
    if not updated:
        await update.message.reply_text("⚠️ Errore durante l'aggiornamento. Riprova o scrivi /cancel:")
        return EDIT_EPISODE

    await send_or_edit_dashboard(update, context, updated, notice=f"✅ Episodio aggiornato a: <b>Episodio {updated.current_episode}</b>")
    return SELECTING_FIELD


async def save_anilist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """_Fetches anime metadata from AniList and links it to the series._"""
    raw_text = update.message.text.strip() if update.message and update.message.text else ""
    if raw_text.lower() in ["nessuno", "rimuovi", "no", "skip", "/skip"]:
        return await remove_anilist(update, context)

    match = re.search(r"\d+", raw_text)
    if not match:
        await update.message.reply_text("⚠️ ID o link non valido. Invia l'ID numerico o il link di AniList, oppure scrivi /skip:")
        return EDIT_ANILIST

    media_id = int(match.group())
    anime_data = fetch_anime_info_by_id(media_id)
    if not anime_data:
        await update.message.reply_text("⚠️ Anime non trovato su AniList. Riprova o scrivi /skip:")
        return EDIT_ANILIST

    anime_record, _ = AnilistAnime.get_or_create(
        anilist_media_id=anime_data["anilist_id"],
        defaults={
            "total_episodes": anime_data["total_episodes"],
            "cover_image_url": anime_data["cover_image"],
        }
    )

    serie_id = context.user_data.get("edit_serie", {}).get("serie_id")
    updated = update_series_anilist(serie_id, anime_record)
    if not updated:
        await update.message.reply_text("⚠️ Errore durante l'aggiornamento. Riprova o scrivi /cancel:")
        return EDIT_ANILIST

    notice = f"✅ <b>Collegato ad AniList:</b> <a href=\"https://anilist.co/anime/{anime_data['anilist_id']}\">{html.escape(anime_data['title'])}</a>"
    await send_or_edit_dashboard(update, context, updated, notice=notice)
    return SELECTING_FIELD


async def remove_anilist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """_Detaches any AniList anime from the series._"""
    serie_id = context.user_data.get("edit_serie", {}).get("serie_id")
    updated = update_series_anilist(serie_id, None)
    if not updated:
        await update.message.reply_text("⚠️ Errore durante l'aggiornamento.")
        return SELECTING_FIELD

    await send_or_edit_dashboard(update, context, updated, notice="✅ Collegamento AniList rimosso.")
    return SELECTING_FIELD


async def save_end_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """_Updates the end termination date of the series._"""
    raw_text = update.message.text.strip().lower() if update.message and update.message.text else ""
    if raw_text in ["nessuna", "nessuno", "no", "skip", "/skip", "rimuovi"]:
        return await remove_end_date(update, context)

    serie_id = context.user_data.get("edit_serie", {}).get("serie_id")
    serie = EventSerie.get_or_none(EventSerie.id == serie_id)
    if not serie:
        return ConversationHandler.END

    try:
        parsed_date = datetime.datetime.strptime(raw_text, "%Y-%m-%d").date()
        if parsed_date < serie.start_date:
            await update.message.reply_text(
                f"⚠️ La data di fine non può essere precedente alla data di inizio ({serie.start_date.strftime('%Y-%m-%d')}). Riprova o scrivi /cancel:"
            )
            return EDIT_END_DATE
    except ValueError:
        await update.message.reply_text("⚠️ Formato data non valido. Usa YYYY-MM-DD (es. <code>2026-12-31</code>) oppure scrivi <code>nessuna</code>:", parse_mode="HTML")
        return EDIT_END_DATE

    updated, count = update_series_end_date(serie_id, parsed_date)
    notice = f"✅ Data di fine impostata al <b>{parsed_date.strftime('%d/%m/%Y')}</b>. Appuntamenti futuri sincronizzati: {count}"
    await send_or_edit_dashboard(update, context, updated, notice=notice)
    return SELECTING_FIELD


async def remove_end_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """_Removes the termination date of the series._"""
    serie_id = context.user_data.get("edit_serie", {}).get("serie_id")
    updated, count = update_series_end_date(serie_id, None)
    notice = f"✅ Data di fine rimossa. Appuntamenti futuri sincronizzati: {count}"
    await send_or_edit_dashboard(update, context, updated, notice=notice)
    return SELECTING_FIELD


async def cancel_field_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """_Cancels current field editing and returns to the series dashboard._"""
    serie_id = context.user_data.get("edit_serie", {}).get("serie_id")
    serie = EventSerie.get_or_none(EventSerie.id == serie_id) if serie_id else None
    if not serie:
        return ConversationHandler.END

    await send_or_edit_dashboard(update, context, serie, notice="↩️ Modifica annullata.")
    return SELECTING_FIELD


async def cancel_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """_Terminates the edit conversation completely._"""
    context.user_data.clear()
    await update.message.reply_text("🏁 Modifica serie terminata.")
    return ConversationHandler.END


edit_series_handler = ConversationHandler(
    entry_points=[
        CommandHandler(
            "start",
            middleware(start_edit_serie),
            filters=filters.ChatType.PRIVATE & filters.Regex(r"^/start editserie_"),
        )
    ],
    states={
        SELECTING_FIELD: [
            CallbackQueryHandler(edit_field_callback, pattern=r"^edit_field:"),
        ],
        EDIT_TITLE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, middleware(save_title)),
            CommandHandler("cancel", middleware(cancel_field_edit)),
        ],
        EDIT_EVENT_TIME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, middleware(save_event_time)),
            CommandHandler("cancel", middleware(cancel_field_edit)),
        ],
        EDIT_REMIND_TIME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, middleware(save_remind_time)),
            CommandHandler("cancel", middleware(cancel_field_edit)),
        ],
        EDIT_EPISODE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, middleware(save_episode)),
            CommandHandler("cancel", middleware(cancel_field_edit)),
        ],
        EDIT_ANILIST: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, middleware(save_anilist)),
            CommandHandler("skip", middleware(remove_anilist)),
            CommandHandler("cancel", middleware(cancel_field_edit)),
        ],
        EDIT_END_DATE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, middleware(save_end_date)),
            CommandHandler("skip", middleware(remove_end_date)),
            CommandHandler("cancel", middleware(cancel_field_edit)),
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel_edit),
        CommandHandler("done", cancel_edit),
    ],
    allow_reentry=True,
    per_message=False,
)
