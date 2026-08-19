import datetime
from typing import Optional
from peewee import Database, Model, ModelSelect

db: Database

def init_db() -> None:
    """_Initialize database and apply migrations_"""
    pass

class User(Model):
    id: int
    """_id from telegram_"""
    username: Optional[str]
    admin: bool
    
    iscrizioni_eventi: ModelSelect['EventSerieSubscription']

class Chat(Model):
    id: int
    """_id from telegram_"""
    title: Optional[str]
    
    event_series: ModelSelect['EventSerie']

class EventSerie(Model):
    id: int
    chat: Chat
    title: str
    default_event_time: datetime.time
    default_remind_time: datetime.time
    day_of_week: int
    """_Domain: 0 (Monday) --> 6 (Sunday)_"""
    start_date: datetime.date
    end_date: datetime.date
    is_active: bool

    partecipanti: ModelSelect['EventSerieSubscription']
    events: ModelSelect['ActualEvent']

class EventSerieSubscription(Model):
    event_serie: EventSerie
    user: User

class ActualEvent(Model):
    id: int
    event_serie: EventSerie
    event_datetime: datetime.datetime
    remind_datetime: datetime.datetime
    status: str
    note: Optional[str]