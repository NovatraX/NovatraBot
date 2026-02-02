import sqlite3
from typing import Dict, List, Optional

from utilities.tasks.utils import clean_task_text, dedupe_key, normalize_priority


class TaskDatabase:
    def __init__(self, db_path: str = "data/tasks.db"):
        self.db_path = db_path
        self.init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_columns(
        self, conn: sqlite3.Connection, table: str, columns: Dict[str, str]
    ):
        existing = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for name, ddl in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")

    def init_db(self):
        with self._get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    original_message_id INTEGER,
                    task_text TEXT NOT NULL,
                    category TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    task_message_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    batch_id INTEGER,
                    source_message_id INTEGER,
                    source_message_link TEXT,
                    source_message_ts INTEGER,
                    dedupe_key TEXT,
                    linear_issue_id TEXT,
                    linear_issue_url TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_batches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    source_channel_id INTEGER NOT NULL,
                    target_channel_id INTEGER NOT NULL,
                    message_start_id INTEGER,
                    message_end_id INTEGER,
                    message_count INTEGER,
                    status TEXT DEFAULT 'open',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS channel_progress (
                    channel_id INTEGER PRIMARY KEY,
                    last_message_id INTEGER NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            self._ensure_columns(
                conn,
                "tasks",
                {
                    "batch_id": "INTEGER",
                    "source_message_id": "INTEGER",
                    "source_message_link": "TEXT",
                    "source_message_ts": "INTEGER",
                    "dedupe_key": "TEXT",
                    "linear_issue_id": "TEXT",
                    "linear_issue_url": "TEXT",
                    "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                },
            )

            self._ensure_columns(
                conn,
                "task_batches",
                {
                    "status": "TEXT DEFAULT 'open'",
                    "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                },
            )

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_batch ON tasks(batch_id)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_user_channel ON tasks(user_id, channel_id)"
            )

            conn.commit()

    def create_batch(
        self,
        user_id: int,
        source_channel_id: int,
        target_channel_id: int,
        message_start_id: Optional[int],
        message_end_id: Optional[int],
        message_count: int,
    ) -> int:
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO task_batches (
                    user_id,
                    source_channel_id,
                    target_channel_id,
                    message_start_id,
                    message_end_id,
                    message_count,
                    status
                ) VALUES (?, ?, ?, ?, ?, ?, 'open')
                """,
                (
                    user_id,
                    source_channel_id,
                    target_channel_id,
                    message_start_id,
                    message_end_id,
                    message_count,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def update_batch_status(self, batch_id: int, status: str):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE task_batches SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, batch_id),
            )
            conn.commit()

    def _task_exists(self, conn: sqlite3.Connection, key: str) -> bool:
        if not key:
            return False
        row = conn.execute(
            "SELECT 1 FROM tasks WHERE dedupe_key = ? LIMIT 1", (key,)
        ).fetchone()
        return row is not None

    def save_tasks(
        self,
        tasks: List[Dict],
        batch_id: int,
        channel_id: int,
        user_id: int,
    ) -> List[Dict]:
        saved_tasks = []
        with self._get_conn() as conn:
            for task in tasks:
                task_text = clean_task_text(task.get("text", ""))
                if not task_text:
                    continue

                priority = normalize_priority(task.get("priority"))
                source_message_id = task.get("source_message_id")
                source_message_link = task.get("source_message_link")
                source_message_ts = task.get("source_message_ts")
                key = task.get("dedupe_key") or dedupe_key(
                    user_id, source_message_id, task_text
                )

                if self._task_exists(conn, key):
                    continue

                cursor = conn.execute(
                    """
                    INSERT INTO tasks (
                        user_id,
                        channel_id,
                        original_message_id,
                        task_text,
                        category,
                        status,
                        batch_id,
                        source_message_id,
                        source_message_link,
                        source_message_ts,
                        dedupe_key
                    ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        channel_id,
                        source_message_id or 0,
                        task_text,
                        priority,
                        batch_id,
                        source_message_id,
                        source_message_link,
                        source_message_ts,
                        key,
                    ),
                )
                task_id = cursor.lastrowid
                saved_tasks.append(
                    {
                        "id": task_id,
                        "text": task_text,
                        "priority": priority,
                        "status": "pending",
                        "source_message_id": source_message_id,
                        "source_message_link": source_message_link,
                        "source_message_ts": source_message_ts,
                    }
                )
            conn.commit()
        return saved_tasks

    def get_tasks_for_batch(self, batch_id: int) -> List[Dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT id, task_text, category, status, source_message_id,
                       source_message_link, source_message_ts, linear_issue_id, linear_issue_url
                FROM tasks
                WHERE batch_id = ?
                ORDER BY source_message_ts ASC, id ASC
                """,
                (batch_id,),
            ).fetchall()

        tasks = []
        for row in rows:
            tasks.append(
                {
                    "id": row["id"],
                    "text": row["task_text"],
                    "priority": row["category"],
                    "status": row["status"],
                    "source_message_id": row["source_message_id"],
                    "source_message_link": row["source_message_link"],
                    "source_message_ts": row["source_message_ts"],
                    "linear_issue_id": row["linear_issue_id"],
                    "linear_issue_url": row["linear_issue_url"],
                }
            )
        return tasks

    def update_task_text(self, task_id: int, task_text: str):
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET task_text = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (clean_task_text(task_text), task_id),
            )
            conn.commit()

    def update_task_priority(self, task_id: int, priority: str):
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET category = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (normalize_priority(priority), task_id),
            )
            conn.commit()

    def set_task_status(self, task_id: int, status: str):
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, task_id),
            )
            conn.commit()

    def set_task_status_bulk(self, task_ids: List[int], status: str):
        if not task_ids:
            return
        with self._get_conn() as conn:
            placeholders = ",".join("?" for _ in task_ids)
            conn.execute(
                f"UPDATE tasks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
                [status] + task_ids,
            )
            conn.commit()

    def mark_task_uploaded(self, task_id: int, issue_id: str, issue_url: str):
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = 'uploaded', linear_issue_id = ?, linear_issue_url = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (issue_id, issue_url, task_id),
            )
            conn.commit()

    def mark_task_failed(self, task_id: int):
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = 'failed', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (task_id,),
            )
            conn.commit()

    def get_last_message_id(self, channel_id: int) -> int:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT last_message_id FROM channel_progress WHERE channel_id = ?",
                (channel_id,),
            ).fetchone()
            return int(row["last_message_id"]) if row else 0

    def set_last_message_id(self, channel_id: int, message_id: int):
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO channel_progress (channel_id, last_message_id, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                (channel_id, message_id),
            )
            conn.commit()

    def mark_channel_tasks_completed(self, channel_id: int):
        """Mark all active tasks in a channel as completed."""
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = 'completed', updated_at = CURRENT_TIMESTAMP
                WHERE channel_id = ? AND status NOT IN ('rejected', 'completed')
                """,
                (channel_id,),
            )
            conn.commit()
