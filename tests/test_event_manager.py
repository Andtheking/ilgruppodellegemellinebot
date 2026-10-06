import datetime
import pytest
import os
from peewee import SqliteDatabase

from models.models import User, Chat, EventSerie, EventSerieSubscription, ActualEvent, AnilistAnime
from services.actualevent_manager import populate_rolling_events_for_series, sync_all_active_series

db_test = SqliteDatabase(':memory:', pragmas={'foreign_keys': 1})
MODELS = [User, Chat, AnilistAnime, EventSerie, EventSerieSubscription, ActualEvent]
WEEKS_AHEAD = 4

@pytest.fixture(autouse=True)
def setup_test_database():
    """_Initialize DB and destroys it at the end of each test_"""
    db_test.bind(MODELS, bind_refs=False, bind_backrefs=False)
    db_test.connect()
    db_test.create_tables(MODELS)
    yield
    db_test.drop_tables(MODELS)
    db_test.close()

def test_populate_initial_events():
    """_Check that event series are populated_"""
    chat = Chat.create(id=123456, title="Gruppo Watchparty")
    
    today = datetime.date.today()
    series = EventSerie.create(
        chat=chat,
        title="Anime Night",
        default_event_time=datetime.time(21, 30),
        default_remind_time=datetime.time(20, 30),
        day_of_week=today.weekday(),
        start_date=today,
        end_date=today + datetime.timedelta(days=90),
        is_active=True
    )

    created = populate_rolling_events_for_series(series, weeks_ahead=WEEKS_AHEAD)
    assert created >= WEEKS_AHEAD
    assert ActualEvent.select().where(ActualEvent.event_serie == series).count() == created

def test_4_week_sync():
    """_If the event series has already been populated for the horizon weeks, 
    it should not be populated anymore._"""
    chat = Chat.create(id=999, title="Series Test")
    today = datetime.date.today()

    series = EventSerie.create(
        chat=chat,
        title="Gaming Night",
        default_event_time=datetime.time(21, 00),
        default_remind_time=datetime.time(20, 00),
        day_of_week=(today.weekday() + 1) % 7, # tomorrow
        start_date=today,
        end_date=today + datetime.timedelta(days=60),
        is_active=True
    )

    first_time = sync_all_active_series()
    assert first_time > 0

    second_time = sync_all_active_series()
    assert second_time == 0 # no actual event created

def test_series_without_end_date():
    """Check that series with end_date=None are supported and populated correctly."""
    chat = Chat.create(id=111, title="No End Date Chat")
    today = datetime.date.today()

    series = EventSerie.create(
        chat=chat,
        title="Ongoing Anime",
        default_event_time=datetime.time(21, 00),
        default_remind_time=datetime.time(20, 00),
        day_of_week=today.weekday(),
        start_date=today,
        end_date=None,
        is_active=True
    )

    created = populate_rolling_events_for_series(series, weeks_ahead=WEEKS_AHEAD)
    assert created >= WEEKS_AHEAD

    # sync should also work without throwing TypeError
    synced = sync_all_active_series()
    assert synced == 0

def test_advance_episode_without_anilist():
    """advance_episode should return None for total_episodes when anilist_anime is None."""
    from services.episodes_manager import advance_episode
    chat = Chat.create(id=222, title="No AniList Chat")
    today = datetime.date.today()

    series = EventSerie.create(
        chat=chat,
        title="Custom Movie Night",
        default_event_time=datetime.time(21, 00),
        default_remind_time=datetime.time(20, 00),
        day_of_week=today.weekday(),
        start_date=today,
        end_date=None,
        is_active=True,
        anilist_anime=None,
        current_episode=1
    )

    new_ep, total_eps = advance_episode(series)
    assert new_ep == 2
    assert total_eps is None

def test_user_mention_html_escaping():
    """Verify that mentions properly escape HTML characters."""
    from services.watchstatus_manager import format_user_mention
    user_with_tags = User.create(id=123, username="<hacker>&co")
    mention = format_user_mention(user_with_tags)
    assert "&lt;hacker&gt;&amp;co" in mention
    assert "<hacker>" not in mention