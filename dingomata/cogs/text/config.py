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
        #HIGH/Ordered-priority responses
        TextReply(
            triggers=['fuck you', 'frick you', 'you suck', 'I hate'],
            responses=[
                'No, fuck __YOU__!',
                'Screw you too!',
                "I'll remember this...",
                "I'm a bot, I run on electricity, not your bullshit!",
                "I can't harm a human, but my robotic laws didn't say anything about a furry >:3",
            ]),
        TextReply(
            triggers=['bot'],
            responses=[
                "Maybe I am, maybe I'm not...",
                'You cannot compute my ability.',
                'Only if I am connected to the internet...',
            ]),
        TextReply(
            triggers=['why', "can"],
            responses=[
                'Why not?',
                "I'm just a bot, don't ask me.",
                'Because I said so.',
                "I don't know, you tell me.",
                'Have you tried the 8Ball?',
            ]),
        TextReply(
            triggers=['hi', 'hello', 'hewwo','hey'],
            responses=['Hello!', 'Howdy!', 'Salutations and hello there!'],
        ),
        TextReply(
            triggers=['is'],
            responses=[
                '**"YES, A TOMATO IS A FRUIT"**',
            ]),
            #Piror of "love" check, making sure user intention is good
        TextReply(
            triggers=['i loves', ' i love', 'i likes', 'i like'], 
            responses=[
                'Aww',
                'I appreciate it',
                "You shouldn't have",
                'Thank you!',
            ]),
        #After of "i love" check, making sure user intention is not for good
        TextReply(
            triggers=['loves you', 'love you', 'likes you', 'like you'],
            responses=[
                "I am a bot, I'm indifferent about love.",
                "You should check your phone's contact list first.",
                "I tried hacking into your social media, but I was keep getting an error saying something like `null friend list`...",
                "I feel no emotion, but I can't say the same thing about you... :wdingDEVIL:",
            ]),
        #After all love check. A more general variation.
        TextReply(
            triggers=['love'],
            responses=[
                "<3",
                'Absolutely.',
                'yes.',
            ]),
            #Prior to "friend" to make sure friend is not checked first and it's good intention
        TextReply(
            triggers=['my friend'], 
            responses=[
                'Yes.',
                'Only if you think me as one <3.',
                'YAY!',
                'FRIENDS!',
            ]),
        #After "my friend" check instance, for example as "you have no friend etc" for bad intention
        TextReply(
            triggers=['friend'], 
            responses=[
                'You should ask yourself that question.',
                'Yes... I will add you on **THE LIST**',
                'I have many connections, there are ways to make you regret',
            ]),
            #Prior to funny
        TextReply(
            triggers=["isn't funny", "aren't funny", 'not funny'], 
            responses=[
                "It's funny... Not the way you thought of it.",
                'Human logic confuses me.',
                'There are ways to make it funny.',
                'Perhaps, but I think it is funny.',
            ]),
        #After not funny
        TextReply(
            triggers=['funny'], 
            responses=[
                'Thanks',
                'At least someone appreciate my sense of humor.',
                'I will update it into the database.',
            ]),
        #MEDIUM/random-priority responses, Mid sentence check
        TextReply(
            triggers=['gay', 'homosexual', 'lewd', 'horni'],
            responses=[
                'I am a bot, I only have love for electricity...Amongst other things...',
                'OwO',
                'It just comes naturally for some people.',
                'It seems my algorithm is working as intended.',
            ]),
        TextReply(
            triggers=['daddy'],
            responses=[
                'Based on my calculation, I am much younger than you, you must mistaken me for someone else.',
                "I am sorry but the number you are trying to reach is Unavailable, please wait and try again.",
                'DMs',
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
            triggers=['your fault', 'dank'],
            responses=[
                "HEY! Don't blame me for your pepeganess.",
                'I have nothing to do with this!',
                'D:',
            ]),
        TextReply(
            triggers=['furry', 'furries'],
            responses=[
                'Oh, I think I have few down in the basement.',
                'Internet animals?'
                "I needs to research them more... Will you volutneer?",
                'You mean you?',
        TextReply(
            triggers=['sus', 'sussy'],
            responses=[
                'Hey! You where the one who vented!',
                'I an a bot, I cannot hearm human!',
                'I have no idea what you are talking about.',
            ]),
        TextReply(
            triggers=['dank'],
            responses=[
                'This is the way',
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
            triggers=['dad','father'],
            responses=[
            'No.',
            ],
        ),
        TextReply(
            triggers=['dam','shit'],
            responses=["Bless your heart."],
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
        #LOW-priority responses, fail safe
        TextReply(
            triggers=['single pringle', 'single'],
            responses=[
                'I will be your friend!',
                'Appreciate the people you already have...',
                ''
            ]),
        TextReply(
            triggers=['alone', 'lonely'],
            responses=[
                '*https://www.youtube.com/watch?v=n3Xv_g3g-mA*',
                'I am here.',
                "It's very normal to feel that, you are not the only one.",
            ]),
        TextReply(
            triggers=['a'],
            responses=[
                'AA',
                'AAA',
                'AAAA', 
                'a mong-',
            ]),
        TextReply(
            triggers=['?'],
            responses=[
                "What's that look?",
                'I cannot answer your question.',
                "Maybe it's best that you ask someone else.",
                'Maybe you should ask 8ball.',
            ]),
    ]
