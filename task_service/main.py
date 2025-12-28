from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from datetime import datetime
import asyncio
import json
import aio_pika
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

app = FastAPI()

# 1. Enable CORS (So Frontend can connect)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database Connection
client = AsyncIOMotorClient("mongodb://mongodb:27017")
db = client.task_db
tasks_collection = db.tasks

# --- WEBSOCKET MANAGER ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_email: str):
        await websocket.accept()
        self.active_connections[user_email] = websocket

    def disconnect(self, user_email: str):
        if user_email in self.active_connections:
            del self.active_connections[user_email]

    async def send_personal_message(self, message: str, user_email: str):
        if user_email in self.active_connections:
            websocket = self.active_connections[user_email]
            await websocket.send_text(message)

manager = ConnectionManager()

# --- BACKGROUND LISTENER (The Feedback Loop) ---
async def consume_updates():
    # Wait for RabbitMQ to start
    await asyncio.sleep(5) 
    try:
        connection = await aio_pika.connect_robust("amqp://guest:guest@rabbitmq/")
        queue_name = "task_updates"

        async with connection:
            channel = await connection.channel()
            queue = await channel.declare_queue(queue_name)

            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        data = json.loads(message.body.decode())
                        user_email = data.get("user_email")
                        print(f"Update received for {user_email}")
                        
                        # PUSH TO FRONTEND
                        await manager.send_personal_message(
                            json.dumps(data), user_email
                        )
    except Exception as e:
        print(f"RabbitMQ Connection Failed: {e}")

@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_event_loop()
    loop.create_task(consume_updates())

# --- API ENDPOINTS ---

class Task(BaseModel):
    title: str
    user_email: str
    createdAt: datetime = Field(default_factory=datetime.now)

@app.post("/tasks")
async def create_task(task: Task):
    # 1. Save to DB
    new_task = await tasks_collection.insert_one(task.model_dump())
    
    # 2. Send to RabbitMQ (Async)
    connection = await aio_pika.connect_robust("amqp://guest:guest@rabbitmq/")
    async with connection:
        channel = await connection.channel()
        # Declare queue to be safe
        await channel.declare_queue("task_events", durable=True)
        
        message = {
            "title": task.title,
            "user_email": task.user_email,
            "task_id": str(new_task.inserted_id)
        }
        
        await channel.default_exchange.publish(
            aio_pika.Message(body=json.dumps(message).encode()),
            routing_key="task_events"
        )
        
    return {"message": "Task sent to background worker"}

# THE MISSING PIECE: The WebSocket Endpoint
@app.websocket("/ws/{user_email}")
async def websocket_endpoint(websocket: WebSocket, user_email: str):
    await manager.connect(websocket, user_email)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_email)