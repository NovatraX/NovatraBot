import sqlite3
from typing import Dict, List, Optional


class LinkDatabase:
    def __init__(self, db_path: str = "data/links.db"):
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
                CREATE TABLE IF NOT EXISTS saved_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    normalized_url TEXT,
                    domain TEXT,
                    title TEXT,
                    description TEXT,
                    site_name TEXT,
                    image_url TEXT,
                    message_id INTEGER NOT NULL,
                    message_link TEXT NOT NULL,
                    channel_id INTEGER NOT NULL,
                    category_id INTEGER NOT NULL,
                    author_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            self._ensure_columns(
                conn,
                "saved_links",
                {
                    "normalized_url": "TEXT",
                    "domain": "TEXT",
                    "title": "TEXT",
                    "description": "TEXT",
                    "site_name": "TEXT",
                    "image_url": "TEXT",
                    "category": "TEXT",
                    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                },
            )

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_links_category_type ON saved_links(category)"
            )

            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_links_message_url ON saved_links(message_id, url)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_links_created ON saved_links(created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_links_category ON saved_links(category_id)"
            )
            conn.commit()

    def save_links(self, links: List[Dict]) -> List[Dict]:
        saved = []
        with self._get_conn() as conn:
            for link in links:
                try:
                    cursor = conn.execute(
                        """
                        INSERT OR IGNORE INTO saved_links (
                            url,
                            normalized_url,
                            domain,
                            message_id,
                            message_link,
                            channel_id,
                            category_id,
                            author_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            link["url"],
                            link.get("normalized_url"),
                            link.get("domain"),
                            link["message_id"],
                            link["message_link"],
                            link["channel_id"],
                            link["category_id"],
                            link["author_id"],
                        ),
                    )
                    if cursor.rowcount:
                        saved.append({"id": cursor.lastrowid, "url": link["url"]})
                except sqlite3.IntegrityError:
                    continue
            conn.commit()
        return saved

    def update_metadata(
        self,
        link_id: int,
        title: Optional[str],
        description: Optional[str],
        site_name: Optional[str],
        image_url: Optional[str],
        category: Optional[str] = None,
    ):
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE saved_links
                SET title = ?, description = ?, site_name = ?, image_url = ?, category = ?
                WHERE id = ?
                """,
                (title, description, site_name, image_url, category, link_id),
            )
            conn.commit()

    def count_links(
        self,
        query: Optional[str] = None,
        user_id: Optional[int] = None,
        category_id: Optional[int] = None,
        category: Optional[str] = None,
    ) -> int:
        where, params = self._build_filters(query, user_id, category_id, category)
        sql = "SELECT COUNT(1) FROM saved_links"
        if where:
            sql += f" WHERE {where}"
        with self._get_conn() as conn:
            row = conn.execute(sql, params).fetchone()
            return int(row[0]) if row else 0

    def get_links(
        self,
        query: Optional[str] = None,
        user_id: Optional[int] = None,
        category_id: Optional[int] = None,
        category: Optional[str] = None,
        limit: int = 25,
        offset: int = 0,
    ) -> List[Dict]:
        where, params = self._build_filters(query, user_id, category_id, category)
        sql = (
            "SELECT id, url, normalized_url, domain, title, description, site_name, image_url, "
            "message_link, channel_id, author_id, created_at, category "
            "FROM saved_links"
        )
        if where:
            sql += f" WHERE {where}"
        sql += " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?"
        params = params + [limit, offset]

        with self._get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        results = []
        for row in rows:
            results.append(
                {
                    "id": row["id"],
                    "url": row["url"],
                    "normalized_url": row["normalized_url"],
                    "domain": row["domain"],
                    "title": row["title"],
                    "description": row["description"],
                    "site_name": row["site_name"],
                    "image_url": row["image_url"],
                    "message_link": row["message_link"],
                    "channel_id": row["channel_id"],
                    "author_id": row["author_id"],
                    "created_at": row["created_at"],
                    "category": row["category"],
                }
            )
        return results

    def _build_filters(
        self,
        query: Optional[str],
        user_id: Optional[int],
        category_id: Optional[int],
        category: Optional[str] = None,
    ) -> tuple[str, List]:
        filters = []
        params: List = []
        if query:
            like = f"%{query}%"
            filters.append(
                "(url LIKE ? OR title LIKE ? OR description LIKE ? OR site_name LIKE ? OR domain LIKE ?)"
            )
            params.extend([like, like, like, like, like])
        if user_id:
            filters.append("author_id = ?")
            params.append(user_id)
        if category_id:
            filters.append("category_id = ?")
            params.append(category_id)
        if category:
            filters.append("category = ?")
            params.append(category)
        where = " AND ".join(filters)
        return where, params
