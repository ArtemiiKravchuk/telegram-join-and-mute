from datetime import datetime
import configparser
import logging
import csv
import sys

from loguru import logger

from telethon import TelegramClient, functions, types
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.errors.rpcerrorlist import UserAlreadyParticipantError
from telethon.errors.rpcerrorlist import FloodWaitError


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


async def mute_channel(client, channel_id: str, channel_name: str) -> None:

    logger.info("Attempt to mute {}, where channel_id = {}",
                channel_name, channel_id)
    await client(functions.account.UpdateNotifySettingsRequest(
        peer=int(channel_id),
        settings=types.InputPeerNotifySettings(
            mute_until=2**31 - 1
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


async def send_notification(bot_client, service_bot_group: str,
                            session_name: str, channel_name: str):

    logger.info("Sending notification to {}", service_bot_group)

    await bot_client.send_message(int(service_bot_group), f"""
🔇 **{session_name}** joined and muted **{channel_name}**
__at {datetime.now().strftime("%H:%M:%s")}__
                                  """, link_preview=False)


async def process_channel(client, session, bot_client, channel_name: str,
                          channel_id: str, invite_hash: str,
                          service_bot_group: str) -> None:

    await join_channel(client, channel_name, invite_hash)
    await mute_channel(client, channel_id, channel_name)

    await send_notification(bot_client, service_bot_group,
                            session, channel_name)


def process_account(bot_client, api_id: str, api_hash: str,
                    session: str, channels: list):

    service_bot_group = config["SERVICE_BOT"]["notification_group_id"]

    logger.info("Connecting to account, session file name: {}", session)

    with TelegramClient(session, api_id, api_hash) as client:
        for channel_id in channels.keys():
            channel_name = channels[channel_id][0]
            invite_hash = channels[channel_id][1]
            logger.debug("Retrieved info about {}: id={}, invite_hash={}",
                         channel_name, channel_id, invite_hash)

            client.loop.run_until_complete(
                process_channel(client, session, bot_client, channel_name,
                                channel_id, invite_hash, service_bot_group)
            )


def main():
    logger.debug("Reading config.ini data")

    accounts = read_accounts(config["DATA"]["sessions"])
    channels = read_channels(config["DATA"]["channels"])

    api_id = config["TG_CORE"]["api_id"]
    api_hash = config["TG_CORE"]["api_hash"]

    service_bot_token = config["SERVICE_BOT"]["token"]
    service_bot_session = config["SERVICE_BOT"]["session_name"]

    bot_client = TelegramClient(service_bot_session, api_id, api_hash).start(
        bot_token=service_bot_token)

    for account in accounts:
        process_account(bot_client, api_id, api_hash, account, channels)


if __name__ == "__main__":
    main()
