import sqlite3
from datetime import datetime, timezone, timedelta


class AccountabilityDB:
    def __init__(self):
        self.conn = sqlite3.connect("accountability.db")
        self.cursor = self.conn.cursor()
        self._setup_tables()
        self._upgrade_database()

    def _setup_tables(self):
        """Set up the database tables if they don't exist."""
        self.cursor.execute(
            """CREATE TABLE IF NOT EXISTS accountability (
                user_id INTEGER PRIMARY KEY, 
                novacoins INTEGER DEFAULT 0, 
                streak INTEGER DEFAULT 1,
                highest_streak INTEGER DEFAULT 1,
                last_logged TEXT,
                total_tasks INTEGER DEFAULT 0,
                grace_days_used INTEGER DEFAULT 0,
                weekly_target INTEGER DEFAULT 5
            )"""
        )
        self.cursor.execute(
            """CREATE TABLE IF NOT EXISTS accountability_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                user_id INTEGER, 
                task TEXT, 
                logged_date TEXT,
                logged_time TEXT,
                message_id INTEGER,
                reward INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES accountability(user_id)
            )"""
        )
        
        self.cursor.execute(
            """CREATE TABLE IF NOT EXISTS store_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                description TEXT,
                price INTEGER,
                is_active BOOLEAN DEFAULT 1
            )"""
        )
        
        self.cursor.execute(
            """CREATE TABLE IF NOT EXISTS user_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item_id INTEGER,
                purchase_date TEXT,
                is_used BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES accountability(user_id),
                FOREIGN KEY (item_id) REFERENCES store_items(id)
            )"""
        )
        
        self.cursor.execute(
            """CREATE TABLE IF NOT EXISTS user_reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                reminder_time TEXT,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES accountability(user_id)
            )"""
        )
        
        self.conn.commit()
        
    def _upgrade_database(self):
        """Add new columns to existing tables if needed."""
        
        self.cursor.execute("PRAGMA table_info(accountability)")
        columns = [info[1] for info in self.cursor.fetchall()]
        
        
        new_columns = {
            "highest_streak": "INTEGER DEFAULT 1",
            "total_tasks": "INTEGER DEFAULT 0",
            "grace_days_used": "INTEGER DEFAULT 0",
            "weekly_target": "INTEGER DEFAULT 5"
        }
        
        for column, data_type in new_columns.items():
            if column not in columns:
                self.cursor.execute(f"ALTER TABLE accountability ADD COLUMN {column} {data_type}")
        
        
        self.cursor.execute("PRAGMA table_info(accountability_logs)")
        log_columns = [info[1] for info in self.cursor.fetchall()]
        
        if "reward" not in log_columns:
            self.cursor.execute("ALTER TABLE accountability_logs ADD COLUMN reward INTEGER DEFAULT 0")
            
        self.conn.commit()

    def get_user_stats(self, user_id):
        """Get a user's stats from the database."""
        self.cursor.execute(
            "SELECT novacoins, streak, last_logged, highest_streak, total_tasks, grace_days_used, weekly_target FROM accountability WHERE user_id = ?",
            (user_id,),
        )
        return self.cursor.fetchone()

    def update_user_stats(self, user_id, novacoins, streak, last_logged, highest_streak=None, grace_days_used=None):
        """Update a user's stats in the database."""
        
        if highest_streak is None or grace_days_used is None:
            current_stats = self.get_user_stats(user_id)
            if current_stats:
                if highest_streak is None:
                    highest_streak = current_stats[3]
                if grace_days_used is None:
                    grace_days_used = current_stats[5]
        
        
        if highest_streak < streak:
            highest_streak = streak
        
        self.cursor.execute(
            "UPDATE accountability SET novacoins = ?, streak = ?, last_logged = ?, highest_streak = ?, grace_days_used = ? WHERE user_id = ?",
            (novacoins, streak, last_logged, highest_streak, grace_days_used, user_id),
        )
        self.conn.commit()

    def create_user(self, user_id, novacoins, streak, last_logged):
        """Create a new user in the database."""
        self.cursor.execute(
            "INSERT INTO accountability (user_id, novacoins, streak, last_logged, highest_streak, total_tasks, grace_days_used) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, novacoins, streak, last_logged, streak, 0, 0),
        )
        self.conn.commit()

    def log_task(self, user_id, task, logged_date, logged_time, reward=0):
        """Log a task for a user."""
        self.cursor.execute(
            "INSERT INTO accountability_logs (user_id, task, logged_date, logged_time, reward) VALUES (?, ?, ?, ?, ?)",
            (user_id, task, logged_date, logged_time, reward),
        )
        
        
        self.cursor.execute(
            "UPDATE accountability SET total_tasks = total_tasks + 1 WHERE user_id = ?",
            (user_id,),
        )
        
        self.conn.commit()
        return self.cursor.lastrowid

    def get_tasks_for_day(self, user_id, date):
        """Get all tasks for a user on a specific day."""
        self.cursor.execute(
            "SELECT task, message_id, logged_time FROM accountability_logs WHERE user_id = ? AND logged_date = ? ORDER BY logged_time ASC",
            (user_id, date),
        )
        return self.cursor.fetchall()
        
    def get_task_by_number(self, user_id, date, task_number):
        """Get a specific task by its number for a user on a specific day."""
        self.cursor.execute(
            "SELECT id, task, message_id FROM accountability_logs WHERE user_id = ? AND logged_date = ? ORDER BY logged_time ASC",
            (user_id, date),
        )
        rows = self.cursor.fetchall()
        
        if not rows or task_number < 1 or task_number > len(rows):
            return None
            
        return rows[task_number - 1]
        
    def delete_task(self, task_id):
        """Delete a task from the database."""
        
        self.cursor.execute("SELECT user_id FROM accountability_logs WHERE id = ?", (task_id,))
        result = self.cursor.fetchone()
        
        if result:
            user_id = result[0]
            
            self.cursor.execute(
                "UPDATE accountability SET total_tasks = total_tasks - 1 WHERE user_id = ? AND total_tasks > 0",
                (user_id,),
            )
        
        self.cursor.execute("DELETE FROM accountability_logs WHERE id = ?", (task_id,))
        self.conn.commit()

    def update_task_message_id(self, user_id, date, message_id):
        """Update the message ID for all tasks on a specific day."""
        self.cursor.execute(
            "UPDATE accountability_logs SET message_id = ? WHERE user_id = ? AND logged_date = ?",
            (message_id, user_id, date),
        )
        self.conn.commit()

    def get_user_history(self, user_id, limit=10):
        """Get a user's task history."""
        self.cursor.execute(
            "SELECT task, logged_date, logged_time, reward FROM accountability_logs WHERE user_id = ? ORDER BY logged_time DESC LIMIT ?",
            (user_id, limit),
        )
        return self.cursor.fetchall()

    def get_leaderboard(self, limit=10, by_streak=False):
        """Get the accountability leaderboard."""
        if by_streak:
            self.cursor.execute(
                "SELECT user_id, streak, highest_streak FROM accountability ORDER BY streak DESC, highest_streak DESC LIMIT ?",
                (limit,),
            )
        else:
            self.cursor.execute(
                "SELECT user_id, novacoins, streak FROM accountability ORDER BY novacoins DESC LIMIT ?",
                (limit,),
            )
        return self.cursor.fetchall()

    def get_weekly_tasks_count(self, user_id):
        """Get the number of tasks logged by a user in the current week."""
        
        today = datetime.now(timezone.utc).date()
        start_of_week = today - timedelta(days=today.weekday())
        
        self.cursor.execute(
            "SELECT COUNT(*) FROM accountability_logs WHERE user_id = ? AND date(logged_date) >= date(?)",
            (user_id, start_of_week),
        )
        
        return self.cursor.fetchone()[0]
        
    def update_weekly_target(self, user_id, target):
        """Update a user's weekly task target."""
        self.cursor.execute(
            "UPDATE accountability SET weekly_target = ? WHERE user_id = ?",
            (target, user_id),
        )
        self.conn.commit()
    
    def add_store_item(self, name, description, price):
        """Add a new item to the store."""
        try:
            self.cursor.execute(
                "INSERT INTO store_items (name, description, price) VALUES (?, ?, ?)",
                (name, description, price),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
            
    def get_store_items(self):
        """Get all active items from the store."""
        self.cursor.execute(
            "SELECT id, name, description, price FROM store_items WHERE is_active = 1"
        )
        return self.cursor.fetchall()
        
    def purchase_item(self, user_id, item_id):
        """Record a user's purchase of an item."""
        purchase_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        self.cursor.execute(
            "INSERT INTO user_items (user_id, item_id, purchase_date) VALUES (?, ?, ?)",
            (user_id, item_id, purchase_date),
        )
        self.conn.commit()
        
    def get_user_items(self, user_id, unused_only=False):
        """Get all items owned by a user."""
        if unused_only:
            self.cursor.execute(
                """
                SELECT ui.id, s.name, s.description, ui.purchase_date 
                FROM user_items ui
                JOIN store_items s ON ui.item_id = s.id
                WHERE ui.user_id = ? AND ui.is_used = 0
                """,
                (user_id,),
            )
        else:
            self.cursor.execute(
                """
                SELECT ui.id, s.name, s.description, ui.purchase_date, ui.is_used 
                FROM user_items ui
                JOIN store_items s ON ui.item_id = s.id
                WHERE ui.user_id = ?
                """,
                (user_id,),
            )
        return self.cursor.fetchall()
        
    def use_item(self, user_item_id):
        """Mark an item as used."""
        self.cursor.execute(
            "UPDATE user_items SET is_used = 1 WHERE id = ?",
            (user_item_id,),
        )
        self.conn.commit()

    def reset_user(self, user_id):
        """Reset a user's stats and logs."""
        self.cursor.execute("DELETE FROM accountability WHERE user_id = ?", (user_id,))
        self.cursor.execute("DELETE FROM accountability_logs WHERE user_id = ?", (user_id,))
        self.cursor.execute("DELETE FROM user_items WHERE user_id = ?", (user_id,))
        self.conn.commit()

    def get_all_users(self):
        """Get all users from the database."""
        self.cursor.execute("SELECT DISTINCT user_id FROM accountability")
        return [row[0] for row in self.cursor.fetchall()]

    def set_reminder(self, user_id, reminder_time):
        """Set a daily reminder for a user."""
        
        self.cursor.execute(
            "DELETE FROM user_reminders WHERE user_id = ?",
            (user_id,),
        )
        
        
        self.cursor.execute(
            "INSERT INTO user_reminders (user_id, reminder_time) VALUES (?, ?)",
            (user_id, reminder_time),
        )
        self.conn.commit()
        return True
        
    def get_user_reminder(self, user_id):
        """Get a user's active reminder."""
        self.cursor.execute(
            "SELECT reminder_time FROM user_reminders WHERE user_id = ? AND is_active = 1",
            (user_id,),
        )
        result = self.cursor.fetchone()
        return result[0] if result else None
        
    def delete_reminder(self, user_id):
        """Delete a user's reminders."""
        self.cursor.execute(
            "DELETE FROM user_reminders WHERE user_id = ?",
            (user_id,),
        )
        self.conn.commit()
        return True
        
    def get_all_active_reminders(self, current_hour=None, current_minute=None):
        """Get all active reminders for users.
        If current_hour and current_minute are provided, only returns reminders that match that time."""
        if current_hour is not None and current_minute is not None:
            
            time_condition = f"{current_hour:02d}:{current_minute:02d}"
            
            self.cursor.execute(
                """
                SELECT ur.user_id, ur.reminder_time 
                FROM user_reminders ur
                JOIN accountability a ON ur.user_id = a.user_id
                WHERE ur.is_active = 1 
                AND ur.reminder_time = ?
                """,
                (time_condition,),
            )
        else:
            self.cursor.execute(
                """
                SELECT ur.user_id, ur.reminder_time 
                FROM user_reminders ur
                JOIN accountability a ON ur.user_id = a.user_id
                WHERE ur.is_active = 1
                """
            )
        
        return self.cursor.fetchall()

    def close(self):
        """Close the database connection."""
        self.conn.close()