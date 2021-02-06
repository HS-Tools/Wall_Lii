import asyncio
import logging
from pyslobs import SlobsConnection, ScenesService

async def list_all_scenes(conn):
    print("Available scenes:")
    ss = ScenesService(conn)
    scenes = await ss.get_scenes()
    for scene in scenes:
        print(" - ", scene.name)
    await conn.close()

async def main():
    token = "d9a1a782725fb4aac142689b2263425f2d11a574"

    # Provide any non-default port and IP address here
    conn = SlobsConnection(token)

    # Give CPU to both your task and the connection instance.
    await asyncio.gather(
        conn.background_processing(),
        list_all_scenes(conn)
    )

logging.basicConfig(level=logging.DEBUG)
asyncio.run(main())      