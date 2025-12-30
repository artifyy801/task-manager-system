from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import asyncio
import json
import aio_pika
from motor.motor_asyncio import AsyncIOMotorClient
from jose import jwt, JWTError
import os
from dotenv import load_dotenv

app = FastAPI()

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY", "fallback_secret_key")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

# 2. Enable CORS (So Frontend can connect)
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
            # Ensure queue exists before listening
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

# --- API ENDPOINTS & SECURITY ---

class TaskCreate(BaseModel):
    title: str

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# DEPENDENCY: Verify Token & Extract Email
async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_email: str = payload.get("sub")
        if user_email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_email
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

@app.post("/tasks")
async def create_task(
    task: TaskCreate, 
    user_email: str = Depends(get_current_user) # <--- SECURITY INJECTED HERE
):
    # 1. Prepare Data (Combine input with Secure Email)
    task_dict = task.model_dump()
    task_dict["user_email"] = user_email
    task_dict["createdAt"] = datetime.now()

    # 2. Save to DB
    new_task = await tasks_collection.insert_one(task_dict)
    
    # 3. Send to RabbitMQ (Async)
    connection = await aio_pika.connect_robust("amqp://guest:guest@rabbitmq/")
    async with connection:
        channel = await connection.channel()
        # Declare queue to be safe
        await channel.declare_queue("task_events", durable=True)
        
        message = {
            "title": task.title,
            "user_email": user_email,
            "task_id": str(new_task.inserted_id)
        }
        
        await channel.default_exchange.publish(
            aio_pika.Message(body=json.dumps(message).encode()),
            routing_key="task_events"
        )
        
    return {"message": "Task sent to background worker"}

# The WebSocket Endpoint
@app.websocket("/ws/{user_email}")
async def websocket_endpoint(websocket: WebSocket, user_email: str):
    await manager.connect(websocket, user_email)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(user_email)