import os
import psycopg2
from psycopg2.extras import execute_values, RealDictCursor


class LeaderboardDB:
    def __init__(self):
        self.db_config = {
            "host": os.environ.get("DB_HOST"),
            "port": os.environ.get("DB_PORT", "5432"),
            "dbname": os.environ.get("DB_NAME"),
            "user": os.environ.get("DB_USER"),
            "password": os.environ.get("DB_PASSWORD"),
            "sslmode": "require",
        }

    def _get_connection(self):
        return psycopg2.connect(**self.db_config)

    def execute_query(self, query, params=None, fetch=True, dict_cursor=False):
        """Execute a query and optionally return results"""
        try:
            with self._get_connection() as conn:
                cursor_factory = RealDictCursor if dict_cursor else None
                with conn.cursor(cursor_factory=cursor_factory) as cur:
                    cur.execute(query, params)
                    if fetch:
                        return cur.fetchall()
                    return cur.rowcount
        except Exception as e:
            print(f"DB Error: {e}")
            raise

    def execute_values(self, query, values, page_size=100):
        """Execute a query with multiple value sets"""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    execute_values(cur, query, values, page_size=page_size)
                    return cur.rowcount
        except Exception as e:
            print(f"DB Error: {e}")
            raise


# For backward compatibility
def get_db_connection():
    db = LeaderboardDB()
    return db._get_connection()
