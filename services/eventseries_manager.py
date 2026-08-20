import datetime
from typing import Optional, Tuple
from models.models import db
from models.models import EventSerie, Chat
from services.actualevent_manager import populate_rolling_events_for_series

def create_series_with_events(
    chat_id: int,
    title: str,
    day_of_week: int,
    event_time: datetime.time,
    remind_time: datetime.time,
    start_date: datetime.date,
    end_date: Optional[datetime.date] = None,
    chat_title: Optional[str] = None
) -> Tuple[EventSerie, int]:
    """_Creates a new event series and populates its initial rolling schedule._

    Args:
        chat_id (int): _The unique Telegram ID of the chat or group._
        title (str): _The descriptive name or title of the series._
        day_of_week (int): _Weekly recurrence day (0=Monday, 6=Sunday)._
        event_time (datetime.time): _Scheduled start time for the events._
        remind_time (datetime.time): Scheduled notification/reminder dispatch time._
        start_date (datetime.date): _Start date from which the series becomes active._
        end_date (Optional[datetime.date], optional): _Termination date of the series. Defaults to None._
        chat_title (Optional[str], optional): _Display name of the Telegram chat for database logging._ Defaults to _None_.

    Returns:
        Tuple[EventSerie, int]: _A tuple containing the created EventSerie model instance and the count of generated ActualEvent records._
    """
    with db.atomic():
        Chat.get_or_create(id=chat_id, defaults={'title': chat_title or 'Chat'})

        serie = EventSerie.create(
            chat_id=chat_id,
            title=title,
            day_of_week=day_of_week,
            default_event_time=event_time,
            default_remind_time=remind_time,
            start_date=start_date,
            end_date=end_date,
            is_active=True
        )

        events_count = populate_rolling_events_for_series(serie)

    return serie, events_count