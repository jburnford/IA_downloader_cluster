#!/usr/bin/env python3
"""
Workflow manager for Internet Archive PDF processing pipeline.

Provides commands to:
- Check status of downloads, OCR, and exports
- List pending items at each stage
- Generate reports
"""

import argparse
import sys
from pathlib import Path
from tabulate import tabulate

from archive_db import ArchiveDatabase


def cmd_status(db: ArchiveDatabase, subcollection: str = None):
    """Show overall workflow status."""
    stats = db.get_statistics(subcollection=subcollection)

    print("Internet Archive Workflow Status")
    print("=" * 70)

    if subcollection:
        print(f"Subcollection: {subcollection}")
    else:
        print("All subcollections")

    print()

    # Items
    print(f"Total items in database: {stats['total_items']}")
    print()

    # PDFs
    print("PDF Downloads:")
    pdf_status = stats.get('pdf_status', {})
    for status, count in pdf_status.items():
        print(f"  {status}: {count}")
    print(f"  Total: {sum(pdf_status.values())}")
    print()

    # OCR
    print("OCR Processing:")
    ocr_status = stats.get('ocr_status', {})
    for status, count in ocr_status.items():
        print(f"  {status}: {count}")

    total_ocr = sum(ocr_status.values())
    total_pdfs = sum(pdf_status.values())
    if total_pdfs > 0:
        pending_ocr = total_pdfs - total_ocr
        if pending_ocr > 0:
            print(f"  not_started: {pending_ocr}")
        print(f"  Total: {total_ocr} of {total_pdfs} PDFs")
    print()

    # Exports
    print("Exports:")
    print(f"  Completed: {stats.get('total_exports', 0)}")
    if 'ocr_status' in stats and 'completed' in stats['ocr_status']:
        pending = stats['ocr_status']['completed'] - stats.get('total_exports', 0)
        print(f"  Pending: {max(0, pending)}")
    print()


def cmd_list_pending_ocr(db: ArchiveDatabase, subcollection: str = None, limit: int = 20):
    """List PDFs that need OCR processing."""
    pending = db.get_pending_ocr(subcollection=subcollection)

    print(f"PDFs Pending OCR Processing: {len(pending)}")
    print("=" * 70)

    if not pending:
        print("No PDFs pending OCR.")
        return

    # Show first N items
    display_items = pending[:limit]

    table_data = []
    for item in display_items:
        table_data.append([
            item['identifier'][:30],
            item['filename'][:40],
            item.get('subcollection', 'None')[:20]
        ])

    print(tabulate(
        table_data,
        headers=['Identifier', 'Filename', 'Subcollection'],
        tablefmt='simple'
    ))

    if len(pending) > limit:
        print(f"\n... and {len(pending) - limit} more")


def cmd_list_pending_exports(db: ArchiveDatabase, subcollection: str = None, limit: int = 20):
    """List items that need export."""
    pending = db.get_pending_exports(subcollection=subcollection)

    print(f"Items Pending Export: {len(pending)}")
    print("=" * 70)

    if not pending:
        print("No items pending export.")
        return

    # Show first N items
    display_items = pending[:limit]

    table_data = []
    for item in display_items:
        table_data.append([
            item['identifier'][:30],
            item['filename'][:40]
        ])

    print(tabulate(
        table_data,
        headers=['Identifier', 'Filename'],
        tablefmt='simple'
    ))

    if len(pending) > limit:
        print(f"\n... and {len(pending) - limit} more")


def cmd_workflow_status(db: ArchiveDatabase, identifier: str = None, limit: int = 20):
    """Show detailed workflow status for items."""
    items = db.get_workflow_status(identifier=identifier)

    if not items:
        if identifier:
            print(f"No items found for identifier: {identifier}")
        else:
            print("No items in database.")
        return

    print(f"Workflow Status: {len(items)} items")
    print("=" * 70)

    display_items = items[:limit] if not identifier else items

    table_data = []
    for item in display_items:
        table_data.append([
            item['identifier'][:25] if item['identifier'] else 'N/A',
            item['filename'][:30] if item['filename'] else 'N/A',
            item.get('download_status', 'N/A')[:12],
            item.get('ocr_status', 'N/A')[:12],
            item.get('export_status', 'N/A')[:12]
        ])

    print(tabulate(
        table_data,
        headers=['Identifier', 'Filename', 'Download', 'OCR', 'Export'],
        tablefmt='simple'
    ))

    if len(items) > limit and not identifier:
        print(f"\n... and {len(items) - limit} more")
        print(f"Use --limit to show more, or specify an identifier")


def cmd_item_details(db: ArchiveDatabase, identifier: str):
    """Show detailed information about a specific item."""
    item = db.get_item(identifier)

    if not item:
        print(f"Item not found: {identifier}")
        return

    print(f"Item Details: {identifier}")
    print("=" * 70)
    print()

    # Metadata
    print("Metadata:")
    for key in ['title', 'creator', 'publisher', 'date', 'year', 'language', 'subject', 'collection']:
        value = item.get(key)
        if value:
            print(f"  {key}: {value}")
    print(f"  URL: {item.get('item_url', 'N/A')}")
    print()

    # PDFs
    pdfs = db.get_pdf_files_for_item(identifier)
    print(f"PDF Files: {len(pdfs)}")
    for pdf in pdfs:
        print(f"  - {pdf['filename']}")
        print(f"    Path: {pdf['filepath']}")
        print(f"    Size: {pdf.get('size_bytes', 0)} bytes")
        print(f"    SHA256: {pdf.get('sha256', 'N/A')[:16]}...")
        print(f"    Status: {pdf.get('download_status', 'unknown')}")

        # OCR status
        ocr = db.conn.execute(
            "SELECT * FROM ocr_processing WHERE pdf_file_id = ?",
            (pdf['id'],)
        ).fetchone()

        if ocr:
            ocr = dict(ocr)
            print(f"    OCR Status: {ocr.get('status', 'unknown')}")
            if ocr.get('json_output_path'):
                print(f"    OCR JSON: {ocr['json_output_path']}")

        # Export status
        export = db.conn.execute(
            "SELECT * FROM exports WHERE pdf_file_id = ?",
            (pdf['id'],)
        ).fetchone()

        if export:
            export = dict(export)
            print(f"    Export: {export.get('export_type', 'unknown')}")
            if export.get('json_output_path'):
                print(f"      JSON: {export['json_output_path']}")
            if export.get('markdown_output_path'):
                print(f"      Markdown: {export['markdown_output_path']}")

        print()


def main():
    parser = argparse.ArgumentParser(
        description="Manage Internet Archive PDF workflow"
    )
    parser.add_argument(
        "--db-path",
        default="archive_tracking.db",
        help="Path to SQLite database (default: archive_tracking.db)"
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # status command
    status_parser = subparsers.add_parser('status', help='Show overall status')
    status_parser.add_argument('--subcollection', help='Filter by subcollection')

    # pending-ocr command
    ocr_parser = subparsers.add_parser('pending-ocr', help='List PDFs needing OCR')
    ocr_parser.add_argument('--subcollection', help='Filter by subcollection')
    ocr_parser.add_argument('--limit', type=int, default=20, help='Max items to show')

    # pending-exports command
    export_parser = subparsers.add_parser('pending-exports', help='List items needing export')
    export_parser.add_argument('--subcollection', help='Filter by subcollection')
    export_parser.add_argument('--limit', type=int, default=20, help='Max items to show')

    # workflow command
    workflow_parser = subparsers.add_parser('workflow', help='Show workflow status for all items')
    workflow_parser.add_argument('--identifier', help='Show specific item')
    workflow_parser.add_argument('--limit', type=int, default=20, help='Max items to show')

    # item command
    item_parser = subparsers.add_parser('item', help='Show details for specific item')
    item_parser.add_argument('identifier', help='Item identifier')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Check database exists
    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"Error: Database not found: {db_path}")
        print("Create it by running the downloader with --db-path")
        sys.exit(1)

    # Execute command
    try:
        with ArchiveDatabase(args.db_path) as db:
            if args.command == 'status':
                cmd_status(db, args.subcollection)
            elif args.command == 'pending-ocr':
                cmd_list_pending_ocr(db, args.subcollection, args.limit)
            elif args.command == 'pending-exports':
                cmd_list_pending_exports(db, args.subcollection, args.limit)
            elif args.command == 'workflow':
                cmd_workflow_status(db, args.identifier, args.limit)
            elif args.command == 'item':
                cmd_item_details(db, args.identifier)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
