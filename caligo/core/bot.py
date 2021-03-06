import asyncio
import logging
from typing import Optional

import aiohttp
import pyrogram

from .command_dispatcher import CommandDispatcher
from .database import DataBase
from .event_dispatcher import EventDispatcher
from .module_extender import ModuleExtender
from .telegram_bot import TelegramBot


class Bot(TelegramBot, CommandDispatcher, DataBase, EventDispatcher,
          ModuleExtender):
    client: pyrogram.Client
    http: aiohttp.ClientSession
    lock: asyncio.Lock
    log: logging.Logger
    loop: asyncio.AbstractEventLoop
    stopping: bool

    def __init__(self):
        self.log = logging.getLogger("Bot")
        self.loop = asyncio.get_event_loop()
        self.stopping = False

        super().__init__()

        self.http = aiohttp.ClientSession()

    @classmethod
    async def create_and_run(cls,
                             *,
                             loop: Optional[asyncio.AbstractEventLoop] = None
                            ) -> "Bot":
        bot = None

        if loop:
            asyncio.set_event_loop(loop)

        try:
            bot = cls()
            await bot.run()
            return bot
        finally:
            if bot is None or (bot is not None and not bot.stopping):
                asyncio.get_event_loop().stop()

    async def stop(self) -> None:
        self.stopping = True

        await self.dispatch_event("stop")

        self.log.info("Stopping")
        if self.loaded:
            await self.dispatch_event("stop")
        await self.http.close()
        await self.close_db()

        async def finalize() -> None:
            lock = asyncio.Lock()

            async with lock:
                if self.client.is_initialized:
                    await self.client.stop()
                for task in asyncio.all_tasks():
                    if task is not asyncio.current_task():
                        task.cancel()
                await self.loop.shutdown_asyncgens()
                self.loop.stop()

        self.log.info("Running post-stop hooks")
        if self.loaded:
            await finalize()
            await self.dispatch_event("stopped")
        else:
            self.loop.stop()
