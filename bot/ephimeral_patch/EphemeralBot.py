from typing import Optional, Union

from telegram.ext import ExtBot
from telegram import Message

from bot.ephimeral_patch.EphemeralMessageParameters import EphemeralMessageParameters
from bot.ephimeral_patch.EphemeralReplyParameters import EphemeralReplyParameters

def make_ephemeral_kwargs(
    ephemeral_params: EphemeralMessageParameters,
    reply_params: Optional[EphemeralReplyParameters] = None,
    existing_api_kwargs: Optional[dict] = None
) -> dict:
    kwargs = dict(existing_api_kwargs or {})
    kwargs["ephemeral_message_parameters"] = ephemeral_params.to_dict()
    
    if reply_params:
        kwargs["reply_parameters"] = reply_params.to_dict()
        
    return kwargs

class EphemeralExtBot(ExtBot):
    """Temporary patch for ephimeral messages in python-telegram-bot"""
    async def send_ephemeral_message(
        self,
        chat_id: Union[int, str],
        text: str,
        ephemeral_parameters: EphemeralMessageParameters,
        reply_parameters: Optional[EphemeralReplyParameters] = None,
        api_kwargs: Optional[dict] = None,
        **kwargs
    ) -> Message:
        extra_kwargs = make_ephemeral_kwargs(
            ephemeral_params=ephemeral_parameters,
            reply_params=reply_parameters,
            existing_api_kwargs=api_kwargs
        )

        return await self.send_message(
            chat_id=chat_id,
            text=text,
            api_kwargs=extra_kwargs,
            **kwargs
        )

    async def edit_ephemeral_message_text(
        self,
        text: str,
        chat_id: Optional[Union[int, str]] = None,
        message_id: Optional[int] = None,
        inline_message_id: Optional[str] = None,
        **kwargs
    ) -> Union[Message, bool]:
        data = {"text": text, **kwargs}
        if chat_id:
            data["chat_id"] = chat_id
        if message_id:
            data["message_id"] = message_id
        if inline_message_id:
            data["inline_message_id"] = inline_message_id

        return await self._post("editEphemeralMessageText", data=data)