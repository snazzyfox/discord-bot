from functools import cached_property
from pathlib import Path
from typing import Set, List
from zlib import decompress

import yaml
import re
from pydantic import BaseModel
from dingomata.config import CogConfig


class TextReply(BaseModel):
    triggers: List[str]
    responses: List[str]

    class Config:
        keep_untouched = (cached_property,)

    @cached_property
    def regex(self) -> re.Pattern:
        return re.compile('|'.join(rf'(?:^|\b|\s){t}(?:$|\b|\s)' for t in self.triggers), re.IGNORECASE)


def _get_text_replies() -> List[TextReply]:
    with (Path(__file__).parent / 'text_response_data.yaml').open() as data:
        return [TextReply.parse_obj(entry) for entry in yaml.safe_load_all(data)]


def _get_wheel_replies() -> List[TextReply]:
    with (Path(__file__).parent / 'wheel.bin').open('rb') as bindata:
        bindata.seek(2, 0)
        textdata = decompress(bindata.read())
        return [TextReply.parse_obj(entry) for entry in yaml.safe_load_all(textdata)]


class TextConfig(CogConfig):
    #: List of role or user IDs where unnecessary pings are suppressed.
    no_pings: Set[int] = set()

    #: List of terms to reply to
    replies: List[TextReply] = _get_text_replies()

    #: Responses for the wheel (obfuscated)
    wheel: List[TextReply] = _get_wheel_replies()
