from typing import Set, Dict
from random import choice

from dingomata.config import CogConfig


class TextConfig(CogConfig):
    #: List of role or user IDs where unnecessary pings are suppressed.
    no_pings: Set[int] = set()

    #: List of terms to reply to
    replies: Dict[str, str] = {
        'fuck you': choice([
            'No fuck __YOU__!',
            'Screw you too!',
            "I'll remember this...",
            "I'm a bot, I run on electricity, not your bullshit!",
            "I can't harm a human, but my laws didn't say anything about a furry >:3",
        ]),
        'shut': choice([
            'No, you shut up!',
            "you can't tell me what to do!",
            'Not if you make me!',
            'My patience is running thin...',
        ]),
        'stfu': choice([
            'No, you shut up!',
            "you can't tell me what to do!",
            'Not if you make me!',
            'Only if there is a way to does the same to you...',
        ]),
        'shush': choice([
            'No, you shush up!',
            "you can't tell me what to do!",
            'Not if you make me!',
            'Do you say that to everyone?',
        ]),
        'your fault': choice([
            "HEY! Don't blame me for your pepeganess.",
            'I have nothing to do with this!',
            'D:',
        ]),
        'stimky': choice([
            'Not as stimky as you!',
            'Get a shower first, stimky!',
            'You should smell yourself first, stimky!',
        ]),
        'stinky': choice([
            'Not as stinky as you!',
            'Get a shower first, stimky!',
            'You should smell yourself first, stimky!',
        ]),
        'a sign': choice([
            "Here's a sign.",
            'Sign',
            '*Throws a bottle at your snoot*',
        ]),
        'why': choice([
            'Why not?',
            "Why shouldn't I?'",
            'You started it.',
            "I'm just a bot, don't ask me.",
        ]),
        'cute': 'No U.',
        'ur mom': choice([
            "Surely you meant your mom?",
            'My mom snazzy have nothing to do with this!',
        ]),
        'your mom': choice([
            "Surely you meant your mom?",
            'My mom snazzy have nothing to do with this!',
        ]),
        "dam": choice([
            "Bless your heart.",
        ]),
        'hi': choice([
            'Hello!',
            'Salutations and hello there!',
            'howdy',
        ]),
        'ball': choice([
            'I clean those up everyday...',
            "Don't throw that!",
            'Hey! bad!',
        ]),
        'bad': choice([
            "What? I've done my commands perfectly!",
            "It's most likely a human error...",
            'Probably just a bug...'
        ]),
        'do to me': choice([
            'I have a few ideas I wanted to test out...',
            'Since you asked nicely...',
            'Is that a challenge?',
        ]),
    }
