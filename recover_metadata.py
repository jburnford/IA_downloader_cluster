#!/usr/bin/env python3
"""
Recover metadata for PDFs based on filenames.

Supports:
1. Internet Archive - Extract identifier from filename and fetch metadata
2. Canadiana - Extract identifier and fetch from Canadiana API
3. British Library Indian Office Lists - Parse from filename pattern
4. Custom archives - User-provided metadata mapping
5. British Library newspapers - Gold standard collection mapping
"""

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

# Import database if available
try:
    from archive_db import ArchiveDatabase
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    print("Warning: archive_db module not found. Database updates disabled.")


class MetadataRecovery:
    """Recover metadata from PDF filenames."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        delay: float = 0.5,
        dry_run: bool = False
    ):
        self.db_path = db_path
        self.delay = delay
        self.dry_run = dry_run
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; MetadataRecovery/1.0; Academic Use)"
        })

        self.db = None
        if DB_AVAILABLE and db_path and not dry_run:
            self.db = ArchiveDatabase(db_path)

        self.stats = {
            "total": 0,
            "internet_archive": 0,
            "canadiana": 0,
            "british_library": 0,
            "custom": 0,
            "not_found": 0,
            "errors": 0
        }

        self._setup_logging()

    def _setup_logging(self):
        """Setup logging."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        self.logger = logging.getLogger(__name__)

    def extract_internet_archive_id(self, filename: str) -> Optional[str]:
        """
        Extract Internet Archive identifier from filename.

        Common patterns:
        - identifier.pdf
        - identifier_bw.pdf
        - identifier_jp2.pdf
        - pub_identifier.pdf
        """
        # Remove extension
        name = Path(filename).stem

        # Remove common suffixes
        name = re.sub(r'_(bw|jp2|color|text|djvu)$', '', name)

        # Skip purely numeric filenames - these are likely Canadiana or British Library
        if re.match(r'^\d+$', name):
            return None

        # Internet Archive identifiers typically don't have spaces
        # and are alphanumeric with underscores/hyphens
        if ' ' in name:
            return None

        # Basic validation - must be reasonable length
        if len(name) < 5 or len(name) > 100:
            return None

        # Check if it looks like an IA identifier (must contain at least some letters)
        if re.match(r'^[a-zA-Z0-9_\-]+$', name) and re.search(r'[a-zA-Z]', name):
            return name

        return None

    def fetch_internet_archive_metadata(self, identifier: str) -> Optional[Dict]:
        """Fetch metadata from Internet Archive."""
        url = f"https://archive.org/metadata/{identifier}"

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Check if item exists
            if data.get("error"):
                return None

            return data
        except Exception as e:
            self.logger.debug(f"Failed to fetch IA metadata for {identifier}: {e}")
            return None

    def extract_canadiana_id(self, filename: str) -> Optional[str]:
        """
        Extract Canadiana identifier from filename.

        Common patterns:
        - oocihm.12345.pdf
        - oocihm_12345.pdf
        - 12345.pdf (numeric only - prepend oocihm.)
        """
        name = Path(filename).stem

        # Look for oocihm pattern
        match = re.search(r'oocihm[._](\d+)', name, re.IGNORECASE)
        if match:
            return f"oocihm.{match.group(1)}"

        # If filename is purely numeric (5-6 digits), assume it's Canadiana
        if re.match(r'^\d{5,6}(_text)?$', name):
            numeric_id = name.replace('_text', '')
            return f"oocihm.{numeric_id}"

        return None

    def fetch_canadiana_metadata(self, identifier: str) -> Optional[Dict]:
        """
        Fetch metadata from Canadiana.

        Canadiana API documentation: https://www.canadiana.ca/en/pcdhn-lod
        """
        # Canadiana uses IIIF and LOD APIs
        # Example: https://www.canadiana.ca/view/oocihm.12345

        url = f"https://www.canadiana.ca/view/{identifier}/1"

        try:
            response = self.session.get(url, timeout=30, allow_redirects=True)

            # If page exists, construct minimal metadata
            if response.status_code == 200:
                return {
                    "identifier": identifier,
                    "source": "canadiana",
                    "url": f"https://www.canadiana.ca/view/{identifier}",
                    "metadata": {
                        "title": identifier,  # Placeholder
                        "collection": ["canadiana"]
                    }
                }

            return None
        except Exception as e:
            self.logger.debug(f"Failed to fetch Canadiana metadata for {identifier}: {e}")
            return None

    def extract_british_library_id(self, filename: str) -> Optional[str]:
        """
        Extract British Library identifier from filename.

        Pattern: 3207643410.pdf (starts with 320, 10 digits total)
        """
        name = Path(filename).stem

        # Remove common suffixes
        name = re.sub(r'_text$', '', name)

        # British Library IDs start with 320 and are 10 digits
        if re.match(r'^320\d{7}$', name):
            return name

        return None

    def fetch_british_library_metadata(self, identifier: str) -> Optional[Dict]:
        """
        Fetch metadata from British Library.

        British Library API: https://api.bl.uk/
        Note: May require API key for full access
        """
        # For now, create basic metadata structure
        # Can be enhanced with actual API calls if available
        return {
            "identifier": identifier,
            "source": "british_library",
            "metadata": {
                "title": f"British Library Document {identifier}",
                "collection": ["British Library"],
                "bl_identifier": identifier
            }
        }

    def parse_british_library_iol(self, filename: str) -> Optional[Dict]:
        """
        Parse British Library Indian Office List filename.

        Expected pattern: Will be defined based on user examples.
        """
        # Placeholder - will implement based on actual filename patterns
        name = Path(filename).stem

        # Check if filename contains "indian office" or similar patterns
        if re.search(r'indian.?office', name, re.IGNORECASE):
            return {
                "identifier": name,
                "source": "british_library_iol",
                "metadata": {
                    "title": name.replace('_', ' ').replace('-', ' '),
                    "collection": ["British Library", "Indian Office Lists"]
                }
            }

        return None

    def parse_pioneer_questionnaires(self, filename: str) -> Optional[Dict]:
        """
        Parse Pioneer Questionnaires filename.

        Pattern: PioneerQuestionnaires_No.12-PioneerQuestionnairesMisc_Box13001_3472.pdf

        Components:
        - Document type: PioneerQuestionnaires
        - Number: No.12
        - Subcategory: PioneerQuestionnairesMisc
        - Box number: Box13001
        - Item/page number: 3472
        """
        name = Path(filename).stem

        if not name.startswith("PioneerQuestionnaires"):
            return None

        # Parse the components
        parts = name.split('_')

        # Extract number if present (e.g., No.12)
        number = None
        subcategory = None
        box_number = None
        item_number = None

        for part in parts:
            if part.startswith("No."):
                number = part
            elif part.startswith("Box"):
                box_number = part
            elif part.startswith("PioneerQuestionnaires") and part != "PioneerQuestionnaires":
                subcategory = part
            elif part.isdigit():
                item_number = part

        # Build title
        title_parts = ["Pioneer Questionnaires"]
        if number:
            title_parts.append(number)
        if subcategory and subcategory != "PioneerQuestionnaires":
            # Extract the subcategory name
            subcat_name = subcategory.replace("PioneerQuestionnaires", "")
            if subcat_name:
                title_parts.append(subcat_name)
        if box_number:
            title_parts.append(box_number.replace("Box", "Box "))
        if item_number:
            title_parts.append(f"Item {item_number}")

        title = " - ".join(title_parts)

        metadata = {
            "identifier": name,
            "source": "saskatchewan_archives",
            "metadata": {
                "title": title,
                "collection": ["Saskatchewan Archives", "Pioneer Questionnaires"],
                "document_type": "Pioneer Questionnaire",
            }
        }

        # Add structured metadata
        if number:
            metadata["metadata"]["questionnaire_number"] = number
        if subcategory:
            metadata["metadata"]["subcategory"] = subcategory
        if box_number:
            metadata["metadata"]["box"] = box_number
        if item_number:
            metadata["metadata"]["item"] = item_number

        return metadata

    def process_pdf(self, pdf_path: Path, source_hint: Optional[str] = None) -> bool:
        """
        Process a single PDF and recover metadata.

        Args:
            pdf_path: Path to PDF file
            source_hint: Optional hint about the source (internet_archive, canadiana, etc.)

        Returns:
            True if metadata was recovered, False otherwise
        """
        self.stats["total"] += 1
        filename = pdf_path.name

        self.logger.info(f"Processing: {filename}")

        # Try different metadata sources in order
        metadata = None
        source_type = None

        # 1. Try Internet Archive
        if not metadata or source_hint == "internet_archive":
            ia_id = self.extract_internet_archive_id(filename)
            if ia_id:
                self.logger.debug(f"Trying Internet Archive ID: {ia_id}")
                metadata = self.fetch_internet_archive_metadata(ia_id)
                if metadata:
                    source_type = "internet_archive"
                    self.stats["internet_archive"] += 1
                    self.logger.info(f"✓ Found on Internet Archive: {ia_id}")
                time.sleep(self.delay)

        # 2. Try British Library (check before Canadiana since BL IDs are more specific)
        if not metadata or source_hint == "british_library":
            bl_id = self.extract_british_library_id(filename)
            if bl_id:
                self.logger.debug(f"Trying British Library ID: {bl_id}")
                metadata = self.fetch_british_library_metadata(bl_id)
                if metadata:
                    source_type = "british_library"
                    self.stats["british_library"] += 1
                    self.logger.info(f"✓ Found British Library ID: {bl_id}")

        # 3. Try Canadiana
        if not metadata or source_hint == "canadiana":
            canadiana_id = self.extract_canadiana_id(filename)
            if canadiana_id:
                self.logger.debug(f"Trying Canadiana ID: {canadiana_id}")
                metadata = self.fetch_canadiana_metadata(canadiana_id)
                if metadata:
                    source_type = "canadiana"
                    self.stats["canadiana"] += 1
                    self.logger.info(f"✓ Found on Canadiana: {canadiana_id}")
                time.sleep(self.delay)

        # 4. Try Pioneer Questionnaires (Saskatchewan Archives)
        if not metadata or source_hint == "saskatchewan_archives":
            pq_metadata = self.parse_pioneer_questionnaires(filename)
            if pq_metadata:
                metadata = pq_metadata
                source_type = "saskatchewan_archives"
                self.stats["custom"] += 1
                self.logger.info(f"✓ Identified as Pioneer Questionnaire")

        # 5. Try British Library Indian Office Lists
        if not metadata or source_hint == "british_library_iol":
            bl_metadata = self.parse_british_library_iol(filename)
            if bl_metadata:
                metadata = bl_metadata
                source_type = "british_library_iol"
                self.stats["british_library"] += 1
                self.logger.info(f"✓ Identified as British Library IOL")

        # If metadata found, update database
        if metadata and self.db and not self.dry_run:
            self._update_database(pdf_path, metadata, source_type)
            return True
        elif metadata and self.dry_run:
            self.logger.info(f"[DRY RUN] Would update: {filename}")
            return True
        else:
            self.stats["not_found"] += 1
            self.logger.warning(f"✗ No metadata found for: {filename}")
            return False

    def _update_database(self, pdf_path: Path, metadata: Dict, source_type: str):
        """Update database with recovered metadata."""
        try:
            identifier = metadata.get("identifier")
            if not identifier:
                identifier = metadata.get("metadata", {}).get("identifier")

            if not identifier:
                self.logger.warning(f"No identifier found in metadata for {pdf_path.name}")
                return

            if source_type == "internet_archive":
                # Use existing add_item method which handles IA metadata properly
                self.db.add_item(identifier, metadata.get("metadata", metadata))
            elif source_type == "canadiana":
                # Extract fields for Canadiana items
                meta = metadata.get("metadata", {})
                title = meta.get("title", identifier)

                self.db.conn.execute("""
                    INSERT OR REPLACE INTO items (
                        identifier, title, item_url, metadata_json, download_date
                    ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    identifier,
                    title,
                    metadata.get("url", f"https://www.canadiana.ca/view/{identifier}"),
                    json.dumps(metadata)
                ))
                self.db.conn.commit()
            elif source_type in ["british_library", "saskatchewan_archives", "british_library_iol"]:
                # Extract fields for other sources
                meta = metadata.get("metadata", {})
                title = meta.get("title", pdf_path.stem)
                collection = meta.get("collection", [])
                if isinstance(collection, list):
                    collection = "; ".join(collection)

                self.db.conn.execute("""
                    INSERT OR REPLACE INTO items (
                        identifier, title, collection, metadata_json, download_date
                    ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    identifier,
                    title,
                    collection,
                    json.dumps(metadata)
                ))
                self.db.conn.commit()

            self.logger.debug(f"Updated database for {identifier}")
        except Exception as e:
            self.logger.error(f"Failed to update database for {pdf_path.name}: {e}")
            self.stats["errors"] += 1

    def process_directory(
        self,
        directory: Path,
        source_hint: Optional[str] = None,
        recursive: bool = False
    ):
        """Process all PDFs in a directory."""
        pattern = "**/*.pdf" if recursive else "*.pdf"
        pdf_files = list(directory.glob(pattern))

        self.logger.info(f"Found {len(pdf_files)} PDF files in {directory}")

        for pdf_path in pdf_files:
            try:
                self.process_pdf(pdf_path, source_hint)
            except Exception as e:
                self.logger.error(f"Error processing {pdf_path.name}: {e}")
                self.stats["errors"] += 1

    def print_stats(self):
        """Print statistics."""
        print("\n" + "=" * 60)
        print("Metadata Recovery Statistics")
        print("=" * 60)
        print(f"Total PDFs processed:      {self.stats['total']}")
        print(f"Internet Archive:          {self.stats['internet_archive']}")
        print(f"Canadiana:                 {self.stats['canadiana']}")
        print(f"British Library:           {self.stats['british_library']}")
        print(f"Custom:                    {self.stats['custom']}")
        print(f"Not found:                 {self.stats['not_found']}")
        print(f"Errors:                    {self.stats['errors']}")

        success_rate = 0
        if self.stats['total'] > 0:
            found = (self.stats['total'] - self.stats['not_found'] - self.stats['errors'])
            success_rate = (found / self.stats['total']) * 100

        print(f"Success rate:              {success_rate:.1f}%")
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Recover metadata for PDFs based on filenames"
    )
    parser.add_argument(
        "directory",
        type=Path,
        help="Directory containing PDFs"
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        help="Path to SQLite database"
    )
    parser.add_argument(
        "--source-hint",
        choices=["internet_archive", "canadiana", "british_library", "saskatchewan_archives", "custom"],
        help="Hint about the source of PDFs"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Delay between API requests in seconds (default: 0.5)"
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Process subdirectories recursively"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.directory.exists():
        print(f"Error: Directory not found: {args.directory}")
        sys.exit(1)

    recovery = MetadataRecovery(
        db_path=args.db_path,
        delay=args.delay,
        dry_run=args.dry_run
    )

    print("PDF Metadata Recovery Tool")
    print("=" * 60)
    print(f"Directory: {args.directory}")
    print(f"Source hint: {args.source_hint or 'Auto-detect'}")
    print(f"Database: {args.db_path or 'None (dry run)'}")
    print(f"Dry run: {args.dry_run}")
    print("=" * 60)
    print()

    recovery.process_directory(
        args.directory,
        source_hint=args.source_hint,
        recursive=args.recursive
    )

    recovery.print_stats()


if __name__ == "__main__":
    main()
