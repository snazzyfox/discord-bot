# The Party Game Dingomata
A bot that randomly selects users and DM's them a message on Discord. This is intended for more fairly selecting 
players on stream. 

This bot is intended to be run on the host's machine. It can be hosted or ran by someone else, but it's probably not
necessary. It only works with one discord server at a time.

## Getting Started

Before you run the bot, you'll need 
- A channel where the bot posts messages
- A channel where admins control the bot (this should be hidden from public view, otherwise everyone will be able to 
  see the messages you're DMing winners via the bot)

## How it works

The typical way this bot should be used is like this:

- A moderator opens a queue with `+open My Awesome Game`
- The bot posts a message in a channel, such as "The Dingomata is now accepting players for My Awesome Game. 
  React to this message for a chance to join the game!"
- Members join the pool by reacting (any emote) to the message
- Member receives a join successful message via DM. **If their DM is not open, 
- Mod closes the pool with `+close`. Members will no longer be able to join after this
- Mod issues a command like `+pick 8 Game code is ABCD`
- The bot DM's the message to each selected user, like "You've been selected! Game code is ABCD"
- The bot posts a public message in the channel announcing the selected users: "Congrats to @person @person @person. 
  Watch out for DMs!"

The bot also keeps track of which users have been selected in each round, and can be configured so that a user cannot 
join consecutive games.

## Command List

All commands in this list requires moderator permissions (controlled by the `manager_roles` config), and are only 
accepted from moderator channels (controlled by `manage_channel` config).

| Command | Description |
| --- | --- |
| `+open <title>` | Opens the pool for entry. The title parameter is text that can be included in the bot's message. |
| `+close` | Closes the currently open pool. |
| `+pick <count> <message>` | Pick <count> users at random from the pool. These users will be removed from the pool after picking. The pool must be closed first. |
| `+resend <message>` | Send a message to everyone who was last picked. |
| `+clear pool` | Clears the current pool |
| `+clear selected` | Clears the history of selected users, making everyone eligible for the next pool. |
| `+list` | Lists all members who in the current pool. This will not actually mention the users to avoid being bonked by moderation bots.
| `+help` | Displays this list. |

## Configuration File Reference

Options in the `disqueue.cfg` configuration file control how the bot runs. If you change these settings, the bot must 
be restarted for them to take effect. See comments in the file for the meaning of each configuration option.

If necessary, you can also set these configurations using environment variables with the format 
`DINGOMATA_{SECTION}_{KEY}`, for example `DINGOMATA_BOT_TOKEN`. Note that environment variables must be all uppercase.
