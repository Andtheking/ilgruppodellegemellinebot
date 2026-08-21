from collections import defaultdict
from typing import Dict, List, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from models.models import Chat, EventSerie
from services.subscribe_to_eventseries import get_series_subscribers, toggle_subscription

DAYS_NAME = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]


def build_compact_schedule_dashboard(
    chat_id: int, 
    user_id: int
) -> Tuple[str, InlineKeyboardMarkup]:
    """_Builds a consolidated weekly schedule text and an interactive inline keyboard for all active series._

    Args:
        chat_id (int): _The unique Telegram chat ID._
        user_id (int): _The Telegram user ID to check subscription states._

    Returns:
        Tuple[str, InlineKeyboardMarkup]: _A tuple containing the formatted HTML dashboard text and inline keyboard markup._
    """
    active_series = list(
        EventSerie
        .select()
        .where(
            (EventSerie.chat == chat_id) &
            (EventSerie.is_active == True)
        )
        .order_by(EventSerie.day_of_week, EventSerie.default_event_time)
    )

    if not active_series:
        return "Non ci sono serie attive in questo gruppo.", InlineKeyboardMarkup([])

    # Group series by day of week
    by_day: Dict[int, List[EventSerie]] = defaultdict(list)
    for s in active_series:
        by_day[s.day_of_week].append(s)

    lines = ["📅 <b>PALINSESTO WATCHPARTY SETTIMANALE</b>\n"]
    keyboard_buttons = []

    for day_idx in range(7):
        if day_idx not in by_day:
            continue

        day_name = DAYS_NAME[day_idx]
        lines.append(f"📌 <b>{day_name}</b>")

        for s in by_day[day_idx]:
            subs = get_series_subscribers(s.id)
            is_subbed = any(u.id == user_id for u in subs)
            time_str = s.default_event_time.strftime("%H:%M")
            title_display = s.title
            ep_str = f'[Ep. {s.current_episode}'
            # Per ogni serie 's':
            if s.anilist_anime:
                ep_total = f"/{s.anilist_anime.total_episodes}" if s.anilist_anime.total_episodes else ""
                ep_str = f" [Ep. {s.current_episode}{ep_total}]"

                if s.anilist_anime:
                    title_display = f'<a href="https://anilist.co/anime/{s.anilist_anime.anilist_media_id}">{s.title}</a>'

            lines.append(f"  • <code>{time_str}</code> <b>{title_display}</b>{ep_str} ({len(subs)} iscritti)")

            # Button per-serie: status icon + truncated title
            icon = "🔔" if is_subbed else "🔕"
            button_label = f"{icon} {s.title}"
            keyboard_buttons.append([
                InlineKeyboardButton(button_label, callback_data=f"toggle_sub:{s.id}")
            ])

        lines.append("")

    lines.append("<i>Tocca i pulsanti sotto per iscriverti (🔔) o disiscriverti (🔕)</i>")

    return "\n".join(lines), InlineKeyboardMarkup(keyboard_buttons)


async def list_series_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """_Displays the consolidated weekly schedule dashboard as an ephemeral message for the requesting user._

    Args:
        update (Update): _The incoming Telegram update._
        context (ContextTypes.DEFAULT_TYPE): _The execution context._
    """
    if not update.effective_chat or not update.effective_user or not update.effective_message:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    Chat.get_or_create(id=chat_id, defaults={'title': update.effective_chat.title or "Chat"})

    text, reply_markup = build_compact_schedule_dashboard(chat_id, user_id)

    raw_dict = update.effective_message.to_dict()
    ephemeral_id = raw_dict.get("ephemeral_message_id")

    extra_params = {
        "receiver_user_id": user_id,
    }
    if ephemeral_id:
        extra_params["reply_parameters"] = {
            "ephemeral_message_id": ephemeral_id
        }

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode="HTML",
        api_kwargs=extra_params,
    )

# FIXME: future me, when python-telegram-bot adds support to new ephemeral messages fix this please
async def subscription_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """_Handles button clicks to toggle user subscriptions and edits the ephemeral message text via editEphemeralMessageText._

    Args:
        update (Update): _The incoming callback query update._
        context (ContextTypes.DEFAULT_TYPE): _The execution context._
    """
    query = update.callback_query
    if not query or not update.effective_user or not update.effective_chat:
        return

    await query.answer()

    _, serie_id_str = query.data.split(":")
    serie_id = int(serie_id_str)
    user_tg = update.effective_user
    chat_id = update.effective_chat.id

    # 1. Toggle subscription in DB
    is_subbed, serie_title = toggle_subscription(
        user_id=user_tg.id,
        username=user_tg.username or "",
        serie_id=serie_id
    )

    alert_text = f"Iscritto a {serie_title}!" if is_subbed else f"Disiscritto da {serie_title}."
    await query.answer(text=alert_text, show_alert=False)

    # 2. Rebuild updated dashboard for the user
    text, reply_markup = build_compact_schedule_dashboard(chat_id, user_tg.id)

    # 3. Extract ephemeral_message_id from the callback message dict
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
        print(f"Errore editEphemeralMessageText: {error}")