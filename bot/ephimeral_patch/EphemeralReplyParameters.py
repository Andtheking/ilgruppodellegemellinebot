from dataclasses import dataclass, asdict
from typing import Optional, Union

@dataclass
class EphemeralReplyParameters:
    message_id: Optional[int] = None
    chat_id: Optional[Union[int, str]] = None
    ephemeral_message_id: Optional[int] = None
    allow_sending_without_reply: Optional[bool] = None
    quote: Optional[str] = None
    quote_parse_mode: Optional[str] = None

    def to_dict(self) -> dict:
        data = {k: v for k, v in asdict(self).items() if v is not None}
        if "message_id" not in data and "ephemeral_message_id" not in data:
            raise ValueError("One between message_id and ephemeral_message_id must be specified.")
        return data