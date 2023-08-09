import configparser
import logging
import random
import time
import csv
import sys

from loguru import logger

from telethon import TelegramClient, functions, types
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.errors.rpcerrorlist import UserAlreadyParticipantError
from telethon.errors.rpcerrorlist import FloodWaitError
from telethon.tl.types import NotificationSoundDefault


class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists.
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message.
        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage())


logging.basicConfig(handlers=[InterceptHandler()],
                    level=logging.INFO)

config = configparser.ConfigParser()
config.read('config.ini')


async def join_channel(client, channel_name: str, invite_hash: str) -> None:

    logger.info("Attempt to join {}, where invite_hash = {}",
                channel_name, invite_hash)
    try:
        await client(ImportChatInviteRequest(hash=invite_hash))
    except UserAlreadyParticipantError:
        msg = "While trying to join {}, UserAlreadyParticipantError occured"
        logger.warning(msg, channel_name)
    except FloodWaitError:
        logger.error("While trying to join {}, FloodWaitError occured",
                     channel_name)


async def mute_channel(client, channel_id: str, channel_name: str,
                       mode: int) -> None:

    if mode == 0:
        logger.info("Attempt to mute {}, where channel_id = {}",
                    channel_name, channel_id)
        await client(functions.account.UpdateNotifySettingsRequest(
            peer=int(channel_id),
            settings=types.InputPeerNotifySettings(
                mute_until=2**31 - 1
            )
        ))
    else:
        logger.info("Attempt to unmute {}, where channel_id = {}",
                    channel_name, channel_id)
        await client(functions.account.UpdateNotifySettingsRequest(
            peer=int(channel_id),
            settings=types.InputPeerNotifySettings(
                sound=NotificationSoundDefault()
            )
        ))


def read_accounts(file_name: str) -> list:

    logger.info("Reading session file names from {}", file_name)
    sessions = []
    with open(file_name, "r", encoding="UTF-8") as file:
        reader = csv.reader(file)
        next(reader)
        for account in reader:
            sessions.append(account[0])

    return sessions


def read_channels(file_name: str) -> dict:

    logger.info("Reading channels data from {}", file_name)
    channels = {}
    with open(file_name, "r", encoding="UTF-8") as file:
        reader = csv.reader(file)
        next(reader)
        for channel in reader:
            channels.update({channel[1]: [channel[0], channel[2]]})

    return channels


def process_channel(channel_id: str, channel_name: str, invite_hash: str,
                    accounts: list, mode: int) -> None:

    api_id = config["TG_CORE"]["api_id"]
    api_hash = config["TG_CORE"]["api_hash"]

    for account in accounts:
        with TelegramClient(account, api_id, api_hash) as client:
            client.loop.run_until_complete(
                process_account(client, channel_id,
                                channel_name, invite_hash, mode)
            )


async def process_account(client, channel_id: str, channel_name: str,
                          invite_hash: list, mode: int):

    await join_channel(client, channel_name, invite_hash)
    await mute_channel(client, channel_id, channel_name, mode)


def main(mode: int, max_accounts: int):
    accounts = read_accounts(config["DATA"]["sessions"])
    channels = read_channels(config["DATA"]["channels"])

    if max_accounts > len(accounts):
        logger.error("Accounts to use {} > total accounts {}",
                     max_accounts, len(accounts))
        exit(0)
    accounts = random.sample(accounts, max_accounts)
    logger.debug("Sampled random {} accounts from list", max_accounts)

    for channel_id in channels.keys():
        channel_name = channels[channel_id][0]
        invite_hash = channels[channel_id][1]
        logger.debug("Retrieved info about {}: id={}, invite_hash={}",
                     channel_name, channel_id, invite_hash)

        process_channel(channel_id, channel_name, invite_hash, accounts, mode)

        if list(channels.keys())[-1] != channel_id:
            wait = 5
            logger.info("Sleeping for {} s", wait)
            time.sleep(wait)


if __name__ == "__main__":
    mode = int(input("Enter 0 for mute, and 1 for unmute: "))
    max_accounts = int(input("Enter number of accounts to use: "))
    main(mode, max_accounts)
