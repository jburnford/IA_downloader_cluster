#!/usr/bin/env python3
"""
Database management for Internet Archive PDF workflow tracking.

Tracks:
- PDF downloads and metadata from Internet Archive
- OCR processing status (olmOCR)
- Export generation (JSON + Markdown)
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class ArchiveDatabase:
    """Manage SQLite database for tracking PDF workflow."""

    def __init__(self, db_path: str = "archive_tracking.db"):
        """Initialize database connection."""
        self.db_path = Path(db_path)
        self.conn = None
        self.connect()
        self.init_schema()

    def connect(self):
        """Establish database connection."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        # Enable foreign keys
        self.conn.execute("PRAGMA foreign_keys = ON")

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def init_schema(self):
        """Initialize database schema."""
        schema_file = Path(__file__).parent / "database_schema.sql"

        if schema_file.exists():
            with open(schema_file) as f:
                self.conn.executescript(f.read())
        else:
            # Fallback inline schema
            self._create_inline_schema()

        self.conn.commit()

    def _create_inline_schema(self):
        """Create schema inline if schema file not found."""
        # Basic tables - see database_schema.sql for full version
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS items (
                identifier TEXT PRIMARY KEY,
                title TEXT,
                creator TEXT,
                publisher TEXT,
                date TEXT,
                year INTEGER,
                language TEXT,
                subject TEXT,
                collection TEXT,
                description TEXT,
                item_url TEXT,
                download_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata_json TEXT,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS pdf_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identifier TEXT NOT NULL,
                filename TEXT NOT NULL,
                filepath TEXT NOT NULL,
                subcollection TEXT,
                size_bytes INTEGER,
                sha256 TEXT,
                download_status TEXT DEFAULT 'downloaded',
                is_valid BOOLEAN DEFAULT 1,
                validation_error TEXT,
                download_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_verified TIMESTAMP,
                FOREIGN KEY (identifier) REFERENCES items(identifier),
                UNIQUE(filepath)
            );

            CREATE TABLE IF NOT EXISTS ocr_processing (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pdf_file_id INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                ocr_engine TEXT DEFAULT 'olmOCR',
                json_output_path TEXT,
                started_date TIMESTAMP,
                completed_date TIMESTAMP,
                processing_time_seconds INTEGER,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                FOREIGN KEY (pdf_file_id) REFERENCES pdf_files(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS exports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pdf_file_id INTEGER NOT NULL,
                export_type TEXT,
                json_output_path TEXT,
                markdown_output_path TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pdf_file_id) REFERENCES pdf_files(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                operation TEXT,
                table_name TEXT,
                record_id INTEGER,
                details TEXT,
                user TEXT
            );
        """)

    # ==================== ITEM OPERATIONS ====================

    def add_item(self, identifier: str, metadata: Dict) -> bool:
        """
        Add or update Internet Archive item metadata.

        Args:
            identifier: Internet Archive identifier
            metadata: Dictionary with item metadata

        Returns:
            True if successful
        """
        try:
            # Extract common fields
            title = metadata.get("title", "")
            if isinstance(title, list):
                title = title[0] if title else ""

            creator = metadata.get("creator", "")
            if isinstance(creator, list):
                creator = "; ".join(creator)

            subject = metadata.get("subject", "")
            if isinstance(subject, list):
                subject = "; ".join(subject)

            collection = metadata.get("collection", "")
            if isinstance(collection, list):
                collection = "; ".join(collection)

            year = metadata.get("year")
            if year:
                try:
                    year = int(year)
                except (ValueError, TypeError):
                    year = None

            self.conn.execute("""
                INSERT OR REPLACE INTO items (
                    identifier, title, creator, publisher, date, year,
                    language, subject, collection, description, item_url,
                    metadata_json, download_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                identifier,
                title,
                creator,
                metadata.get("publisher", ""),
                metadata.get("date", ""),
                year,
                metadata.get("language", ""),
                subject,
                collection,
                metadata.get("description", ""),
                f"https://archive.org/details/{identifier}",
                json.dumps(metadata),
                datetime.now()
            ))

            self.conn.commit()
            self._log_audit("download", "items", identifier, {"action": "add_item"})
            return True

        except Exception as e:
            print(f"Error adding item {identifier}: {e}")
            return False

    def get_item(self, identifier: str) -> Optional[Dict]:
        """Get item metadata by identifier."""
        cursor = self.conn.execute(
            "SELECT * FROM items WHERE identifier = ?",
            (identifier,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    # ==================== PDF FILE OPERATIONS ====================

    def add_pdf_file(
        self,
        identifier: str,
        filename: str,
        filepath: str,
        subcollection: str = None,
        size_bytes: int = None,
        sha256: str = None,
        download_status: str = "downloaded",
        is_valid: bool = True
    ) -> Optional[int]:
        """
        Add PDF file record.

        Returns:
            PDF file ID if successful, None otherwise
        """
        try:
            cursor = self.conn.execute("""
                INSERT OR REPLACE INTO pdf_files (
                    identifier, filename, filepath, subcollection,
                    size_bytes, sha256, download_status, is_valid,
                    download_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                identifier, filename, str(filepath), subcollection,
                size_bytes, sha256, download_status, is_valid,
                datetime.now()
            ))

            self.conn.commit()
            pdf_id = cursor.lastrowid

            self._log_audit("download", "pdf_files", pdf_id, {
                "filename": filename,
                "status": download_status
            })

            return pdf_id

        except Exception as e:
            print(f"Error adding PDF file {filename}: {e}")
            return None

    def get_pdf_file_by_path(self, filepath: str) -> Optional[Dict]:
        """Get PDF file record by filepath."""
        cursor = self.conn.execute(
            "SELECT * FROM pdf_files WHERE filepath = ?",
            (str(filepath),)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_pdf_files_for_item(self, identifier: str) -> List[Dict]:
        """Get all PDF files for an item."""
        cursor = self.conn.execute(
            "SELECT * FROM pdf_files WHERE identifier = ? ORDER BY filename",
            (identifier,)
        )
        return [dict(row) for row in cursor.fetchall()]

    # ==================== OCR OPERATIONS ====================

    def add_ocr_record(self, pdf_file_id: int, status: str = "pending") -> Optional[int]:
        """Initialize OCR processing record."""
        try:
            cursor = self.conn.execute("""
                INSERT INTO ocr_processing (pdf_file_id, status, started_date)
                VALUES (?, ?, ?)
            """, (pdf_file_id, status, datetime.now() if status == "processing" else None))

            self.conn.commit()
            return cursor.lastrowid

        except Exception as e:
            print(f"Error creating OCR record: {e}")
            return None

    def update_ocr_status(
        self,
        pdf_file_id: int,
        status: str,
        json_output_path: str = None,
        error_message: str = None
    ) -> bool:
        """Update OCR processing status."""
        try:
            updates = {"status": status}

            if status == "processing":
                updates["started_date"] = datetime.now()
            elif status == "completed":
                updates["completed_date"] = datetime.now()
                if json_output_path:
                    updates["json_output_path"] = json_output_path
            elif status == "failed" and error_message:
                updates["error_message"] = error_message

            set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
            values = list(updates.values()) + [pdf_file_id]

            self.conn.execute(f"""
                UPDATE ocr_processing
                SET {set_clause}
                WHERE pdf_file_id = ?
            """, values)

            self.conn.commit()

            self._log_audit("ocr_update", "ocr_processing", pdf_file_id, updates)
            return True

        except Exception as e:
            print(f"Error updating OCR status: {e}")
            return False

    def get_pending_ocr(self, subcollection: str = None) -> List[Dict]:
        """Get PDFs that need OCR processing."""
        query = """
            SELECT p.id, p.identifier, p.filename, p.filepath, p.subcollection
            FROM pdf_files p
            LEFT JOIN ocr_processing o ON p.id = o.pdf_file_id
            WHERE p.download_status = 'downloaded'
              AND p.is_valid = 1
              AND (o.status IS NULL OR o.status = 'failed')
        """

        params = []
        if subcollection:
            query += " AND p.subcollection = ?"
            params.append(subcollection)

        query += " ORDER BY p.download_date"

        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    # ==================== EXPORT OPERATIONS ====================

    def add_export(
        self,
        pdf_file_id: int,
        export_type: str,
        json_path: str = None,
        markdown_path: str = None
    ) -> Optional[int]:
        """Record export generation."""
        try:
            cursor = self.conn.execute("""
                INSERT INTO exports (
                    pdf_file_id, export_type, json_output_path,
                    markdown_output_path, created_date
                ) VALUES (?, ?, ?, ?, ?)
            """, (pdf_file_id, export_type, json_path, markdown_path, datetime.now()))

            self.conn.commit()
            return cursor.lastrowid

        except Exception as e:
            print(f"Error adding export record: {e}")
            return None

    def get_pending_exports(self, subcollection: str = None) -> List[Dict]:
        """Get items with completed OCR but no export."""
        query = """
            SELECT p.id, p.identifier, p.filename, p.filepath,
                   o.json_output_path as ocr_json
            FROM pdf_files p
            INNER JOIN ocr_processing o ON p.id = o.pdf_file_id
            LEFT JOIN exports e ON p.id = e.pdf_file_id
            WHERE o.status = 'completed'
              AND e.id IS NULL
        """

        params = []
        if subcollection:
            query += " AND p.subcollection = ?"
            params.append(subcollection)

        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    # ==================== REPORTING ====================

    def get_workflow_status(self, identifier: str = None) -> List[Dict]:
        """Get complete workflow status."""
        query = "SELECT * FROM workflow_status"
        params = []

        if identifier:
            query += " WHERE identifier = ?"
            params.append(identifier)

        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_statistics(self, subcollection: str = None) -> Dict:
        """Get overall statistics."""
        where_clause = ""
        params = []

        if subcollection:
            where_clause = "WHERE p.subcollection = ?"
            params = [subcollection]

        stats = {}

        # Total items
        cursor = self.conn.execute("SELECT COUNT(*) FROM items")
        stats["total_items"] = cursor.fetchone()[0]

        # PDF statistics
        cursor = self.conn.execute(f"""
            SELECT download_status, COUNT(*) as count
            FROM pdf_files p
            {where_clause}
            GROUP BY download_status
        """, params)
        stats["pdf_status"] = {row[0]: row[1] for row in cursor.fetchall()}

        # OCR statistics
        cursor = self.conn.execute(f"""
            SELECT o.status, COUNT(*) as count
            FROM ocr_processing o
            JOIN pdf_files p ON o.pdf_file_id = p.id
            {where_clause}
            GROUP BY o.status
        """, params)
        stats["ocr_status"] = {row[0]: row[1] for row in cursor.fetchall()}

        # Export statistics
        cursor = self.conn.execute(f"""
            SELECT COUNT(*) FROM exports e
            JOIN pdf_files p ON e.pdf_file_id = p.id
            {where_clause}
        """, params)
        stats["total_exports"] = cursor.fetchone()[0]

        return stats

    # ==================== UTILITY ====================

    def _log_audit(self, operation: str, table_name: str, record_id, details: Dict):
        """Log operation to audit log."""
        try:
            self.conn.execute("""
                INSERT INTO audit_log (operation, table_name, record_id, details)
                VALUES (?, ?, ?, ?)
            """, (operation, table_name, record_id, json.dumps(details)))
            self.conn.commit()
        except Exception:
            pass  # Audit logging is best-effort

    def vacuum(self):
        """Optimize database."""
        self.conn.execute("VACUUM")
        self.conn.commit()
