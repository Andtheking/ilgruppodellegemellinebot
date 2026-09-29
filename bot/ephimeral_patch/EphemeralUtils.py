from typing import Optional, Tuple
from telegram import Message, Update

from bot.ephimeral_patch.EphemeralMessageParameters import EphemeralMessageParameters
from bot.ephimeral_patch.EphemeralReplyParameters import EphemeralReplyParameters

def extract_ephemeral_id(message: Message) -> Optional[int]:
    if not message:
        return None
    if hasattr(message, "api_kwargs") and "ephemeral_message_id" in message.api_kwargs:
        return message.api_kwargs["ephemeral_message_id"]
    if getattr(message, "reply_parameters", None):
        reply_kwargs = getattr(message.reply_parameters, "api_kwargs", {})
        if "ephemeral_message_id" in reply_kwargs:
            return reply_kwargs["ephemeral_message_id"]
    return message.to_dict().get("ephemeral_message_id")

def build_ephemeral_reply_context(update: Update) -> Tuple[EphemeralMessageParameters, Optional[EphemeralReplyParameters]]:
    """_Extracts and builds the parameters required to send an ephemeral reply to an update._

    Args:
        update (Update): _The incoming Telegram update containing the message and user context._

    Returns:
        Tuple[EphemeralMessageParameters, Optional[EphemeralReplyParameters]]: _A tuple containing the mandatory ephemeral parameters configured for the effective user, and the reply parameters targeting the ephemeral message ID if present in the incoming update._
    """
    user_id = update.effective_user.id
    query = update.callback_query
    if query:
        ephem_params = EphemeralMessageParameters(
            receiver_user_id=user_id,
            callback_query_id=query.id,
            replace_callback_query_message=False 
        )
        return ephem_params, None

    ephemeral_id = extract_ephemeral_id(update.effective_message)
    ephem_params = EphemeralMessageParameters(receiver_user_id=user_id)
    
    repl_params = None
    if ephemeral_id:
        repl_params = EphemeralReplyParameters(ephemeral_message_id=ephemeral_id)

    return ephem_params, repl_params