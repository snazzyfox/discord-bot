import random
import re
from functools import cached_property
from itertools import accumulate
from pathlib import Path
from typing import Set, List, Union, Dict
from zlib import decompress

import yaml
from pydantic import BaseModel, confloat, PrivateAttr

from dingomata.config import CogConfig


class TriggerTextReply(BaseModel):
    triggers: List[str]
    responses: List[str]

    class Config:
        keep_untouched = (cached_property,)

    @cached_property
    def regex(self) -> re.Pattern:
        return re.compile('|'.join(rf'(?:^|\b|\s){t}(?:$|\b|\s)' for t in self.triggers), re.IGNORECASE)


def _get_text_replies() -> List[TriggerTextReply]:
    with (Path(__file__).parent / 'text_responses.bin').open('rb') as bindata:
        bindata.seek(2, 0)
        textdata = decompress(bindata.read())
        return [TriggerTextReply.parse_obj(entry) for entry in yaml.safe_load_all(textdata)]


class RandomTextChoice(BaseModel):
    content: str
    probability: confloat(gt=0) = 1.0  #: Note: probabilities don't have to add up to 1. They'll be normalized.


class RandomTextChoiceList(BaseModel):
    __root__: List[Union[RandomTextChoice, str]]
    _weights: List[float] = PrivateAttr()

    def __init__(self, __root__: List[Union[RandomTextChoice, str]], **kwargs):
        for idx, value in enumerate(__root__):
            if isinstance(value, str):
                __root__[idx] = RandomTextChoice(content=value, probability=1.0)
        super().__init__(__root__=__root__, **kwargs)
        self._weights = list(accumulate(choice.probability for choice in self.__root__))

    def choose(self) -> str:
        return random.choices(population=self.__root__, cum_weights=self._weights)[0].content


class RandomTextReply(BaseModel):
    templates: RandomTextChoiceList
    fragments: Dict[str, RandomTextChoiceList] = {}

    def render(self, **kwargs) -> str:
        fragments = {k: v.choose() for k, v in self.fragments.items()}
        template = self.templates.choose()
        return template.format(**fragments, **kwargs)


def _get_random_text_replies() -> Dict[str, RandomTextReply]:
    with (Path(__file__).parent / 'random_response_data.yaml').open() as data:
        return {k: RandomTextReply.parse_obj(v) for k, v in yaml.safe_load(data).items()}


class TextConfig(CogConfig):
    #: List of role or user IDs where unnecessary pings are suppressed.
    no_pings: Set[int] = set()

    #: Text data
    rawtext_replies: List[TriggerTextReply] = _get_text_replies()
    random_replies: Dict[str, RandomTextReply] = _get_random_text_replies()
