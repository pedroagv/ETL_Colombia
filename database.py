import os
import sqlite3
from datetime import datetime

class DianDatabase:
    def __init__(self, db_path="dian_downloads.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """
        Inicializa la base de datos SQLite y crea la tabla downloads si no existe.
        """
        query = """
        CREATE TABLE IF NOT EXISTS downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_type TEXT CHECK(file_type IN ('importaciones', 'exportaciones')),
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            url TEXT UNIQUE NOT NULL,
            filename TEXT NOT NULL,
            status TEXT NOT NULL, -- 'SUCCESS', 'FAILED', 'NOT_FOUND', 'CORRUPT'
            downloaded_at TEXT,
            file_size INTEGER,
            sha256 TEXT
        );
        """
        with self._get_connection() as conn:
            conn.execute(query)
            conn.commit()

    def is_already_downloaded(self, url):
        """
        Verifica si la URL ya se descargó correctamente.
        """
        query = "SELECT status FROM downloads WHERE url = ? AND status = 'SUCCESS'"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (url,))
            result = cursor.fetchone()
            return result is not None

    def get_download_status(self, url):
        """
        Obtiene el registro de descarga para una URL específica.
        """
        query = "SELECT status, downloaded_at, file_size, sha256 FROM downloads WHERE url = ?"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (url,))
            row = cursor.fetchone()
            if row:
                return {
                    'status': row[0],
                    'downloaded_at': row[1],
                    'file_size': row[2],
                    'sha256': row[3]
                }
            return None

    def record_download(self, file_type, year, month, url, filename, status, file_size=None, sha256=None):
        """
        Registra o actualiza el intento de descarga en la base de datos.
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query = """
        INSERT OR REPLACE INTO downloads (file_type, year, month, url, filename, status, downloaded_at, file_size, sha256)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._get_connection() as conn:
            conn.execute(query, (file_type, year, month, url, filename, status, now, file_size, sha256))
            conn.commit()
