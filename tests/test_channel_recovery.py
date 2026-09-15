"""Recovery regressions, isolated from credentials and production services."""
import ast
import asyncio
import logging
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]


def load_class(path, name, **namespace):
    tree = ast.parse((ROOT / path).read_text())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name)
    if name == "TwitchBot":
        cls.bases = []
        cls.body = [node for node in cls.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {"_connection_is_ready", "_liihs_membership_ok", "connection_watchdog"}]
    exec(compile(ast.Module(body=[cls], type_ignores=[]), path, "exec"), namespace)
    return namespace[name]


class RecoveryTests(unittest.IsolatedAsyncioTestCase):
    def manager(self, statuses):
        responses = iter(statuses)

        class Response:
            async def __aenter__(self):
                self.status = next(responses)
                return self

            async def __aexit__(self, *args):
                pass

            async def json(self):
                return {"data": [{"user_login": "live", "game_id": "138585"}]}

        class Session(Response):
            async def __aenter__(self):
                return self

            def get(self, *args, **kwargs):
                return Response()

        cls = load_class("src/managers/channel_manager.py", "ChannelManager", Set=set, os=os, asyncio=asyncio,
                         logger=logging.getLogger("test"), get_all_live_channels=lambda: {f"channel{i}" for i in range(51)},
                         aiohttp=SimpleNamespace(ClientSession=lambda **kw: Session(), ClientTimeout=lambda **kw: None))
        obj = cls.__new__(cls)
        obj.hearthstone_channels = {"previous"}
        return obj

    async def test_partial_api_failure_preserves_previous_snapshot(self):
        manager = self.manager([200, 503])
        with patch.dict(os.environ, TWITCH_CLIENT_ID="test", TWITCH_TOKEN="test"), patch.object(asyncio, "sleep", new=AsyncMock()):
            with self.assertRaises(RuntimeError):
                await manager.get_live_channels()
        self.assertEqual(manager.hearthstone_channels, {"previous"})

    async def test_success_publishes_complete_snapshot(self):
        manager = self.manager([200, 200])
        with patch.dict(os.environ, TWITCH_CLIENT_ID="test", TWITCH_TOKEN="test"), patch.object(asyncio, "sleep", new=AsyncMock()):
            self.assertEqual(await manager.get_live_channels(), {"live"})
        self.assertEqual(manager.hearthstone_channels, {"live"})

    async def test_database_failure_propagates(self):
        manager = self.manager([])
        manager.load_channels = lambda: (_ for _ in ()).throw(OSError("database unavailable"))
        with self.assertRaises(OSError):
            await manager.get_live_channels()

    async def test_open_socket_without_membership_triggers_restart(self):
        kill = unittest.mock.Mock()
        cls = load_class("src/twitchBot.py", "TwitchBot", asyncio=asyncio, time=SimpleNamespace(monotonic=lambda: 400),
                         os=SimpleNamespace(kill=kill, getpid=lambda: 123), signal=SimpleNamespace(SIGTERM=15), logger=logging.getLogger("test"))
        bot = cls()
        bot._connection = SimpleNamespace(is_alive=True, is_ready=SimpleNamespace(is_set=lambda: True))
        bot.get_channel = lambda name: SimpleNamespace(get_chatter=lambda nick: None)
        bot.nick = "walliibot"
        bot.connection_lost_at = 1
        bot.reconnect_grace_period = 300
        await bot.connection_watchdog()
        kill.assert_called_once_with(123, 15)


if __name__ == "__main__":
    unittest.main()
