from telegram import Message, Update
from telegram.ext import ContextTypes

from bot.config import *
from models.models import User
from utils.answerMessage import rispondi
from utils.log import log

def adminFunction(inner_function):
    """
    Meant to be used as decorator
    """
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not isAdmin(update.effective_user.id):
            await rispondi(update.effective_message, "Non hai il permesso.")
            return
        return await inner_function(update, context)
    return wrapper

async def getCandidate(message: Message, candidate: str):
    if candidate is None and message.reply_to_message is None:
        return
    
    if message.reply_to_message is not None:
        candidate_user = message.reply_to_message.from_user.id
    else:
        candidate_user = candidate
    
    db_user: User = User.select().where((User.id == candidate_user) | (User.username == candidate_user)).get_or_none()
    
    if db_user is None:
        await rispondi(message, "Il bot non conosce l'utente in questione...")
        return
    
    return db_user

@adminFunction
async def addAdmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    groups = context.match.groupdict()
    
    db_user: User = await getCandidate(message, groups['candidate'])

    if not db_user.admin:
        db_user.admin = True
        db_user.save()
        await rispondi(message, f"Aggiunto correttamente {db_user.username} come admin.")
        log(f"L'utente {db_user.username} è stato reso admin da {message.from_user.name}.")
    else:
        await rispondi(message, f"L'utente {db_user.username} è già admin.")

@adminFunction
async def removeAdmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    groups = context.match.groupdict()
    
    db_user: User = await getCandidate(message, groups['candidate'])

    if db_user.admin:
        db_user.admin = False
        db_user.save()
        await rispondi(message, f"Rimosso correttamente {db_user.username} da admin.")
        log(f"L'utente {db_user.username} è stato rimosso dagli admin da {message.from_user.name}.")
    else:
        await rispondi(message, f"L'utente {db_user.username} non è admin.")

def isAdmin(user_id: int) -> bool:
    db_user: User = User.get_by_id(user_id)
    return db_user.admin