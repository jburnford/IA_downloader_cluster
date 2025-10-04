-- Internet Archive PDF Processing Database Schema
-- Tracks download, OCR processing, and export workflow
-- Database location: <project_dir>/archive_tracking.db

-- Core metadata from Internet Archive items
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
    metadata_json TEXT,  -- Full IA metadata as JSON
    notes TEXT
);

-- Track PDF files across different subcollections/directories
CREATE TABLE IF NOT EXISTS pdf_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identifier TEXT NOT NULL,
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,  -- Full path, can be in different directories
    subcollection TEXT,      -- Track which subcollection this belongs to
    size_bytes INTEGER,
    sha256 TEXT,
    download_status TEXT CHECK(download_status IN ('downloaded', 'failed', 'skipped', 'pending')),
    is_valid BOOLEAN DEFAULT 1,
    validation_error TEXT,
    download_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_verified TIMESTAMP,
    FOREIGN KEY (identifier) REFERENCES items(identifier),
    UNIQUE(filepath)
);

-- Index for common queries
CREATE INDEX IF NOT EXISTS idx_pdf_identifier ON pdf_files(identifier);
CREATE INDEX IF NOT EXISTS idx_pdf_subcollection ON pdf_files(subcollection);
CREATE INDEX IF NOT EXISTS idx_pdf_status ON pdf_files(download_status);

-- Track OCR processing workflow
CREATE TABLE IF NOT EXISTS ocr_processing (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pdf_file_id INTEGER NOT NULL,
    status TEXT CHECK(status IN ('pending', 'processing', 'completed', 'failed')) DEFAULT 'pending',
    ocr_engine TEXT DEFAULT 'olmOCR',
    json_output_path TEXT,
    started_date TIMESTAMP,
    completed_date TIMESTAMP,
    processing_time_seconds INTEGER,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    FOREIGN KEY (pdf_file_id) REFERENCES pdf_files(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ocr_status ON ocr_processing(status);
CREATE INDEX IF NOT EXISTS idx_ocr_pdf ON ocr_processing(pdf_file_id);

-- Track combined exports (metadata + OCR data)
CREATE TABLE IF NOT EXISTS exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pdf_file_id INTEGER NOT NULL,
    export_type TEXT CHECK(export_type IN ('json', 'markdown', 'both')),
    json_output_path TEXT,
    markdown_output_path TEXT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pdf_file_id) REFERENCES pdf_files(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_export_pdf ON exports(pdf_file_id);

-- Audit log for tracking changes and operations
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    operation TEXT,  -- 'download', 'ocr_start', 'ocr_complete', 'export', etc.
    table_name TEXT,
    record_id INTEGER,
    details TEXT,  -- JSON with additional context
    user TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_operation ON audit_log(operation);

-- View for complete workflow status
CREATE VIEW IF NOT EXISTS workflow_status AS
SELECT
    i.identifier,
    i.title,
    i.creator,
    i.year,
    i.subject,
    p.filename,
    p.filepath,
    p.subcollection,
    p.download_status,
    p.download_date,
    COALESCE(o.status, 'not_started') as ocr_status,
    o.json_output_path as ocr_json_path,
    o.completed_date as ocr_date,
    CASE
        WHEN e.json_output_path IS NOT NULL AND e.markdown_output_path IS NOT NULL THEN 'both'
        WHEN e.json_output_path IS NOT NULL THEN 'json_only'
        WHEN e.markdown_output_path IS NOT NULL THEN 'markdown_only'
        ELSE 'none'
    END as export_status,
    e.created_date as export_date
FROM items i
LEFT JOIN pdf_files p ON i.identifier = p.identifier
LEFT JOIN ocr_processing o ON p.id = o.pdf_file_id
LEFT JOIN exports e ON p.id = e.pdf_file_id
ORDER BY i.identifier, p.filename;

-- View for items needing OCR
CREATE VIEW IF NOT EXISTS pending_ocr AS
SELECT
    p.id as pdf_file_id,
    p.identifier,
    p.filename,
    p.filepath,
    p.subcollection
FROM pdf_files p
LEFT JOIN ocr_processing o ON p.id = o.pdf_file_id
WHERE p.download_status = 'downloaded'
  AND p.is_valid = 1
  AND (o.status IS NULL OR o.status = 'failed');

-- View for items needing export
CREATE VIEW IF NOT EXISTS pending_export AS
SELECT
    p.id as pdf_file_id,
    p.identifier,
    p.filename,
    p.filepath,
    o.json_output_path as ocr_json
FROM pdf_files p
INNER JOIN ocr_processing o ON p.id = o.pdf_file_id
LEFT JOIN exports e ON p.id = e.pdf_file_id
WHERE o.status = 'completed'
  AND e.id IS NULL;
