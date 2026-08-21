from telegram import Update, ChatMember
from telegram.ext import ContextTypes


async def is_user_groupadmin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Verifica se l'utente che lancia il comando è amministratore della chat."""
    
    return update.effective_user.id in [k.user.id for k in await update.effective_chat.get_administrators(False)]