import asyncio
import json
import uuid
import websockets

async def go():
    async with websockets.connect("ws://127.0.0.1:8000/events") as ws:
        await ws.send(json.dumps({
            "event_id": str(uuid.uuid4()),
            "event_type": "test",
            "payload": {"x": 1}
        }))
        await asyncio.sleep(1)

asyncio.run(go())
