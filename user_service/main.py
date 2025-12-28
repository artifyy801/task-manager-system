from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
app = FastAPI()

client = AsyncIOMotorClient("mongodb://mongodb:27017")
db = client.task_db
users_collection = db.users

class User(BaseModel):
    username: str
    email: str

@app.post("/register")
async def register_user(user: User):
    existing_user = await users_collection.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user = await users_collection.insert_one(user.model_dump())

    return {
        "message": "User Registered Successfully",
        "user_id": str(new_user.inserted_id)
    }

@app.get("/")
async def root():
    return {"message": "User Service is running"}