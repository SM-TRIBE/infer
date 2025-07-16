# db.py
# This file handles all interactions with the PostgreSQL database.
# It uses the 'asyncpg' library for asynchronous database operations.

import asyncpg
import os
import uuid
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_USER_IDS = [int(uid) for uid in os.getenv("ADMIN_USER_IDS", "").split(",") if uid]


async def get_conn():
    """Establishes a connection to the database."""
    return await asyncpg.connect(DATABASE_URL)


async def init_db():
    """Initializes the database, creating tables if they don't exist."""
    conn = await get_conn()
    try:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                name TEXT NOT NULL,
                coins INTEGER DEFAULT 100,
                is_premium BOOLEAN DEFAULT FALSE,
                is_banned BOOLEAN DEFAULT FALSE,
                referral_code TEXT UNIQUE,
                referred_by TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS profiles (
                user_id BIGINT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
                gender TEXT,
                age INTEGER,
                bio TEXT,
                photo_id TEXT,
                location TEXT
            );

            CREATE TABLE IF NOT EXISTS likes (
                liker_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                liked_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                PRIMARY KEY (liker_id, liked_id)
            );

            -- You could add a transactions table for a more robust currency system
            """
        )
        print("Database initialized successfully.")
    finally:
        await conn.close()


async def user_exists(user_id: int) -> bool:
    """Checks if a user exists in the database."""
    conn = await get_conn()
    try:
        return await conn.fetchval("SELECT EXISTS(SELECT 1 FROM users WHERE user_id = $1)", user_id)
    finally:
        await conn.close()

async def is_banned(user_id: int) -> bool:
    """Checks if a user is banned."""
    conn = await get_conn()
    try:
        banned = await conn.fetchval("SELECT is_banned FROM users WHERE user_id = $1", user_id)
        return banned if banned is not None else False
    finally:
        await conn.close()


async def create_user(user_id: int, name: str, referral_code: str = None):
    """Creates a new user and their profile."""
    if await user_exists(user_id):
        return

    conn = await get_conn()
    try:
        async with conn.transaction():
            user_referral_code = str(uuid.uuid4())[:8]
            await conn.execute(
                """
                INSERT INTO users (user_id, name, referral_code, referred_by)
                VALUES ($1, $2, $3, $4)
                """,
                user_id,
                name,
                user_referral_code,
                referral_code,
            )
            await conn.execute("INSERT INTO profiles (user_id) VALUES ($1)", user_id)

            # If referred, give coins to the referrer
            if referral_code:
                referrer_id = await conn.fetchval(
                    "SELECT user_id FROM users WHERE referral_code = $1", referral_code
                )
                if referrer_id:
                    await add_coins(referrer_id, 50) # Reward for referral
    finally:
        await conn.close()


async def update_profile(user_id: int, field: str, value):
    """Updates a specific field in a user's profile."""
    conn = await get_conn()
    try:
        # Using f-string here is safe because `field` is controlled by our code, not user input.
        await conn.execute(
            f"UPDATE profiles SET {field} = $1 WHERE user_id = $2", value, user_id
        )
    finally:
        await conn.close()


async def get_user_profile(user_id: int):
    """Retrieves a user's full profile data."""
    conn = await get_conn()
    try:
        row = await conn.fetchrow(
            """
            SELECT u.name, u.coins, u.is_premium, p.gender, p.age, p.bio, p.photo_id, p.location
            FROM users u
            JOIN profiles p ON u.user_id = p.user_id
            WHERE u.user_id = $1
            """,
            user_id,
        )
        return dict(row) if row else None
    finally:
        await conn.close()


async def search_users(searcher_id: int, gender: str, min_age: int, max_age: int):
    """Searches for users based on criteria."""
    conn = await get_conn()
    try:
        # Exclude the user themselves from the search results
        rows = await conn.fetch(
            """
            SELECT p.user_id
            FROM profiles p
            JOIN users u ON p.user_id = u.user_id
            WHERE p.gender = $1
              AND p.age BETWEEN $2 AND $3
              AND p.user_id != $4
              AND u.is_banned = FALSE
            ORDER BY RANDOM() -- For variety, in a real app might use a better algorithm
            LIMIT 20;
            """,
            gender,
            min_age,
            max_age,
            searcher_id
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()


async def get_referral_code(user_id: int) -> str:
    """Gets a user's referral code."""
    conn = await get_conn()
    try:
        return await conn.fetchval("SELECT referral_code FROM users WHERE user_id = $1", user_id)
    finally:
        await conn.close()

async def get_referral_count(user_id: int) -> int:
    """Counts how many users were referred by this user."""
    conn = await get_conn()
    try:
        user_code = await get_referral_code(user_id)
        if not user_code:
            return 0
        return await conn.fetchval("SELECT COUNT(*) FROM users WHERE referred_by = $1", user_code)
    finally:
        await conn.close()


async def add_coins(user_id: int, amount: int):
    """Adds a certain amount of coins to a user's balance."""
    conn = await get_conn()
    try:
        await conn.execute(
            "UPDATE users SET coins = coins + $1 WHERE user_id = $2", amount, user_id
        )
    finally:
        await conn.close()


async def set_premium_status(user_id: int, status: bool):
    """Sets a user's premium status."""
    conn = await get_conn()
    try:
        await conn.execute(
            "UPDATE users SET is_premium = $1 WHERE user_id = $2", status, user_id
        )
    finally:
        await conn.close()


async def set_ban_status(user_id: int, status: bool):
    """Sets a user's banned status."""
    conn = await get_conn()
    try:
        await conn.execute(
            "UPDATE users SET is_banned = $1 WHERE user_id = $2", status, user_id
        )
    finally:
        await conn.close()


async def is_admin(user_id: int) -> bool:
    """Checks if a user is an admin."""
    return user_id in ADMIN_USER_IDS


async def get_all_users():
    """Retrieves a list of all users for the admin panel."""
    conn = await get_conn()
    try:
        rows = await conn.fetch("SELECT user_id, name, is_banned FROM users ORDER BY created_at DESC")
        return [dict(row) for row in rows]
    finally:
        await conn.close()
