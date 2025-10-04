#!/usr/bin/env python3
"""
Test metadata recovery on sample files to verify it works correctly.
"""

from pathlib import Path
from recover_metadata import MetadataRecovery

# Test files representing each pattern
test_files = [
    # Internet Archive - India collection
    ("acataloguelibra00brangoog.pdf", None),  # Should extract: acataloguelibra00brangoog
    ("b21781941.pdf", None),  # Should extract: b21781941

    # Canadiana - Main collection (numeric)
    ("10047.pdf", "canadiana"),
    ("106223.pdf", "canadiana"),

    # British Library - starts with 320
    ("3207643410.pdf", "british_library"),

    # Pioneer Questionnaires
    ("PioneerQuestionnaires_No.12-PioneerQuestionnairesMisc_Box13001_3472.pdf", "saskatchewan_archives"),
]

print("=" * 70)
print("Metadata Recovery Test")
print("=" * 70)
print()

# Create recovery instance in dry-run mode (no database updates)
recovery = MetadataRecovery(db_path=None, delay=0.5, dry_run=True)

for filename, source_hint in test_files:
    print(f"\nTesting: {filename}")
    print(f"Source hint: {source_hint or 'auto-detect'}")
    print("-" * 70)

    # Test identifier extraction
    pdf_path = Path(filename)

    # Try Internet Archive
    ia_id = recovery.extract_internet_archive_id(filename)
    if ia_id:
        print(f"  ✓ Internet Archive ID: {ia_id}")
        metadata = recovery.fetch_internet_archive_metadata(ia_id)
        if metadata:
            print(f"    - Title: {metadata.get('metadata', {}).get('title', 'N/A')}")
            print(f"    - Year: {metadata.get('metadata', {}).get('year', 'N/A')}")
            print(f"    - Creator: {metadata.get('metadata', {}).get('creator', 'N/A')}")
        else:
            print(f"    ✗ No metadata found on Internet Archive")

    # Try Canadiana
    canadiana_id = recovery.extract_canadiana_id(filename)
    if canadiana_id:
        print(f"  ✓ Canadiana ID: {canadiana_id}")
        metadata = recovery.fetch_canadiana_metadata(canadiana_id)
        if metadata:
            print(f"    - Source: {metadata.get('source')}")
            print(f"    - URL: {metadata.get('url')}")
        else:
            print(f"    ✗ No metadata found on Canadiana")

    # Try British Library
    bl_id = recovery.extract_british_library_id(filename)
    if bl_id:
        print(f"  ✓ British Library ID: {bl_id}")
        metadata = recovery.fetch_british_library_metadata(bl_id)
        if metadata:
            print(f"    - Source: {metadata.get('source')}")
            print(f"    - Identifier: {metadata.get('identifier')}")

    # Try Pioneer Questionnaires
    pq_metadata = recovery.parse_pioneer_questionnaires(filename)
    if pq_metadata:
        print(f"  ✓ Pioneer Questionnaire parsed")
        print(f"    - Title: {pq_metadata['metadata']['title']}")
        print(f"    - Box: {pq_metadata['metadata'].get('box', 'N/A')}")
        print(f"    - Item: {pq_metadata['metadata'].get('item', 'N/A')}")

    if not any([ia_id, canadiana_id, bl_id, pq_metadata]):
        print(f"  ✗ No pattern matched for this filename")

print()
print("=" * 70)
print("Test Complete")
print("=" * 70)
