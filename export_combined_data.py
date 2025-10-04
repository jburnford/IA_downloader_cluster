#!/usr/bin/env python3
"""
Export combined metadata + OCR data to JSON and Markdown files.

Creates:
- JSON file with complete metadata + OCR text
- Markdown file with metadata frontmatter + OCR text
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from archive_db import ArchiveDatabase


def load_ocr_jsonl(filepath: Path) -> Dict:
    """
    Load olmOCR JSONL file and combine all records.

    olmOCR format: Each line is a JSON object with:
    - id: unique identifier
    - text: OCR text content
    - source: "olmocr"
    - added: timestamp
    - created: timestamp
    - metadata: dict with Source-File, olmocr-version, pdf-total-pages, token counts, etc.

    Returns:
        Dict with combined OCR data
    """
    records = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        print(f"Warning: Could not parse JSON line: {e}")
                        continue
    except Exception as e:
        print(f"Error loading OCR file {filepath}: {e}")
        return None

    if not records:
        return None

    # Combine all text from records
    combined_text = []
    ocr_metadata = {}
    total_pages = 0
    total_input_tokens = 0
    total_output_tokens = 0

    for record in records:
        # Extract text content
        if 'text' in record and record['text']:
            combined_text.append(record['text'])

        # Capture metadata from first record
        if not ocr_metadata and 'metadata' in record:
            ocr_metadata = record['metadata']
            total_pages = ocr_metadata.get('pdf-total-pages', 0)
            total_input_tokens = ocr_metadata.get('total-input-tokens', 0)
            total_output_tokens = ocr_metadata.get('total-output-tokens', 0)

    # Join text with page breaks
    full_text = '\n\n---\n\n'.join(combined_text)

    return {
        'text': full_text,
        'ocr_metadata': {
            'olmocr_version': ocr_metadata.get('olmocr-version', 'unknown'),
            'source_file': ocr_metadata.get('Source-File', ''),
            'pdf_total_pages': total_pages,
            'total_input_tokens': total_input_tokens,
            'total_output_tokens': total_output_tokens,
        },
        'record_count': len(records),
        'total_length': len(full_text),
        'page_count': total_pages
    }


def create_combined_json(item_data: Dict, pdf_data: Dict, ocr_data: Dict) -> Dict:
    """Create combined JSON with all metadata and OCR text."""
    return {
        'identifier': item_data['identifier'],
        'metadata': {
            'title': item_data['title'],
            'creator': item_data['creator'],
            'publisher': item_data['publisher'],
            'date': item_data['date'],
            'year': item_data['year'],
            'language': item_data['language'],
            'subject': item_data['subject'],
            'collection': item_data['collection'],
            'description': item_data['description'],
            'item_url': item_data['item_url'],
        },
        'pdf': {
            'filename': pdf_data['filename'],
            'filepath': pdf_data['filepath'],
            'size_bytes': pdf_data['size_bytes'],
            'sha256': pdf_data['sha256'],
            'download_date': pdf_data['download_date'],
        },
        'ocr': {
            'engine': 'olmOCR',
            'version': ocr_data.get('ocr_metadata', {}).get('olmocr_version', 'unknown'),
            'text': ocr_data['text'],
            'metadata': ocr_data.get('ocr_metadata', {}),
            'statistics': {
                'record_count': ocr_data['record_count'],
                'page_count': ocr_data.get('page_count', 0),
                'total_length': ocr_data['total_length'],
                'input_tokens': ocr_data.get('ocr_metadata', {}).get('total_input_tokens', 0),
                'output_tokens': ocr_data.get('ocr_metadata', {}).get('total_output_tokens', 0),
            }
        },
        'generated': datetime.now().isoformat()
    }


def create_markdown(item_data: Dict, pdf_data: Dict, ocr_data: Dict) -> str:
    """Create Markdown file with YAML frontmatter."""
    # Build YAML frontmatter
    frontmatter = [
        "---",
        f"identifier: {item_data['identifier']}",
        f"title: \"{item_data['title'] or 'Unknown'}\"",
    ]

    if item_data['creator']:
        frontmatter.append(f"creator: \"{item_data['creator']}\"")

    if item_data['year']:
        frontmatter.append(f"year: {item_data['year']}")

    if item_data['date']:
        frontmatter.append(f"date: \"{item_data['date']}\"")

    if item_data['publisher']:
        frontmatter.append(f"publisher: \"{item_data['publisher']}\"")

    if item_data['language']:
        frontmatter.append(f"language: \"{item_data['language']}\"")

    if item_data['subject']:
        # Split subjects if semicolon-separated
        subjects = [s.strip() for s in item_data['subject'].split(';') if s.strip()]
        if subjects:
            frontmatter.append("subjects:")
            for subj in subjects:
                frontmatter.append(f"  - \"{subj}\"")

    if item_data['collection']:
        collections = [c.strip() for c in item_data['collection'].split(';') if c.strip()]
        if collections:
            frontmatter.append("collections:")
            for coll in collections:
                frontmatter.append(f"  - \"{coll}\"")

    ocr_meta = ocr_data.get('ocr_metadata', {})

    frontmatter.extend([
        f"source: {item_data['item_url']}",
        f"pdf_filename: \"{pdf_data['filename']}\"",
        f"pdf_sha256: \"{pdf_data['sha256']}\"",
        f"pdf_pages: {ocr_meta.get('pdf_total_pages', 'unknown')}",
        "ocr_engine: olmOCR",
        f"ocr_version: \"{ocr_meta.get('olmocr_version', 'unknown')}\"",
        f"generated: {datetime.now().isoformat()}",
        "---",
        ""
    ])

    # Build content
    content = [
        f"# {item_data['title'] or 'Untitled'}",
        ""
    ]

    if item_data['description']:
        content.extend([
            "## Description",
            "",
            item_data['description'],
            ""
        ])

    content.extend([
        "## OCR Text",
        "",
        ocr_data['text'],
        "",
        "---",
        "",
        f"*OCR processed {ocr_data.get('page_count', 0)} pages in {ocr_data['record_count']} records*  ",
        f"*Total length: {ocr_data['total_length']:,} characters*  ",
        f"*olmOCR version: {ocr_data.get('ocr_metadata', {}).get('olmocr_version', 'unknown')}*"
    ])

    return '\n'.join(frontmatter + content)


def export_files(
    db: ArchiveDatabase,
    output_dir: Path,
    subcollection: str = None,
    export_type: str = "both",
    dry_run: bool = False
):
    """
    Export combined data files.

    Args:
        db: Database instance
        output_dir: Output directory for exports
        subcollection: Filter by subcollection
        export_type: 'json', 'markdown', or 'both'
        dry_run: If True, only show what would be done
    """
    print(f"Exporting to: {output_dir}")
    print(f"Export type: {export_type}")
    print(f"Subcollection filter: {subcollection or 'All'}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print("-" * 70)

    # Create output directories
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        if export_type in ('json', 'both'):
            (output_dir / 'json').mkdir(exist_ok=True)
        if export_type in ('markdown', 'both'):
            (output_dir / 'markdown').mkdir(exist_ok=True)

    # Get items ready for export
    pending = db.get_pending_exports(subcollection=subcollection)

    print(f"Found {len(pending)} items ready for export")
    print()

    if not pending:
        print("No items ready for export.")
        print("Items need completed OCR status first.")
        return

    exported_count = 0
    error_count = 0

    for item in pending:
        pdf_id = item['id']
        identifier = item['identifier']
        filename = item['filename']
        ocr_json_path = Path(item['ocr_json'])

        print(f"Processing: {identifier} / {filename}")

        # Get full item metadata
        item_data = db.get_item(identifier)
        if not item_data:
            print(f"  Error: No metadata found for {identifier}")
            error_count += 1
            continue

        # Get PDF data
        pdf_data = db.get_pdf_file_by_path(item['filepath'])
        if not pdf_data:
            print(f"  Error: No PDF data found")
            error_count += 1
            continue

        # Load OCR data
        ocr_data = load_ocr_jsonl(ocr_json_path)
        if not ocr_data:
            print(f"  Error: Could not load OCR data from {ocr_json_path}")
            error_count += 1
            continue

        # Generate base filename (remove .pdf extension if present)
        base_name = Path(filename).stem

        json_path = None
        markdown_path = None

        # Create JSON export
        if export_type in ('json', 'both'):
            json_path = output_dir / 'json' / f"{base_name}.json"
            print(f"  JSON: {json_path.name}")

            if not dry_run:
                combined_data = create_combined_json(item_data, pdf_data, ocr_data)
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(combined_data, f, indent=2, ensure_ascii=False)

        # Create Markdown export
        if export_type in ('markdown', 'both'):
            markdown_path = output_dir / 'markdown' / f"{base_name}.md"
            print(f"  Markdown: {markdown_path.name}")

            if not dry_run:
                markdown_content = create_markdown(item_data, pdf_data, ocr_data)
                with open(markdown_path, 'w', encoding='utf-8') as f:
                    f.write(markdown_content)

        # Record export in database
        if not dry_run:
            db.add_export(
                pdf_file_id=pdf_id,
                export_type=export_type,
                json_path=str(json_path) if json_path else None,
                markdown_path=str(markdown_path) if markdown_path else None
            )

        exported_count += 1

    print()
    print("=" * 70)
    print(f"Summary:")
    print(f"  Successfully exported: {exported_count}")
    print(f"  Errors: {error_count}")

    if dry_run:
        print()
        print("This was a DRY RUN. No files were created.")
        print("Run without --dry-run to generate exports.")


def main():
    parser = argparse.ArgumentParser(
        description="Export combined metadata + OCR data to JSON and Markdown"
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Output directory for exports"
    )
    parser.add_argument(
        "--db-path",
        default="archive_tracking.db",
        help="Path to SQLite database (default: archive_tracking.db)"
    )
    parser.add_argument(
        "--subcollection",
        help="Only export files from this subcollection"
    )
    parser.add_argument(
        "--type",
        choices=['json', 'markdown', 'both'],
        default='both',
        help="Export type (default: both)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without creating files"
    )

    args = parser.parse_args()

    # Initialize database
    try:
        with ArchiveDatabase(args.db_path) as db:
            export_files(
                db=db,
                output_dir=args.output_dir,
                subcollection=args.subcollection,
                export_type=args.type,
                dry_run=args.dry_run
            )
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
