from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from jose import jwt
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

app = FastAPI()

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY", "fallback_secret_key")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")

# --- DB CONNECTION ---
client = AsyncIOMotorClient(MONGO_URL)
db = client.task_db
users_collection = db.users

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserRegister(BaseModel):
    username: str
    email: str
    password: str
class UserLogin(BaseModel):
    email: str
    password: str

def get_hashed_pass(password):
    return pwd_context.hash(password)

def verify_pass(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

ACCESS_TOKEN_EXPIRE_MINUTES = 30 # Token dies after 30 mins

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@app.post("/register")
async def register_user(user: UserRegister):
    existing_user = await users_collection.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_dict = user.model_dump()
    user_dict['password'] = get_hashed_pass(user_dict['password'])

    await users_collection.insert_one(user_dict)
    return {"message": "User registered successfully"}

@app.post("/login")
async def login(user: UserLogin):
    found_user = await users_collection.find_one({"email": user.email})

    if not found_user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if not verify_pass(user.password, found_user['password']):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Generate Token
    token = create_access_token({"sub": user.email})
    return {"access_token": token, "token_type": "bearer"}

@app.get("/")
async def root():
    return {"message": "User Service is running"}