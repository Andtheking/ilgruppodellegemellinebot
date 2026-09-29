from collections import defaultdict
from typing import Dict, List, Tuple, Set
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from telegram.error import BadRequest, Forbidden  # Aggiunto per filtrare gli utenti

from models.models import ActualEvent, User, SharedEventSerie  # Importa SharedEventSerie
from services.episodes_manager import advance_episode
from services.actualevent_manager import sync_all_active_series
from services.notification_service import get_due_reminders, mark_events_as_sent
from services.watchstatus_manager import categorize_subscribers_progress
from utils.log import log


async def check_reminders_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """_Dispatches aggregated watchparty reminders across all owner and shared groups, 
    filtering users per-group and advancing episodes globally._"""
    due_reminders = get_due_reminders()
    if not due_reminders:
        return

    # 1. Raggruppa gli eventi per chat_id (includendo i gruppi condivisi)
    reminders_by_chat: Dict[int, List[Tuple[ActualEvent, List[User]]]] = defaultdict(list)
    events_to_mark: Set[ActualEvent] = set() # Usiamo un set per evitare duplicati di avanzamento

    for event, global_users in due_reminders:
        events_to_mark.add(event)
        serie = event.event_serie
        
        # Recupera tutte le chat associate alla serie (Proprietario + Condivise)
        target_chats = {serie.chat.id}
        shared_chats = SharedEventSerie.select().where(SharedEventSerie.event_serie == serie)
        for shared in shared_chats:
            target_chats.add(shared.chat.id)
            
        for chat_id in target_chats:
            reminders_by_chat[chat_id].append((event, global_users))

    # 2. Processa l'invio per ogni singola chat
    for chat_id, items in reminders_by_chat.items():
        sections: List[str] = []

        for event, global_users in items:
            serie = event.event_serie
            event_hour = event.event_datetime.strftime("%H:%M")

            # FILTRO UTENTI: Controlla chi è davvero in questo gruppo
            local_users = []
            for user in global_users:
                try:
                    member = await context.bot.get_chat_member(chat_id, user.id)
                    # Aggiungiamo l'utente solo se è ancora attivamente nel gruppo
                    if member.status not in ['left', 'kicked']:
                        local_users.append(user)
                except (BadRequest, Forbidden):
                    # Il bot non è nel gruppo o l'utente non è mai entrato
                    continue

            # Analisi AniList SOLO per gli iscritti presenti in questa specifica chat
            caught_up, behind, not_linked = categorize_subscribers_progress(serie, local_users)

            status_lines: List[str] = []
            if caught_up:
                status_lines.append(f"🟢 <b>In pari:</b> {', '.join(caught_up)}")
            if behind:
                status_lines.append(f"🟡 <b>Indietro:</b> {', '.join(behind)}")
            if not_linked:
                status_lines.append(f"⚪ <b>Senza AniList:</b> {', '.join(not_linked)}")

            status_block = "\n".join(status_lines) if status_lines else "<i>Nessun iscritto al momento in questo gruppo</i>"

            # Costruzione Titolo (con indicatore visivo se è una serie condivisa)
            prefix = "🎬 " if serie.chat.id == chat_id else "🤝 "
            total_eps = serie.anilist_anime.total_episodes if serie.anilist_anime else None
            tot_str = f"/{total_eps}" if total_eps else ""

            if serie.anilist_anime:
                title_line = f'<a href="https://anilist.co/anime/{serie.anilist_anime.anilist_media_id}">{serie.title}</a>'
            else:
                title_line = serie.title

            note_line = f"\n📝 <b>Note:</b> {event.note}" if event.note else ""

            section_text = (
                f"{prefix}<b>{title_line}</b> — <b>Episodio {serie.current_episode}{tot_str}</b>\n"
                f"⏰ Inizio: <b>{event_hour}</b>{note_line}\n\n"
                f"👥 <b>Stato Partecipanti:</b>\n{status_block}"
            )

            sections.append(section_text)

        divider = "\n\n" + "—" * 16 + "\n\n"
        message_text = "🔔 <b>PROMEMORIA IN ARRIVO!</b>\n\n" + divider.join(sections)

        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=message_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except Exception as error:
            log(f"Errore durante l'invio della notifica aggregata per la chat {chat_id}: {error}")

    # 3. DOPO aver inviato i messaggi in tutte le chat, avanziamo gli episodi una volta sola per evento
    if events_to_mark:
        sent_events_list = list(events_to_mark)
        mark_events_as_sent(sent_events_list)
        
        for event in sent_events_list:
            advance_episode(event.event_serie)


async def daily_sync_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... rimane invariato ...
    sync_all_active_series()