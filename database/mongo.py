import logging
import os
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from agent_common.database.mongo import BaseMongoDatabase

logger = logging.getLogger("agent_health.mongo")

_DB_NAME = os.getenv("MONGO_DB_NAME", "agent_health")


class MongoDB(BaseMongoDatabase):
    _gridfs: AsyncIOMotorGridFSBucket | None = None

    @classmethod
    def db_name(cls) -> str:
        return _DB_NAME

    @classmethod
    def _db(cls):
        return cls.get_client()[cls.db_name()]

    @classmethod
    def _gridfs_bucket(cls) -> AsyncIOMotorGridFSBucket:
        if cls._gridfs is None:
            cls._gridfs = AsyncIOMotorGridFSBucket(cls._db())
        return cls._gridfs

    @classmethod
    def _profiles(cls):
        return cls._db()["health_profiles"]

    @classmethod
    def _files(cls):
        return cls._db()["files"]

    # ── Health profile persistence ──

    @classmethod
    async def save_profile(cls, user_id: str, profile: dict) -> None:
        """Upsert a user's health profile. One profile per user_id."""
        doc = {
            "user_id": user_id,
            "goals": profile.get("goals", ""),
            "fitness_level": profile.get("fitness_level", "beginner"),
            "available_equipment": profile.get("available_equipment", []),
            "dietary_restrictions": profile.get("dietary_restrictions", []),
            "injuries_or_limitations": profile.get("injuries_or_limitations", ""),
            "age": profile.get("age"),
            "weight_kg": profile.get("weight_kg"),
            "height_cm": profile.get("height_cm"),
            "sessions_per_week": profile.get("sessions_per_week"),
            "minutes_per_session": profile.get("minutes_per_session"),
            "updated_at": datetime.now(timezone.utc),
        }
        await cls._profiles().update_one(
            {"user_id": user_id},
            {"$set": doc},
            upsert=True,
        )
        logger.info("Saved health profile for user='%s'", user_id)

    @classmethod
    async def get_profile(cls, user_id: str) -> dict | None:
        """Retrieve a user's health profile by user_id."""
        return await cls._profiles().find_one(
            {"user_id": user_id},
            {"_id": 0},
        )

    # ── File storage (GridFS for plan exports) ──

    @classmethod
    async def store_file(
        cls,
        file_id: str,
        filename: str,
        data: bytes,
        file_type: str,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> None:
        """Store file content in MongoDB GridFS and save metadata."""
        bucket = cls._gridfs_bucket()
        await bucket.upload_from_stream(
            file_id,
            data,
            metadata={
                "file_id": file_id,
                "original_filename": filename,
                "file_type": file_type,
                "session_id": session_id,
                "user_id": user_id,
            },
        )
        doc = {
            "file_id": file_id,
            "filename": filename,
            "file_type": file_type,
            "session_id": session_id,
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc),
        }
        await cls._files().insert_one(doc)
        logger.info("Stored file in GridFS — file_id='%s', type='%s', size=%d bytes",
                     file_id, file_type, len(data))

    @classmethod
    async def retrieve_file(cls, file_id: str) -> tuple[bytes, dict] | None:
        """Retrieve file content from GridFS. Returns (data, metadata) or None."""
        bucket = cls._gridfs_bucket()
        try:
            stream = await bucket.open_download_stream_by_name(file_id)
            data = await stream.read()
            meta = await cls._files().find_one({"file_id": file_id}, {"_id": 0})
            return data, meta or {}
        except Exception:
            logger.warning("File not found in GridFS: file_id='%s'", file_id)
            return None

    @classmethod
    async def get_latest_plan(cls, session_id: str) -> dict | None:
        """Retrieve the most recently generated fitness plan file for a session."""
        return await cls._files().find_one(
            {"session_id": session_id, "file_type": "fitness_plan"},
            {"_id": 0},
            sort=[("created_at", -1)],
        )

    # ── Progress tracking ──

    @classmethod
    def _progress(cls):
        return cls._db()["progress_logs"]

    @classmethod
    def _nutrition(cls):
        return cls._db()["nutrition_logs"]

    @classmethod
    async def log_progress(
        cls,
        user_id: str,
        metric_type: str,
        value: float,
        unit: str,
        notes: str = "",
        date: str = "",
    ) -> None:
        from datetime import timezone
        doc = {
            "user_id": user_id,
            "metric_type": metric_type,
            "value": value,
            "unit": unit,
            "notes": notes,
            "date": date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "created_at": datetime.now(timezone.utc),
        }
        await cls._progress().insert_one(doc)

    @classmethod
    async def get_progress(cls, user_id: str, metric_type: str, days: int = 30) -> list[dict]:
        from datetime import timedelta, timezone
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        cursor = cls._progress().find(
            {"user_id": user_id, "metric_type": metric_type, "date": {"$gte": cutoff}},
            {"_id": 0, "value": 1, "unit": 1, "date": 1, "notes": 1},
        ).sort("date", 1)
        return await cursor.to_list(length=500)

    @classmethod
    async def get_all_progress(cls, user_id: str, days: int = 30) -> list[dict]:
        from datetime import timedelta, timezone
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        cursor = cls._progress().find(
            {"user_id": user_id, "date": {"$gte": cutoff}},
            {"_id": 0},
        ).sort("date", 1)
        return await cursor.to_list(length=1000)

    @classmethod
    async def log_nutrition(
        cls,
        user_id: str,
        meal_description: str,
        calories_kcal: float,
        protein_g: float = 0.0,
        carbs_g: float = 0.0,
        fat_g: float = 0.0,
        meal_type: str = "meal",
        date: str = "",
    ) -> None:
        from datetime import timezone
        doc = {
            "user_id": user_id,
            "meal_description": meal_description[:200],
            "calories_kcal": calories_kcal,
            "protein_g": protein_g,
            "carbs_g": carbs_g,
            "fat_g": fat_g,
            "meal_type": meal_type,
            "date": date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "created_at": datetime.now(timezone.utc),
        }
        await cls._nutrition().insert_one(doc)

    @classmethod
    async def get_daily_nutrition_total(cls, user_id: str, date: str) -> dict:
        pipeline = [
            {"$match": {"user_id": user_id, "date": date}},
            {"$group": {
                "_id": None,
                "calories_kcal": {"$sum": "$calories_kcal"},
                "protein_g": {"$sum": "$protein_g"},
                "carbs_g": {"$sum": "$carbs_g"},
                "fat_g": {"$sum": "$fat_g"},
            }},
        ]
        result = await cls._nutrition().aggregate(pipeline).to_list(length=1)
        if result:
            return {k: round(v, 1) for k, v in result[0].items() if k != "_id"}
        return {"calories_kcal": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}

    @classmethod
    async def get_nutrition_logs(cls, user_id: str, days: int = 7) -> list[dict]:
        from datetime import timedelta, timezone
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
        cursor = cls._nutrition().find(
            {"user_id": user_id, "date": {"$gte": cutoff}},
            {"_id": 0},
        ).sort("date", -1)
        return await cursor.to_list(length=500)

    @classmethod
    async def ensure_indexes(cls) -> None:
        await super().ensure_indexes()
        db = cls._db()
        await db["health_profiles"].create_index("user_id", unique=True)
        await db["health_profiles"].create_index("updated_at", expireAfterSeconds=31_536_000)
        await db["files"].create_index("created_at", expireAfterSeconds=2_592_000)
        await db["fs.files"].create_index("uploadDate", expireAfterSeconds=2_592_000)
        await db["progress_logs"].create_index([("user_id", 1), ("metric_type", 1), ("date", 1)])
        await db["progress_logs"].create_index("created_at", expireAfterSeconds=31_536_000)
        await db["nutrition_logs"].create_index([("user_id", 1), ("date", 1)])
        await db["nutrition_logs"].create_index("created_at", expireAfterSeconds=31_536_000)
