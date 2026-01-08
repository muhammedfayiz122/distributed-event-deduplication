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
    "event_id": "FAIL-11",
    "event_type": "shipment",
    "payload": {"shipment_id": "S1", "status": "IN_TRANSIT"}
}

DB_DSN = os.getenv("DATABASE_URL", "postgresql://postgres:123@localhost:5432/event_dedup")


async def send_event():
    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps(TEST_EVENT))
        await asyncio.sleep(0.01)


async def count_rows(event_id: str):
    conn = await asyncpg.connect(dsn=DB_DSN)
    rows = await conn.fetch(
        "SELECT COUNT(*) FROM events WHERE event_id=$1",
        event_id
    )
    await conn.close()
    return rows[0]["count"]



@pytest.mark.asyncio
async def test_lock_release_on_failure():

    fail_event = {
        "event_id": "FAIL-11",
        "event_type": "fail_test",
        "payload": {"force_fail": True}
    }

    success_event = {
        "event_id": "FAIL-11",
        "event_type": "fail_test",
        "payload": {"force_fail": False}
    }

    # 1st attempt - force failure
    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps(fail_event))

    await asyncio.sleep(2)

    # 2nd attempt - should succeed
    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps(success_event))

    await asyncio.sleep(1)

    count = await count_rows("FAIL-11")
    assert count == 1

