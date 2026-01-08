import asyncio
import json
import pytest
import websockets
import asyncpg
from dotenv import load_dotenv
import os
# setup_logging()

WS_URL = "ws://127.0.0.1:8000/events"
TEST_EVENT = {
    "event_id": "TEST-127",
    "event_type": "shipment",
    "payload": {"shipment_id": "S1", "status": "IN_TRANSIT"}
}

DB_DSN = os.getenv("DATABASE_URL", "postgresql://postgres:123@localhost:5432/event_dedup")


async def send_event():
    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps(TEST_EVENT))
        await asyncio.sleep(0.01)


async def count_rows():
    conn = await asyncpg.connect(dsn=DB_DSN)
    rows = await conn.fetch("SELECT COUNT(*) FROM events WHERE event_id=$1", TEST_EVENT["event_id"])
    await conn.close()
    return rows[0]["count"]


@pytest.mark.asyncio
async def test_concurrent_deduplication():
    # Send same event concurrently from 10 clients
    tasks = [send_event() for _ in range(1000)]
    await asyncio.gather(*tasks)

    await asyncio.sleep(1)  # wait for processing

    count = await count_rows()
    assert count == 1, f"Expected 1 row, found {count}"
    
