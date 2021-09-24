from typing import Set, Dict

from dingomata.config import CogConfig


class TextConfig(CogConfig):
    #: List of role or user IDs where unnecessary pings are suppressed.
    no_pings: Set[int] = set()

    #: List of terms to reply to
    replies: Dict[str, str] = {
        'fuck you': 'No, fuck __you__!',
        'shut': 'No, you shut up!',
        'stfu': 'No, you shut up!',
        'shush': 'No, you shut up!',
        'your fault': "HEY! Don't blame me for your pepeganess.",
        'stimky': 'Not as stimky as you!',
        'stinky': 'Not as stinky as you!',
        'a sign': "Here's a sign.",
        'why': 'Why not?',
        'cute': 'No U.',
        'ur mom': "Surely you meant your mom? Because I don't have a mom.",
        'your mom': "Surely you meant your mom? Because I don't have a mom.",
        "damn": "Bless your heart.",
    }
