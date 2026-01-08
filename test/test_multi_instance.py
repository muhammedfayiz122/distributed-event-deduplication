import asyncio
import json
import pytest
import websockets
import asyncpg
import os

WS_URL_1 = "ws://127.0.0.1:8000/events"
WS_URL_2 = "ws://127.0.0.1:8002/events"
WS_URL_3 = "ws://127.0.0.1:8003/events"
WS_URL_4 = "ws://127.0.0.1:8004/events"
WS_URL_5 = "ws://127.0.0.1:8005/events"

TEST_EVENT = {
    "event_id": "MULTI-1",
    "event_type": "shipment",
    "payload": {"shipment_id": "S1", "status": "DELIVERED"}
}

DB_DSN = os.getenv("DATABASE_URL", "postgresql://postgres:123@localhost:5432/event_dedup")


async def send_event(ws_url):
    async with websockets.connect(ws_url) as ws:
        await ws.send(json.dumps(TEST_EVENT))
        await asyncio.sleep(0.05)


async def count_rows():
    conn = await asyncpg.connect(dsn=DB_DSN)
    rows = await conn.fetch(
        "SELECT COUNT(*) FROM events WHERE event_id=$1",
        TEST_EVENT["event_id"]
    )
    await conn.close()
    return rows[0]["count"]


@pytest.mark.asyncio
async def test_multi_instance_deduplication():
    # Send same event to two different instances at same time
    await asyncio.gather(
        send_event(WS_URL_1),
        send_event(WS_URL_2),
        send_event(WS_URL_3),
        send_event(WS_URL_4),
        send_event(WS_URL_5)
    )

    await asyncio.sleep(1)

    count = await count_rows()
    assert count == 1, f"Expected 1 row, found {count}"
