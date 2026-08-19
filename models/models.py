from peewee import SqliteDatabase, Model, IntegerField, TextField, BooleanField
from peewee_migrate import Router

# Connettiamo al database SQLite
db = SqliteDatabase('secret/Database.db')
router = Router(db, migrate_dir='migrations')

def init_db():
    """_Initialize database and apply migrations_"""
    router.run()

class BaseModel(Model):
    class Meta:
        database = db
        
class Utente(BaseModel):
    id = IntegerField(primary_key=True)
    username = TextField(null=True)
    admin = BooleanField(default=False)
    
class Chat(BaseModel):
    id = IntegerField(primary_key=True)
    title = TextField(null=True)