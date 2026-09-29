from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from models.models import Chat, EventSerie, SharedEventSerie
from services.subscribe_to_eventseries import get_series_subscribers, toggle_subscription
from bot.utils.checks import is_user_groupadmin
from bot.ephimeral_patch.EphemeralUtils import build_ephemeral_reply_context
from bot.ephimeral_patch.EphemeralContext import EphemeralContext
from utils.log import log

DAYS_NAME = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
DAYS_SHORT = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]


def build_day_schedule_dashboard(
    chat_id: int, 
    user_id: int,
    selected_day: Optional[int] = None,
    is_admin: bool = False
) -> Tuple[str, InlineKeyboardMarkup]:
    """_Builds a daily paginated schedule text and inline keyboard for active series._

    Args:
        chat_id (int): _The unique Telegram chat ID._
        user_id (int): _The Telegram user ID to check subscription states._
        selected_day (Optional[int], optional): _The day index to show (0=Monday, 6=Sunday). Defaults to None._

    Returns:
        Tuple[str, InlineKeyboardMarkup]: _A tuple containing the formatted HTML dashboard text and inline keyboard markup._
    """
    active_series = list(
        EventSerie.select()
        .left_outer_join(SharedEventSerie, on=(SharedEventSerie.event_serie == EventSerie.id))
        .where(
            (EventSerie.is_active == True) &
            ((EventSerie.chat == chat_id) | (SharedEventSerie.chat == chat_id))
        )
        .order_by(EventSerie.day_of_week, EventSerie.default_event_time)
        .distinct()
    )

    if not active_series:
        return "Non ci sono serie attive in questo gruppo.", InlineKeyboardMarkup([])

    by_day: Dict[int, List[EventSerie]] = defaultdict(list)
    for event in active_series:
        by_day[event.day_of_week].append(event)

    available_days = sorted(by_day.keys())

    # Se il giorno richiesto non è tra quelli attivi, prendi il primo giorno disponibile
    if selected_day is None or selected_day not in by_day:
        selected_day = available_days[0]

    # 1. Barra di navigazione dei giorni (mostra solo i giorni con serie)
    day_nav_buttons: List[InlineKeyboardButton] = []
    for day_idx in available_days:
        label = f"• {DAYS_SHORT[day_idx]} •" if day_idx == selected_day else DAYS_SHORT[day_idx]
        day_nav_buttons.append(
            InlineKeyboardButton(label, callback_data=f"show_day:{day_idx}")
        )

    keyboard_rows: List[List[InlineKeyboardButton]] = [day_nav_buttons]

    # 2. Composizione del testo per il giorno selezionato
    full_day_name = DAYS_NAME[selected_day]
    lines = [
        f"📅 <b>EVENTI</b> - <b>{full_day_name}</b>\n"
    ]

    series_of_day = by_day[selected_day]
    current_btn_row: List[InlineKeyboardButton] = []

    for event in series_of_day:
        subs = get_series_subscribers(event.id)
        is_subbed = any(u.id == user_id for u in subs)
        time_str = event.default_event_time.strftime("%H:%M")

        # Pulizia titolo
        title = event.title.replace("Watchparty ", "").strip()
        tot_eps = f"/{event.anilist_anime.total_episodes}" if event.anilist_anime and event.anilist_anime.total_episodes else ""
        ep_info = f"ep. {event.current_episode}{tot_eps}"

        if event.anilist_anime:
            title_display = f'<a href="https://anilist.co/anime/{event.anilist_anime.anilist_media_id}">{title}</a>'
        else:
            title_display = title

        if event.chat.id != chat_id:
            title_display = f"🤝 {title_display}"
        

        lines.append(f"• <code>{time_str}</code> │ {title_display} (<i>{ep_info}</i>) · 👥 {len(subs)}")

        # Pulsante compatto a 2 colonne
        icon = "🔕" if is_subbed else "🔔"
        btn_label = f"{icon} {title[:16]}…" if len(title) > 17 else f"{icon} {title}"
        current_btn_row.append(
            InlineKeyboardButton(btn_label, callback_data=f"toggle_sub:{event.id}:{selected_day}")
        )
        if is_admin:
            current_btn_row.append(
                InlineKeyboardButton(f"🔗 Condividi", callback_data=f"share_link:{event.id}")
            )

        if len(current_btn_row) == 2:
            keyboard_rows.append(current_btn_row)
            current_btn_row = []

    if current_btn_row:
        keyboard_rows.append(current_btn_row)

    lines.append("\n<i>Tocca i pulsanti sopra per cambiare giorno, sotto per iscriverti (🔔) o disiscriverti (🔕).</i>")

    return "\n".join(lines), InlineKeyboardMarkup(keyboard_rows)


async def list_series_command(update: Update, context: EphemeralContext) -> None:
    """_Displays the day-paginated schedule dashboard as an ephemeral message._"""
    if not update.effective_chat or not update.effective_user or not update.effective_message:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    Chat.get_or_create(id=chat_id, defaults={'title': update.effective_chat.title or "Chat"})

    text, reply_markup = build_day_schedule_dashboard(chat_id, user_id, is_admin=await is_user_groupadmin(update, context))

    eph_params, reply_params = build_ephemeral_reply_context(update)

    await context.bot.send_ephemeral_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode="HTML",
        ephemeral_parameters=eph_params
    )


async def subscription_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """_Handles navigation between days or toggles subscriptions and updates the ephemeral message._"""
    query = update.callback_query
    if not query or not update.effective_user or not update.effective_chat:
        return

    user_tg = update.effective_user
    chat_id = update.effective_chat.id
    data_parts = query.data.split(":")
    action = data_parts[0]

    selected_day: Optional[int] = None

    if action == "show_day":
        selected_day = int(data_parts[1])
        await query.answer()

    elif action == "toggle_sub":
        serie_id = int(data_parts[1])
        selected_day = int(data_parts[2]) if len(data_parts) > 2 else None

        is_subbed, serie_title = toggle_subscription(
            user_id=user_tg.id,
            username=user_tg.username or "",
            serie_id=serie_id
        )

        alert_text = f"Iscritto a {serie_title}!" if is_subbed else f"Disiscritto da {serie_title}."
        await query.answer(text=alert_text, show_alert=False)

    else:
        await query.answer()
        return

    # Rigenera il dashboard con il giorno corrente
    text, reply_markup = build_day_schedule_dashboard(chat_id, user_tg.id, selected_day=selected_day, is_admin=await is_user_groupadmin(update, context))

    raw_query = query.to_dict()
    raw_message = raw_query.get("message", {})
    ephemeral_id = raw_message.get("ephemeral_message_id")

    if not ephemeral_id:
        return

    payload = {
        "chat_id": chat_id,
        "receiver_user_id": user_tg.id,
        "ephemeral_message_id": ephemeral_id,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": reply_markup.to_dict(),
    }

    try:
        await context.bot._post(
            endpoint="editEphemeralMessageText",
            data=payload,
        )
    except Exception as error:
        log(f"Errore editEphemeralMessageText: {error}")