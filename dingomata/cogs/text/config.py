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
            triggers=['fuck you', 'frick you', 'you suck', 'hate you'],
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
        #Secret list. To all our amazing friends (this is purly bias, please don't think dingomata doesn't like you, if you are watching this owo)
        #There are many friends I don't know that well. I'm sorry if I cannot describe them better! ;w;
        TextReply(
            triggers=['banana'],
            responses=[
                "Our favorite, cute and very athletic husky! To our husky that's full of love! Athlete!",
            ]),
        triggers=['shooting star'],
            responses=[
                '"Here comes the shooting star!" And here comes brightest star in the sky! To our amazing shiba star, Galex!',
            ]),
        TextReply(
            triggers=['blueberry'],
            responses=[
                'Blueberry pie? yum yum! Our favorite, amazing and friendly blueberry wolf! Lycaon!',
            ]),
            TextReply( 
        triggers=['snaz', 'snazzy'],
            responses=[
                'Our residential gentleman fox, very smart and creative! The one and only Snazzy!',
            ]),
        triggers=['lycan', 'mike', 'michael','werewolf'],
            responses=[
                'AWOO! Our favorite, one and only, rare find werewolf. To our werewolf friend, LycanMike! "Salutations and hello there!"',
            ]),
        triggers=['tail'],
            responses=[
                '"NO PUT THAT DOWN, YOU ARE NOT SUPPOSE TO HAVE THAT TAIL!" To our amazing tail snatcher, DT!',
            ]),
        triggers=['short'],
            responses=[
                'YES, I can make the dingomata call you short corgi, there is no stopping it now! To our amazing friend, Corgi!',
            ]),
        triggers=['maid outfit'],
            responses=[
                "oh god, no, now you made everyone even cuter! Thank you for all your amazing art, and I'm sure neo is appreciating them.  To our amazing artist, Luna!",
            ]),
        triggers=['fire'],
            responses=[
                ".. and here he is, our fire wolf... He really should sto- wait, no, stop, YOU CAN'T THROW ME INTO- ||To our fire keeper, Neo!||",
            ]),
        triggers=['doritos'],
            responses=[
                'YUMMY DORITOS! wait. did you check if dogueritos is in there, galex? oh god. NOOOOOOOOOOO!!!!! To our wonderful loving bean, dogueritos!',
            ]),
        triggers=['coffee'],
            responses=[
                "Drink your daily starbucks, or you shoudn't call yourself a certified forklift driver! To our wonderful coffee bean, Forklift!",
            ]),
        triggers=['where is the wolf'],
            responses=[
                "where? wolf? I don't see any wolf around, where is it again? AHH there he is! Our wonderful friend with incredible voice, wherewolf!",
            ]),
        triggers=['smol drag'],
            responses=[
                "Oh, hold that with care! You don't want to drop her! She is really talented and creative. To our small dragon, Gem!",
            ]),
        triggers=['sushi'],
            responses=[
                "OHHH shushi... hmm it tastes funny... what kind of fish did you use? **SHARK MEAT?** IT'S NOT HONDA IS IT! GOD DAMN IT! EXOS! WIA- ||To our hyper fish, Honda!||",
            ]),
        triggers=['le chein'],
            responses=[
                'Aww so cute! Shy and adorable friend, so loving and amazing, "also incredibly gay". To our french dogo, Exos!',
            ]),
        triggers=['mango'],
            responses=[
                'YUMM! wait ohh you mean the other mango. To our amazing australia golden retriever, and an incredible friend , Mango!',
            ]),
        triggers=['dusty'],
            responses=[
                'HOWDY PPARTNER, NEEDS SOME MOOD LIFTING? TO OUR AMAZINGLY CUTE LOVING HYPER FRIENDLY SOFT-HEARTED ARCANINE, GG!',
            ]),
        triggers=['daddy UwU'],
            responses=[
                'Amazing artist, friend, even if he is on the other side of the planet, he is still so amazing. To our amazing fluffy Ronzuko!',
            ]),
        triggers=['bear'],
            responses=[
                "I'm sorry what? I thought thet maximun is 4? Wha- To our extremely smart and talented, amazing friend, Koda!",
            ]),
        triggers=['cat'],
            responses=[
                'He is a cat? He is a husky? What is he? If he is a cat when why his pfp is a husky? If he is a husky then why is his name cat? `ERROR LOGICAL MEMORY INSUFFICIENT`. To our amazingly computer techi, Neko!',
            ]),
        triggers=['bunny'],
            responses=[
                'Soft, gentle and must handle with care. Deserve all the loves and friends. To our amazing bunny JML!',
            ]),
        triggers=['roden'],
            responses=[
                "*smoll squeak noise* Oh hello there! Didn't notice you before! hullo smoll friend! To our amazing quiet and friendly bean, Rodney!",
            ]),
        triggers=['dingo'],
            responses=[
                'OUR LORD AND SAVIOR. THE ONE. WHO IS INCREDIBLY FRIENDLY, WELCOMEING, ENERGETIC, ||AND DARE I SAY CUTE|| DINGO, WHISKEY DINGO! THANK YOU FOR CREATING SUCH PLACE FULL OF LOVE AND CARE AND FILLED WITH AMAZING PEOPLE.',
            ]),
        triggers=['white dude'],
            responses=[
                "*Bottom noise* Oh. Aren't you suppose to be somewhere else? Sh- To our amazing, generous and exists in every stream possible. Our black wolf, Bairen!",
            ]),
        triggers=['lllllll'],
            responses=[
                '"lllllllllllleeeeeeeeeeeeepppppppppppppp" AAAAAAAAAAAAAAAAAAAAAAAAAAA. To our chaotic, yet generous fox also full of love and care, Tomi!',
            ]),
        triggers=['critically acclaimed'],
            responses=[
                "Did you know that the critically acclaimed MMORPG Final Fantasy XIV has a free trial, and includes the entirety of A Realm Reborn AND the award-winning Heavensward expansion up to level 60 with no restrictions on playtime? Sign up, and enjoy Eorzea today! To our amazing mod, Cyrcle!",
            ]),
        triggers=['drag'],
            responses=[
                'Deep voiced and yet friendly beeg dragon! Our amazing friend derg!',
            ]),
        triggers=['shepi'],
            responses=[
                'Hey where is that arc-? Oh you have him? nvm, yea there he is, right down there. To our lewd, cheeky and yet loving and care. Our amazing friend, Shep!',
            ]),
        triggers=['furret'],
            responses=[
                'YOU MAD FERRET! WDAISDNWIAD. To our amazing, extremely generous ferret, Seth!',
            ]),
        triggers=['trash panda'],
            responses=[
                "Hey You aren't suppose to be in that trash can! Oh, awww look how cute you look... Okie.. Maybe you can stay a bit longer in there.. To our amazing friend, Ramon!",
            ]),
        triggers=['stirr'],
            responses=[
                'AHHHHHHHH, You huged dogueritos to death yet again!!! NOOOOOOOO! To our amazingly wolf who loves tackle hugs everyone, Stirring!',
            ]),
        triggers=['nurse UwU'],
            responses=[
                'UWU I HAVE A ITCH, nurse UWU. To our amazing friend who is being amazing, Sellsy!',
            ]),
        triggers=['steel'],
            responses=[
                'A gentle fox who is very gentle! Quiet but yet lovingly, our amazing friend, Steel!',
            ]),
    ]
