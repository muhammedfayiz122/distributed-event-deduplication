# Distributed Event Deduplication for WebSocket Listeners

>
> This repository contains implementation of a **distributed event deduplication mechanism** for WebSocket listeners. The system guarantees that even if multiple listener instances receive the same event concurrently, **each event is processed and persisted exactly once (logically once)**.

---

## 1. Problem Context

In a distributed environment, multiple FastAPI instances are connected to the same WebSocket source. Due to fan-out delivery, network retries, or upstream behavior, **the same event can be delivered to multiple instances at the same time**.

The challenge is to design a system where:

* More than one listener may receive the same event
* **Only one instance must process and persist it**
* The system must tolerate **crashes, retries, and partial failures**
* The solution must scale to **high throughput and many listeners**

This implementation directly addresses all of these requirements.

---

## 2. Architecture

<img src="deduplication_arch.png" alt="Deduplication Architecture" width="800">

### Components

| Component             | Role                                        |
| --------------------- | ------------------------------------------- |
| **WebSocket Source**  | Sends events (may send duplicates)          |
| **FastAPI Instances** | Receive events and attempt processing       |
| **Redis**             | Global coordination store for deduplication |
| **PostgreSQL**        | Final persistence with uniqueness guarantee |

> **Important:** Redis is used only for **coordination and ownership claiming**. It is *not* used as a message broker or event store.

---

## 3. Core Design Principles

### 3.1 Atomic Ownership Claim

We use Redis `SET NX` to atomically claim an event:

```
SET dedup:{event_id} <instance_id> NX EX <ttl>
```

* `NX` → ensures the key is set only if it does not already exist (atomic)
* `EX` → TTL for crash recovery

This guarantees that **only one instance can own a given event at any time**.

---

### 3.2 Instance Identity

Each FastAPI process generates a unique `instance_id` at startup. This is stored as the value of the Redis key.

This enables:

* Safe ownership tracking
* Preventing other instances from deleting a lock they do not own

---

### 3.3 Crash Recovery with TTL

If a process crashes after claiming an event (process craches , not error during processing):

* It cannot release the lock
* Redis TTL ensures the key is automatically removed
* The event becomes eligible for retry

TTL is configured **higher than the maximum expected processing time** to avoid premature expiry during normal execution.

---

### 3.4 Idempotency of Side Effects

ll side effects (DB writes, external API calls, payments, emails, etc.) are designed to be idempotent using a deterministic idempotency key derived from the event (typically event_id if it is globally unique and immutable; otherwise a dedicated idempotency_key field or a hash of stable event attributes).

This ensures that even if processing is retried due to failure, **real-world side effects do not happen twice**.

---

## 4. Consistency Guarantees

| Layer            | Guarantee                                     |
| ---------------- | --------------------------------------------- |
| **Delivery**     | At-least-once (WebSocket may send duplicates) |
| **Processing**   | Exactly-once (logical) via Redis dedup        |
| **Persistence**  | Exactly-once via DB unique constraint         |
| **Side Effects** | Exactly-once via idempotency                  |

---

## 5. Algorithm & Flow

### High-Level Flow

1. Receive event from WebSocket
2. Extract `event_id`
3. Attempt atomic claim in Redis
4. If claim fails → **drop event**
5. If claim succeeds → process event
6. Persist event to DB
7. On failure → release lock (only if owner)

---

### Pseudocode

```
onEvent(event):
    eventId = event.event_id
    dedup_key = "dedup:" + eventId

    claimed = redis.SET(dedup_key, instanceId, NX, EX=TTL)

    if not claimed: # means another instance claimed it
        return  # duplicate, ignore

    try:
        process(event)        # idempotent operations
        persist(event)        # DB insert (unique constraint)
    except:
        if redis.GET(dedup_key) == instanceId:      # only owner can release
            redis.DEL(dedup_key)        # now another instance can retry               
        raise
```

---

## 6. Failure Modes & Recovery

### 6.1 Instance Crashes After Claim

* Redis key remains
* TTL expires
* Event becomes available for retry

### 6.2 Instance Crashes During Processing

* Partial execution assumed
* Immediate reprocessing is avoided
* TTL ensures delayed, safe recovery
* Idempotency prevents duplicate side effects

### 6.3 Competing Instances

* Redis `SET NX` guarantees only one winner

### 6.4 Redis Restart

* Keys lost
* Events may reprocess
* DB unique constraint prevents duplicate persistence

---

## 7. Database Design

Single minimal table:

```
events (
    id BIGSERIAL PRIMARY KEY,
    event_id VARCHAR UNIQUE NOT NULL,
    event_type VARCHAR NOT NULL,
    payload JSONB NOT NULL,
    processed_at TIMESTAMP DEFAULT NOW()
)
```

Why minimal?

* Redis handles in-progress state
* DB stores only final successful events
* No status columns, no retry tables, no over-engineering

---

## 8. Scaling Strategy

### Horizontal Scaling

* FastAPI instances are stateless
* Add more instances freely

### Redis Scaling

* O(1) operations
* Can be clustered or sharded

### Database Scaling

* Index on `event_id`
* Connection pooling
* Read replicas if needed

---

## 9. Testing Strategy (Implemented)

This project includes **real concurrency and distributed tests**.

### 9.1 Concurrent Delivery Test

* Multiple WebSocket clients send same event concurrently
* Verified only one DB row is created

### 9.2 Crash Simulation Test

* Force failure after Redis claim
* Verify lock release
* Retry succeeds
* DB contains only one row

### 9.3 Multi-Instance Test

* 5 FastAPI instances on different ports
* Same Redis and DB
* Same event sent to all
* Verified exactly one DB row

These tests prove correctness under real distributed conditions.

---

## 10. Why This Design Works

* **Redis SET NX** ensures atomic claim
* **Instance ID** prevents unsafe lock deletion
* **TTL** ensures crash recovery
* **DB unique constraint** is final safety net
* **Idempotency** prevents real-world damage

This combination provides **strong correctness guarantees without over-engineering**.

---

## 11. How to Run

1. Start Redis
2. Start PostgreSQL
3. Run one or more FastAPI instances

```
uvicorn app.main:app --port 8000
uvicorn app.main:app --port 8001
...
```

4. Connect WebSocket producer to `/events`
5. Send JSON events with unique `event_id`

---

## 12. Author

Muhammed Fayiz
