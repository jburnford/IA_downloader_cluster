#!/usr/bin/env python3
"""
Deduplicate PDF files from Internet Archive downloads.

Identifies and removes duplicate PDFs from the same item, keeping only
the best quality version based on size and naming conventions.
"""

import argparse
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


class PDFDeduplicator:
    def __init__(self, pdf_dir: str, dry_run: bool = True, log_file: str = None):
        self.pdf_dir = Path(pdf_dir)
        self.dry_run = dry_run
        self.log_file = Path(log_file) if log_file else None
        self.duplicates_found = 0
        self.space_recovered = 0

    def extract_identifier(self, filename: str) -> str:
        """Extract Internet Archive identifier from filename."""
        # IA identifiers are typically the base name before extensions like _bw, _text, etc.
        name = filename.replace(".pdf", "")

        # Remove common IA suffixes
        for suffix in ["_bw", "_text", "_jp2", "_djvu"]:
            if name.endswith(suffix):
                return name[: -len(suffix)]

        return name

    def calculate_checksum(self, filepath: Path, block_size: int = 65536) -> str:
        """Calculate SHA256 checksum of a file."""
        sha256 = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                for block in iter(lambda: f.read(block_size), b""):
                    sha256.update(block)
            return sha256.hexdigest()
        except Exception as e:
            print(f"Error calculating checksum for {filepath}: {e}")
            return ""

    def score_pdf(self, filepath: Path) -> Tuple[int, int, int]:
        """
        Score a PDF file for quality selection.
        Returns tuple: (color_score, avoid_text_score, size)
        Higher scores are better.
        """
        name_lower = filepath.name.lower()
        size = filepath.stat().st_size

        # Prefer color over black and white
        color_score = 0 if "_bw" in name_lower else 1

        # Avoid _text versions (usually just OCR text, not full PDF)
        text_score = 0 if "_text" in name_lower else 1

        return (color_score, text_score, size)

    def group_pdfs_by_identifier(self) -> Dict[str, List[Path]]:
        """Group PDF files by their Internet Archive identifier."""
        groups = defaultdict(list)

        if not self.pdf_dir.exists():
            print(f"Directory not found: {self.pdf_dir}")
            return groups

        for pdf_file in self.pdf_dir.glob("*.pdf"):
            if pdf_file.is_file():
                identifier = self.extract_identifier(pdf_file.name)
                groups[identifier].append(pdf_file)

        return groups

    def find_duplicates(self, files: List[Path]) -> Tuple[Path, List[Path]]:
        """
        Identify the best file to keep and duplicates to remove.
        Returns: (file_to_keep, files_to_remove)
        """
        if len(files) <= 1:
            return (files[0] if files else None, [])

        # Sort files by quality score (best first)
        scored_files = [(self.score_pdf(f), f) for f in files]
        scored_files.sort(reverse=True)

        best_file = scored_files[0][1]
        best_size = scored_files[0][0][2]

        files_to_remove = []

        # Check remaining files
        for score, candidate in scored_files[1:]:
            candidate_size = score[2]

            # If files are within 10% size, consider them duplicates
            if best_size > 0:
                size_diff_percent = abs(candidate_size - best_size) / best_size * 100
                if size_diff_percent < 10:
                    files_to_remove.append(candidate)
                    continue

            # Also check if files are identical by checksum
            if candidate_size == best_size:
                best_checksum = self.calculate_checksum(best_file)
                candidate_checksum = self.calculate_checksum(candidate)
                if best_checksum and best_checksum == candidate_checksum:
                    files_to_remove.append(candidate)

        return (best_file, files_to_remove)

    def format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"

    def deduplicate(self) -> Dict[str, any]:
        """Run deduplication process."""
        print(f"Scanning directory: {self.pdf_dir}")
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE - WILL DELETE FILES'}")
        print("-" * 70)

        groups = self.group_pdfs_by_identifier()

        # Filter to only groups with multiple files
        duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}

        print(f"Found {len(groups)} unique identifiers")
        print(f"Found {len(duplicate_groups)} identifiers with multiple PDFs")
        print()

        results = {
            "duplicates_removed": [],
            "files_kept": [],
            "space_saved": 0,
            "errors": [],
        }

        for identifier, files in duplicate_groups.items():
            print(f"Processing: {identifier} ({len(files)} files)")

            best_file, duplicates = self.find_duplicates(files)

            if not duplicates:
                print(f"  No duplicates found (files differ significantly)")
                continue

            print(f"  Keeping: {best_file.name} ({self.format_size(best_file.stat().st_size)})")

            for dup in duplicates:
                dup_size = dup.stat().st_size
                print(
                    f"  {'Would remove' if self.dry_run else 'Removing'}: "
                    f"{dup.name} ({self.format_size(dup_size)})"
                )

                results["duplicates_removed"].append(str(dup))
                results["space_saved"] += dup_size
                self.duplicates_found += 1
                self.space_recovered += dup_size

                if not self.dry_run:
                    try:
                        dup.unlink()
                    except Exception as e:
                        error_msg = f"Failed to remove {dup}: {e}"
                        print(f"  ERROR: {error_msg}")
                        results["errors"].append(error_msg)

            results["files_kept"].append(str(best_file))
            print()

        return results

    def save_report(self, results: Dict[str, any]):
        """Save deduplication report to file."""
        if not self.log_file:
            return

        report = {
            "timestamp": str(Path.ctime(self.pdf_dir)),
            "directory": str(self.pdf_dir),
            "dry_run": self.dry_run,
            "summary": {
                "duplicates_found": len(results["duplicates_removed"]),
                "files_kept": len(results["files_kept"]),
                "space_saved_bytes": results["space_saved"],
                "space_saved_human": self.format_size(results["space_saved"]),
                "errors": len(results["errors"]),
            },
            "details": results,
        }

        try:
            with open(self.log_file, "w") as f:
                json.dump(report, f, indent=2)
            print(f"Report saved to: {self.log_file}")
        except Exception as e:
            print(f"Failed to save report: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Deduplicate Internet Archive PDF downloads"
    )
    parser.add_argument(
        "pdf_dir",
        help="Directory containing PDF files to deduplicate",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Actually delete duplicates (default is dry-run)",
    )
    parser.add_argument(
        "--report",
        default="deduplication_report.json",
        help="Save deduplication report to file",
    )

    args = parser.parse_args()

    if not Path(args.pdf_dir).exists():
        print(f"Error: Directory not found: {args.pdf_dir}")
        sys.exit(1)

    deduplicator = PDFDeduplicator(
        pdf_dir=args.pdf_dir,
        dry_run=not args.live,
        log_file=args.report if args.live or args.report != "deduplication_report.json" else None,
    )

    print("PDF Deduplication Tool for Internet Archive Downloads")
    print("=" * 70)
    print()

    results = deduplicator.deduplicate()

    print("=" * 70)
    print("Summary:")
    print(f"  Duplicates found: {len(results['duplicates_removed'])}")
    print(f"  Space that would be saved: {deduplicator.format_size(results['space_saved'])}")

    if results["errors"]:
        print(f"  Errors: {len(results['errors'])}")

    if deduplicator.dry_run:
        print()
        print("This was a DRY RUN. No files were deleted.")
        print("Run with --live to actually remove duplicates.")
    else:
        print()
        print("Deduplication complete!")

    if args.report:
        deduplicator.save_report(results)


if __name__ == "__main__":
    main()
