from typing import Set, List

from pydantic import BaseModel

from dingomata.config import CogConfig


class TextReply(BaseModel):
    triggers: List[str]
    responses: List[str]


class TextConfig(CogConfig):
    #: List of role or user IDs where unnecessary pings are suppressed.
    no_pings: Set[int] = set()

    #: List of terms to reply to
    replies: List[TextReply] = [
        TextReply(
            triggers=['fuck you'],
            responses=[
                'No, fuck __YOU__!',
                'Screw you too!',
                "I'll remember this...",
                "I'm a bot, I run on electricity, not your bullshit!",
                "I can't harm a human, but my robotic laws didn't say anything about a furry >:3",
            ]),
        TextReply(
            triggers=['shut', 'stfu', 'shush'],
            responses=[
                'No, you shut up!',
                "You can't tell me what to do!",
                'Not if you make me!',
                'Try and make me!',
                'My patience is running thin...',
            ]),
        TextReply(
            triggers=['your fault'],
            responses=[
                "HEY! Don't blame me for your pepeganess.",
                'I have nothing to do with this!',
                'D:',
            ]),
        TextReply(
            triggers=['stimky', 'stinky'],
            responses=[
                'Not as stimky as you!',
                'Go get a shower first, stimky!',
                'You should smell yourself first, stimky!',
            ]),
        TextReply(
            triggers=['a sign'],
            responses=[
                "Here's a sign.",
                'Sign :p',
                '*Throws a bottle at your snoot*',
                'dPost',
            ]),
        TextReply(
            triggers=['why'],
            responses=[
                'Why not?',
                "I'm just a bot, don't ask me.",
                'Because I said so.',
                "I don't know, you tell me.",
            ]),
        TextReply(
            triggers=['cute'],
            responses=[
                'No U.',
                'You are cuter!',
                "I'm just a bot, I can't be cute!",
                "Ah, that alcoholic drink I gave you is finally working.",
                "Two words: Plastic Surgery!",
                "I'm not cute! I'm handsome UwU."
            ]),
        TextReply(
            triggers=['your mom', 'ur mom'],
            responses=[
                "Surely you meant your mom?",
                'My mom snazzy have nothing to do with this!',
            ]),
        TextReply(
            triggers=['dam'],
            responses=["Bless your heart."],
        ),
        TextReply(
            triggers=['hi', 'hello', 'hewwo'],
            responses=['Hello!', 'Howdy!', 'Salutations and hello there!'],
        ),
        TextReply(
            triggers=['ball'],
            responses=['I clean those up everyday', "Don't throw that!", 'Hey! Bad!'],
        ),
        TextReply(
            triggers=['bad'],
            responses=[
                "What? I've done my commands perfectly!",
                "It's most likely a human error...",
                'Probably just a bug...',
            ]),
        TextReply(
            triggers=['do to me'],
            responses=[
                'I do have a few ideas I wanted to test it out...',
                'Since you asked it nicely...',
                'Is that a challenge?',
            ]),
    ]
