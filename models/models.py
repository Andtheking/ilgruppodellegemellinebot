from peewee import (
    AutoField,
    BigIntegerField,
    DateField,
    DateTimeField,
    ForeignKeyField,
    IntegerField,
    SmallIntegerField,
    TextField,
    BooleanField,
    TimeField,
    CompositeKey,
    SqliteDatabase,
    Model
)
from peewee_migrate import Router

db = SqliteDatabase('secret/Database.db', pragmas={'foreign_keys': 1})
router = Router(db, migrate_dir='models/migrations')

def init_db():
    router.run()

class BaseModel(Model):
    class Meta:
        database = db
        
class User(BaseModel):
    id = BigIntegerField(primary_key = True) # tg id
    username = TextField(null = True)
    admin = BooleanField(default = False)
    anilist_username = TextField(null=True)
    
class Chat(BaseModel):
    id = BigIntegerField(primary_key = True) # tg id
    title = TextField(null = True)

class AnilistAnime(BaseModel):
    anilist_media_id = IntegerField(primary_key=True)
    total_episodes = IntegerField(null=True)
    cover_image_url = TextField(null=True)
    
class EventSerie(BaseModel):
    id = AutoField(primary_key = True)
    chat = ForeignKeyField(Chat, backref = 'event_series')
    title = TextField()
    default_event_time = TimeField() 
    default_remind_time = TimeField() 
    day_of_week = SmallIntegerField() # 0 (Monday) --> 6 (Sunday)
    start_date = DateField()
    end_date = DateField()
    is_active = BooleanField(default = True)
    anilist_anime = ForeignKeyField(AnilistAnime, null=True, backref='series')
    current_episode = IntegerField(default=1)

class EventSerieSubscription(BaseModel):
    event_serie = ForeignKeyField(EventSerie, backref = 'partecipanti', on_delete = 'CASCADE')
    user = ForeignKeyField(User, backref = 'iscrizioni_eventi', on_delete = 'CASCADE')

    class Meta:
        primary_key = CompositeKey('event_serie', 'user')

class ActualEvent(BaseModel):
    event_serie = ForeignKeyField(EventSerie, on_delete = 'CASCADE')
    event_datetime = DateTimeField()    
    remind_datetime = DateTimeField()
    status = TextField(default = 'PENDING')
    note = TextField(null=True)

    class Meta:
        indexes = (
            (('status', 'remind_datetime'), False), # that False is "is_unique" param
        )