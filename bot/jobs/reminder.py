from collections import defaultdict
from typing import Dict, List, Tuple
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from models.models import ActualEvent, User
from services.episodes_manager import advance_episode
from services.actualevent_manager import sync_all_active_series
from services.notification_service import get_due_reminders, mark_events_as_sent
from services.watchstatus_manager import categorize_subscribers_progress


async def check_reminders_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """_Dispatches aggregated watchparty reminders with AniList progress tracking and advances episodes._

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

    # 2. Process each chat
    for chat_id, items in reminders_by_chat.items():
        sections: List[str] = []
        sent_events: List[ActualEvent] = []

        for event, users in items:
            serie = event.event_serie
            event_hour = event.event_datetime.strftime("%H:%M")

            # AniList progress analysis
            caught_up, behind, not_linked = categorize_subscribers_progress(serie, users)

            status_lines: List[str] = []
            if caught_up:
                status_lines.append(f"🟢 <b>In pari:</b> {', '.join(caught_up)}")
            if behind:
                status_lines.append(f"🟡 <b>Indietro:</b> {', '.join(behind)}")
            if not_linked:
                status_lines.append(f"⚪ <b>Senza AniList:</b> {', '.join(not_linked)}")

            status_block = "\n".join(status_lines) if status_lines else "<i>Nessun iscritto al momento</i>"

            # Title with AniList link if available
            total_eps = serie.anilist_anime.total_episodes if serie.anilist_anime else None
            tot_str = f"/{total_eps}" if total_eps else ""

            if serie.anilist_anime:
                title_line = f'<a href="https://anilist.co/anime/{serie.anilist_anime.anilist_media_id}">{serie.title}</a>'
            else:
                title_line = serie.title

            note_line = f"\n📝 <b>Note:</b> {event.note}" if event.note else ""

            section_text = (
                f"🎬 <b>{title_line}</b> — <b>Episodio {serie.current_episode}{tot_str}</b>\n"
                f"⏰ Inizio: <b>{event_hour}</b>{note_line}\n\n"
                f"👥 <b>Stato Partecipanti:</b>\n{status_block}"
            )

            sections.append(section_text)
            sent_events.append(event)

        divider = "\n\n" + "—" * 16 + "\n\n"
        message_text = "🔔 <b>PROMEMORIA WATCHPARTY IN ARRIVO!</b>\n\n" + divider.join(sections)

        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )

            # Mark events as processed
            mark_events_as_sent(sent_events)

            # Advance current episode for all screened series
            for event in sent_events:
                advance_episode(event.event_serie)

        except Exception as error:
            print(f"Errore durante l'invio della notifica aggregata per la chat {chat_id}: {error}")


async def daily_sync_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """_Background job executed daily to extend the rolling window for all active series._

    Args:
        context (ContextTypes.DEFAULT_TYPE): _The execution context provided by python-telegram-bot._
    """
    sync_all_active_series()