from __future__ import annotations

import csv
import io
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator

import aiosqlite

from bot.config import DB_PATH


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class Appeal:
    id: int
    public_id: str
    user_id: int | None
    username: str | None
    appeal_type: str
    district: str
    topic: str
    text: str
    wants_reply: bool
    status: str
    admin_note: str | None
    created_at: str
    updated_at: str


def _row_to_appeal(row: aiosqlite.Row) -> Appeal:
    return Appeal(
        id=row["id"],
        public_id=row["public_id"],
        user_id=row["user_id"],
        username=row["username"],
        appeal_type=row["appeal_type"],
        district=row["district"],
        topic=row["topic"],
        text=row["text"],
        wants_reply=bool(row["wants_reply"]),
        status=row["status"],
        admin_note=row["admin_note"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class Database:
    def __init__(self, path: Path = DB_PATH) -> None:
        self.path = path

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[aiosqlite.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA foreign_keys = ON")
            yield conn

    async def init(self) -> None:
        async with self.connect() as db:
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS appeals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    public_id TEXT NOT NULL UNIQUE,
                    user_id INTEGER,
                    username TEXT,
                    appeal_type TEXT NOT NULL,
                    district TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    text TEXT NOT NULL,
                    wants_reply INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'new',
                    admin_note TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_appeals_created
                    ON appeals(created_at);
                CREATE INDEX IF NOT EXISTS idx_appeals_status
                    ON appeals(status);
                CREATE INDEX IF NOT EXISTS idx_appeals_user_day
                    ON appeals(user_id, created_at);

                CREATE TABLE IF NOT EXISTS bot_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            await db.commit()

    async def get_meta(self, key: str) -> str | None:
        async with self.connect() as db:
            cursor = await db.execute(
                "SELECT value FROM bot_meta WHERE key = ?",
                (key,),
            )
            row = await cursor.fetchone()
            return row["value"] if row else None

    async def set_meta(self, key: str, value: str) -> None:
        async with self.connect() as db:
            await db.execute(
                """
                INSERT INTO bot_meta(key, value) VALUES(?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )
            await db.commit()

    async def count_today(self, user_id: int) -> int:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        async with self.connect() as db:
            cursor = await db.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM appeals
                WHERE user_id = ?
                  AND substr(created_at, 1, 10) = ?
                """,
                (user_id, day),
            )
            row = await cursor.fetchone()
            return int(row["cnt"]) if row else 0

    async def create_appeal(
        self,
        *,
        user_id: int | None,
        username: str | None,
        appeal_type: str,
        district: str,
        topic: str,
        text: str,
        wants_reply: bool,
    ) -> Appeal:
        now = utc_now()
        async with self.connect() as db:
            cursor = await db.execute(
                """
                INSERT INTO appeals (
                    public_id, user_id, username, appeal_type, district,
                    topic, text, wants_reply, status, created_at, updated_at
                ) VALUES ('', ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?)
                """,
                (
                    # user_id завжди — для ліміту і «Мої звернення»;
                    # username лише якщо людина просила відповідь.
                    user_id,
                    username if wants_reply else None,
                    appeal_type,
                    district,
                    topic,
                    text.strip(),
                    1 if wants_reply else 0,
                    now,
                    now,
                ),
            )
            appeal_id = cursor.lastrowid
            public_id = f"КММР-{appeal_id:04d}"
            await db.execute(
                "UPDATE appeals SET public_id = ? WHERE id = ?",
                (public_id, appeal_id),
            )
            await db.commit()
            cursor = await db.execute(
                "SELECT * FROM appeals WHERE id = ?",
                (appeal_id,),
            )
            row = await cursor.fetchone()
            assert row is not None
            return _row_to_appeal(row)

    async def get_by_id(self, appeal_id: int) -> Appeal | None:
        async with self.connect() as db:
            cursor = await db.execute(
                "SELECT * FROM appeals WHERE id = ?",
                (appeal_id,),
            )
            row = await cursor.fetchone()
            return _row_to_appeal(row) if row else None

    async def get_by_public_id(self, public_id: str) -> Appeal | None:
        async with self.connect() as db:
            cursor = await db.execute(
                "SELECT * FROM appeals WHERE public_id = ?",
                (public_id,),
            )
            row = await cursor.fetchone()
            return _row_to_appeal(row) if row else None

    async def set_status(
        self,
        appeal_id: int,
        status: str,
        admin_note: str | None = None,
    ) -> Appeal | None:
        now = utc_now()
        async with self.connect() as db:
            if admin_note is None:
                await db.execute(
                    """
                    UPDATE appeals
                    SET status = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (status, now, appeal_id),
                )
            else:
                await db.execute(
                    """
                    UPDATE appeals
                    SET status = ?, admin_note = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (status, admin_note, now, appeal_id),
                )
            await db.commit()
            cursor = await db.execute(
                "SELECT * FROM appeals WHERE id = ?",
                (appeal_id,),
            )
            row = await cursor.fetchone()
            return _row_to_appeal(row) if row else None

    async def list_recent(self, limit: int = 20) -> list[Appeal]:
        async with self.connect() as db:
            cursor = await db.execute(
                """
                SELECT * FROM appeals
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cursor.fetchall()
            return [_row_to_appeal(row) for row in rows]

    async def list_by_status(self, status: str, limit: int = 20) -> list[Appeal]:
        async with self.connect() as db:
            cursor = await db.execute(
                """
                SELECT * FROM appeals
                WHERE status = ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (status, limit),
            )
            rows = await cursor.fetchall()
            return [_row_to_appeal(row) for row in rows]

    async def list_by_user(self, user_id: int, limit: int = 10) -> list[Appeal]:
        async with self.connect() as db:
            cursor = await db.execute(
                """
                SELECT * FROM appeals
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            )
            rows = await cursor.fetchall()
            return [_row_to_appeal(row) for row in rows]

    async def count_status(self, status: str) -> int:
        async with self.connect() as db:
            cursor = await db.execute(
                "SELECT COUNT(*) AS cnt FROM appeals WHERE status = ?",
                (status,),
            )
            row = await cursor.fetchone()
            return int(row["cnt"]) if row else 0

    async def list_overdue_new(self, days: int = 7) -> list[Appeal]:
        """Звернення зі статусом new, старші за N днів (за created_at UTC)."""
        async with self.connect() as db:
            cursor = await db.execute(
                """
                SELECT * FROM appeals
                WHERE status = 'new'
                  AND created_at <= datetime('now', ?)
                ORDER BY id ASC
                """,
                (f"-{int(days)} days",),
            )
            rows = await cursor.fetchall()
            return [_row_to_appeal(row) for row in rows]

    async def stats_month(
        self, year: int | None = None, month: int | None = None
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        year = year or now.year
        month = month or now.month
        prefix = f"{year:04d}-{month:02d}"

        async with self.connect() as db:
            cursor = await db.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM appeals
                WHERE substr(created_at, 1, 7) = ?
                """,
                (prefix,),
            )
            total = int((await cursor.fetchone())["cnt"])

            cursor = await db.execute(
                "SELECT COUNT(*) AS cnt FROM appeals WHERE status = 'new'"
            )
            open_new = int((await cursor.fetchone())["cnt"])

            cursor = await db.execute(
                """
                SELECT topic, COUNT(*) AS cnt
                FROM appeals
                WHERE substr(created_at, 1, 7) = ?
                GROUP BY topic
                ORDER BY cnt DESC
                """,
                (prefix,),
            )
            by_topic = [(row["topic"], int(row["cnt"])) for row in await cursor.fetchall()]

            cursor = await db.execute(
                """
                SELECT district, COUNT(*) AS cnt
                FROM appeals
                WHERE substr(created_at, 1, 7) = ?
                GROUP BY district
                ORDER BY cnt DESC
                """,
                (prefix,),
            )
            by_district = [
                (row["district"], int(row["cnt"])) for row in await cursor.fetchall()
            ]

            cursor = await db.execute(
                """
                SELECT status, COUNT(*) AS cnt
                FROM appeals
                WHERE substr(created_at, 1, 7) = ?
                GROUP BY status
                ORDER BY cnt DESC
                """,
                (prefix,),
            )
            by_status = [
                (row["status"], int(row["cnt"])) for row in await cursor.fetchall()
            ]

            cursor = await db.execute(
                """
                SELECT appeal_type, COUNT(*) AS cnt
                FROM appeals
                WHERE substr(created_at, 1, 7) = ?
                GROUP BY appeal_type
                ORDER BY cnt DESC
                """,
                (prefix,),
            )
            by_type = [
                (row["appeal_type"], int(row["cnt"])) for row in await cursor.fetchall()
            ]

        return {
            "period": prefix,
            "total": total,
            "open_new": open_new,
            "by_topic": by_topic,
            "by_district": by_district,
            "by_status": by_status,
            "by_type": by_type,
        }

    async def export_csv(
        self, year: int | None = None, month: int | None = None
    ) -> str:
        now = datetime.now(timezone.utc)
        year = year or now.year
        month = month or now.month
        prefix = f"{year:04d}-{month:02d}"

        async with self.connect() as db:
            cursor = await db.execute(
                """
                SELECT public_id, created_at, appeal_type, district, topic,
                       text, status, wants_reply, updated_at, admin_note
                FROM appeals
                WHERE substr(created_at, 1, 7) = ?
                ORDER BY id ASC
                """,
                (prefix,),
            )
            rows = await cursor.fetchall()

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "public_id",
                "created_at",
                "appeal_type",
                "district",
                "topic",
                "text",
                "status",
                "wants_reply",
                "updated_at",
                "admin_note",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row["public_id"],
                    row["created_at"],
                    row["appeal_type"],
                    row["district"],
                    row["topic"],
                    row["text"],
                    row["status"],
                    "yes" if row["wants_reply"] else "no",
                    row["updated_at"],
                    row["admin_note"] or "",
                ]
            )
        return buffer.getvalue()


db = Database()
