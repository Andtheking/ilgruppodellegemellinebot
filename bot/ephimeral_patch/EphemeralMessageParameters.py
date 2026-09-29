from dataclasses import dataclass, asdict
from typing import Optional, Union

@dataclass
class EphemeralMessageParameters:
    receiver_user_id: int
    callback_query_id: Optional[str] = None
    replace_callback_query_message: Optional[bool] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}