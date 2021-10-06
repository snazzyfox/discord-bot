from functools import cached_property
from pathlib import Path
from typing import Set, List

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
        return re.compile('|'.join(rf'\b{t}\b' for t in self.triggers), re.IGNORECASE)


class TextConfig(CogConfig):
    #: List of role or user IDs where unnecessary pings are suppressed.
    no_pings: Set[int] = set()

    #: List of terms to reply to
    replies: List[TextReply] = [
        TextReply.parse_obj(entry)
        for entry in yaml.safe_load_all((Path(__file__).parent / 'text_response_data.yaml').open())
    ]
