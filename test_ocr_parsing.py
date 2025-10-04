#!/usr/bin/env python3
"""
Quick test to verify olmOCR JSONL parsing works correctly.
"""

import json
from pathlib import Path

def load_ocr_jsonl(filepath: Path):
    """Load olmOCR JSONL and show what we extract."""
    records = []

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    print(f"Total records: {len(records)}")
    print()

    # Show first record structure
    if records:
        first = records[0]
        print("First record keys:", list(first.keys()))
        print()
        print("Metadata:", json.dumps(first.get('metadata', {}), indent=2))
        print()
        print("Text preview (first 500 chars):")
        print(first.get('text', '')[:500])
        print()

    # Combine all text
    combined_text = []
    for record in records:
        if 'text' in record and record['text']:
            combined_text.append(record['text'])

    full_text = '\n\n---\n\n'.join(combined_text)

    print(f"Combined text length: {len(full_text):,} characters")
    print(f"Number of text chunks: {len(combined_text)}")

    if records and 'metadata' in records[0]:
        meta = records[0]['metadata']
        print()
        print(f"PDF pages: {meta.get('pdf-total-pages', 'unknown')}")
        print(f"olmOCR version: {meta.get('olmocr-version', 'unknown')}")
        print(f"Input tokens: {meta.get('total-input-tokens', 0):,}")
        print(f"Output tokens: {meta.get('total-output-tokens', 0):,}")


if __name__ == "__main__":
    test_file = Path("/Users/jimclifford/Library/CloudStorage/GoogleDrive-cljim22@gmail.com/My Drive/InternetArchive/output_0940d876ef0a8f0caced00220d4232c2a77489bf.jsonl")

    if test_file.exists():
        print(f"Testing OCR parsing on: {test_file.name}")
        print("=" * 70)
        print()
        load_ocr_jsonl(test_file)
    else:
        print(f"File not found: {test_file}")
