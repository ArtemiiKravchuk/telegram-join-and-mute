# telegram-join-and-mute

Joins telegram channels and mutes them

In `config.ini` store paths to .csv files:
1. List of all telethon session names (if several accounts are joining channels)
2. Channels to join: it's name, id and invite hash (part of the invite link after `+`)
   
(keep headers, the first row is skipped!!)

You can get `api_id` and `api_hash` from [here](https://my.telegram.org/auth).
