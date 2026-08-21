from collections import defaultdict
from typing import Dict, List, Tuple

from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from models.models import ActualEvent, User
from services.notification_service import get_due_reminders, mark_events_as_sent
from services.actualevent_manager import sync_all_active_series


async def check_reminders_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """_Background job that groups and dispatches due reminders to Telegram chats in single aggregate messages._

    Args:
        context (ContextTypes.DEFAULT_TYPE): _The execution context provided by python-telegram-bot._
    """
    due_reminders = get_due_reminders()
    if not due_reminders:
        return

    # 1. Group events by chat_id: {chat_id: [(event, users), ...]}
    reminders_by_chat: Dict[int, List[Tuple[ActualEvent, List[User]]]] = defaultdict(list)
    for event, users in due_reminders:
        reminders_by_chat[event.event_serie.chat.id].append((event, users))

    # 2. Build and dispatch one consolidated message per chat
    for chat_id, items in reminders_by_chat.items():
        sections = []
        sent_events: List[ActualEvent] = []

        for event, users in items:
            serie = event.event_serie
            event_hour = event.event_datetime.strftime("%H:%M")

            tags = [
                f"@{u.username}" if u.username else f'<a href="tg://user?id={u.id}">Utente</a>'
                for u in users
            ]
            tag_line = " ".join(tags) if tags else "<i>Nessun iscritto registrato</i>"
            note_line = f"\n📝 <b>Note:</b> {event.note}" if event.note else ""

            section_text = (
                f"🎬 <b>{serie.title}</b>\n"
                f"⏰ Inizio: <b>{event_hour}</b>{note_line}\n"
                f"👥 Partecipanti: {tag_line}"
            )
            sections.append(section_text)
            sent_events.append(event)

        divider = "\n\n" + "—" * 15 + "\n\n"
        message_text = "🔔 <b>PROMEMORIA WATCHPARTY IN ARRIVO!</b>\n\n" + divider.join(sections)

        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                parse_mode=ParseMode.HTML
            )
            mark_events_as_sent(sent_events)
        except Exception as error:
            print(f"Errore durante l'invio della notifica aggregata per la chat {chat_id}: {error}")
            

async def daily_sync_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """_Background job executed daily to extend the rolling window for all active series._

    Args:
        context (ContextTypes.DEFAULT_TYPE): _The execution context provided by python-telegram-bot._
    """
    sync_all_active_series()