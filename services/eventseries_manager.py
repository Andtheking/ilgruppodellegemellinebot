import datetime
from typing import Optional, Tuple, Union
from models.models import Chat, EventSerie, AnilistAnime, SharedEventSerie, EventSerieSubscription, ActualEvent, db
from services.actualevent_manager import populate_rolling_events_for_series


def create_series_with_events(
    chat_id: int,
    title: str,
    day_of_week: int,
    event_time: datetime.time,
    remind_time: datetime.time,
    start_date: datetime.date,
    end_date: Optional[datetime.date] = None,
    anilist_anime: Optional[Union[AnilistAnime, int]] = None,
    current_episode: int = 1
) -> Tuple[EventSerie, int]:
    """_Creates a new event series with optional AniList metadata and populates its initial rolling schedule._

    Args:
        chat_id (int): _The unique Telegram ID of the chat or group._
        title (str): _The descriptive name or title of the series._
        day_of_week (int): _Weekly recurrence day (0=Monday, 6=Sunday)._
        event_time (datetime.time): _Scheduled start time for the events._
        remind_time (datetime.time): _Scheduled notification/reminder dispatch time._
        start_date (datetime.date): _Start date from which the series becomes active._
        end_date (Optional[datetime.date], optional): _Termination date of the series. Defaults to None._
        chat_title (Optional[str], optional): _Display name of the Telegram chat for database logging. Defaults to None._
        anilist_anime (Optional[Union[AnilistAnime, int]], optional): _The linked AnilistAnime model instance or media ID. Defaults to None._
        current_episode (int, optional): _The starting episode index. Defaults to 1._

    Returns:
        Tuple[EventSerie, int]: _A tuple containing the created EventSerie model instance and the count of generated ActualEvent records._
    """
    with db.atomic():
        serie = EventSerie.create(
            chat=chat_id,
            title=title,
            day_of_week=day_of_week,
            default_event_time=event_time,
            default_remind_time=remind_time,
            start_date=start_date,
            end_date=end_date,
            anilist_anime=anilist_anime,
            current_episode=max(1, current_episode),
            is_active=True
        )

        events_count = populate_rolling_events_for_series(serie)

    return serie, events_count


def delete_or_unlink_series(serie_id: int, chat_id: int) -> Tuple[str, str]:
    """_Deletes an event series if the chat is the owner, or unlinks it if the chat is a shared participant._

    Args:
        serie_id (int): _The ID of the series._
        chat_id (int): _The ID of the requesting chat._

    Returns:
        Tuple[str, str]: _("deleted" | "unlinked" | "not_found", title of the series)_
    """
    serie = EventSerie.get_or_none(EventSerie.id == serie_id)
    if not serie:
        return "not_found", ""

    title = serie.title
    if serie.chat_id != chat_id:
        deleted_rows = (
            SharedEventSerie
            .delete()
            .where(
                (SharedEventSerie.event_serie == serie) &
                (SharedEventSerie.chat == chat_id)
            )
            .execute()
        )
        if deleted_rows > 0:
            return "unlinked", title
        return "not_found", title
    else:
        with db.atomic():
            ActualEvent.delete().where(ActualEvent.event_serie == serie).execute()
            EventSerieSubscription.delete().where(EventSerieSubscription.event_serie == serie).execute()
            SharedEventSerie.delete().where(SharedEventSerie.event_serie == serie).execute()
            serie.delete_instance()
        return "deleted", title


def change_series_day_of_week(serie_id: int, new_day_of_week: int) -> Tuple[Optional[EventSerie], int]:
    """_Changes the recurring day of the week for an event series and regenerates future pending actual events._

    Args:
        serie_id (int): _The ID of the event series._
        new_day_of_week (int): _The new day of the week (0=Monday, 6=Sunday)._

    Returns:
        Tuple[Optional[EventSerie], int]: _A tuple containing the updated EventSerie (or None if not found) and the number of recreated events._
    """
    serie = EventSerie.get_or_none(EventSerie.id == serie_id)
    if not serie:
        return None, 0

    now = datetime.datetime.now()

    with db.atomic():
        serie.day_of_week = new_day_of_week
        serie.save(only=[EventSerie.day_of_week])

        # Delete all pending and future skipped events
        (
            ActualEvent
            .delete()
            .where(
                (ActualEvent.event_serie == serie) &
                (
                    (ActualEvent.status == 'PENDING') |
                    ((ActualEvent.status == 'SKIPPED') & (ActualEvent.event_datetime >= now))
                )
            )
            .execute()
        )

        events_created = populate_rolling_events_for_series(serie)

    return serie, events_created


def update_series_times(
    serie_id: int,
    event_time: datetime.time,
    remind_time: datetime.time
) -> Tuple[Optional[EventSerie], int]:
    """_Updates default event and reminder times, regenerating future pending events._"""
    serie = EventSerie.get_or_none(EventSerie.id == serie_id)
    if not serie:
        return None, 0

    now = datetime.datetime.now()
    with db.atomic():
        serie.default_event_time = event_time
        serie.default_remind_time = remind_time
        serie.save(only=[EventSerie.default_event_time, EventSerie.default_remind_time])

        ActualEvent.delete().where(
            (ActualEvent.event_serie == serie) &
            (
                (ActualEvent.status == 'PENDING') |
                ((ActualEvent.status == 'SKIPPED') & (ActualEvent.event_datetime >= now))
            )
        ).execute()

        events_created = populate_rolling_events_for_series(serie)

    return serie, events_created


def update_series_title(serie_id: int, title: str) -> Optional[EventSerie]:
    """_Updates the title of an event series._"""
    serie = EventSerie.get_or_none(EventSerie.id == serie_id)
    if not serie:
        return None

    cleaned_title = title.strip()
    if not cleaned_title:
        return None

    serie.title = cleaned_title
    serie.save(only=[EventSerie.title])
    return serie


def update_series_episode(serie_id: int, current_episode: int) -> Optional[EventSerie]:
    """_Updates the current episode index of an event series._"""
    serie = EventSerie.get_or_none(EventSerie.id == serie_id)
    if not serie:
        return None

    serie.current_episode = max(1, current_episode)
    serie.save(only=[EventSerie.current_episode])
    return serie


def update_series_anilist(
    serie_id: int,
    anilist_anime: Optional[Union[AnilistAnime, int]]
) -> Optional[EventSerie]:
    """_Updates or removes the linked AniList anime for an event series._"""
    serie = EventSerie.get_or_none(EventSerie.id == serie_id)
    if not serie:
        return None

    serie.anilist_anime = anilist_anime
    serie.save(only=[EventSerie.anilist_anime])
    return serie


def update_series_end_date(
    serie_id: int,
    end_date: Optional[datetime.date]
) -> Tuple[Optional[EventSerie], int]:
    """_Updates the termination date of an event series and adjusts pending events._"""
    serie = EventSerie.get_or_none(EventSerie.id == serie_id)
    if not serie:
        return None, 0

    now = datetime.datetime.now()
    with db.atomic():
        serie.end_date = end_date
        serie.save(only=[EventSerie.end_date])

        ActualEvent.delete().where(
            (ActualEvent.event_serie == serie) &
            (
                (ActualEvent.status == 'PENDING') |
                ((ActualEvent.status == 'SKIPPED') & (ActualEvent.event_datetime >= now))
            )
        ).execute()

        events_created = populate_rolling_events_for_series(serie)

    return serie, events_created

