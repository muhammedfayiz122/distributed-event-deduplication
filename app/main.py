from fastapi import FastAPI, WebSocket
from app.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    debug=settings.debug,
    docs_url="/docs",
    redoc_url="/redoc",
)

@app.websocket("/events")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    while True:
        event = await websocket.receive_text()
        print(f"Received event: {event}")
        await websocket.send_text(f"Event received: {event}")