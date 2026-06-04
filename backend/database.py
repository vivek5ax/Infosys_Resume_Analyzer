import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME", "resume_analyzer")
MONGODB_CONNECT_TIMEOUT_MS = int(os.getenv("MONGODB_CONNECT_TIMEOUT_MS", "10000"))

client = None
db = None


async def connect_to_mongo():
    """Connect to MongoDB (Bypassed by design)"""
    global client, db
    print("✓ MongoDB connection bypassed (database disconnected by design)")
    client = None
    db = None


async def close_mongo_connection():
    """Close MongoDB connection (Bypassed by design)"""
    global client, db
    client = None
    db = None
    print("✓ MongoDB disconnection complete (no-op)")


def get_database():
    """Get database instance (Always None)"""
    return None
