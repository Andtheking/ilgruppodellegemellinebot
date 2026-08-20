import datetime
from typing import List
from models.models import db, EventSerie, ActualEvent
from peewee import fn

DEFAULT_WEEKS_AHEAD = 4

def populate_rolling_events_for_series(series: EventSerie, weeks_ahead: int = DEFAULT_WEEKS_AHEAD) -> int:
    """_Generates new actual events from a event series_

    Args:
        series (EventSerie): _event series_
        weeks_ahead (int, optional): _how much in future create actual events_. Defaults to 4.

    Returns:
        int: _how many events have been created_
    """
    today = datetime.date.today()
    now = datetime.datetime.now()

    if not series.is_active or series.end_date < today:
        return 0

    target_horizon_date = today + datetime.timedelta(weeks = weeks_ahead)
    if series.end_date:
        target_horizon_date = min(target_horizon_date, series.end_date)

    # last defined date for this event series
    last_event_dt: datetime.datetime = (
        ActualEvent
        .select(fn.MAX(ActualEvent.event_datetime))
        .where(ActualEvent.event_serie == series)
        .scalar()
    )

    if last_event_dt:
        # start from last actual event + 1
        start_search_date = last_event_dt.date() + datetime.timedelta(days=1)
    else: 
        # it's the first event
        start_search_date = max(series.start_date, today)

    days_ahead = (series.day_of_week - start_search_date.weekday()) % 7 # mod always positive
    actual_date = start_search_date + datetime.timedelta(days=days_ahead)

    events_to_create: List[ActualEvent] = []
    one_week = datetime.timedelta(weeks=1)

    while actual_date <= target_horizon_date:
        event_dt = datetime.datetime.combine(actual_date, series.default_event_time)
        remind_dt = datetime.datetime.combine(actual_date, series.default_remind_time)

        # the remind time is in the previous day
        if series.default_remind_time > series.default_event_time:
            remind_dt -= datetime.timedelta(days=1)

        if remind_dt >= now:
            events_to_create.append(
                ActualEvent(
                    event_serie=series,
                    event_datetime=event_dt,
                    remind_datetime=remind_dt,
                    status='PENDING'
                )
            )

        actual_date += one_week

    if not events_to_create:
        return 0

    with db.atomic():
        ActualEvent.bulk_create(events_to_create, batch_size=50)

    return len(events_to_create)

def sync_all_active_series() -> int:
    """_Generate actual events for each series_

    Returns:
        int: _How many events have been created_
    """
    total_created = 0
    active_series = EventSerie.select().where(EventSerie.is_active == True)

    for serie in active_series:
        total_created += populate_rolling_events_for_series(serie)

    return total_created