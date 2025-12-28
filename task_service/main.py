from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
import pika
import json

app = FastAPI()

client = AsyncIOMotorClient("mongodb://mongodb:27017")
db = client.task_db
tasks_collection = db.tasks

def get_rabbitmq_channel():
    connection = pika.BlockingConnection(pika.ConnectionParameters('rabbitmq'))
    channel = connection.channel()
    channel.queue_declare(queue='task_events')
    return channel, connection

class Task(BaseModel):
    title: str
    user_email: str

@app.post("/tasks")
async def create_task(task: Task):
    # 1. Save to DB
    new_task = await tasks_collection.insert_one(task.model_dump())

    # 2. Publish to RabbitMQ (Uncommented and active!)
    try:
        channel, connection = get_rabbitmq_channel()
        message = {
            "event": "TASK_CREATED",
            "task_id": str(new_task.inserted_id),
            "user_email": task.user_email
        }
        channel.basic_publish(
            exchange='',
            routing_key='task_events',
            body=json.dumps(message)
        )
        connection.close()
    except Exception as e:
        print(f"Error sending message: {e}")

    return {"message": "Task created and notification queued!"}