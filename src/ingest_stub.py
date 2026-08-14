"""Superseded by `src/ingest.py`, which performs real fetches. Kept only as the
original scaffold reference; safe to delete once nothing points at it.
"""
import os
import sys

CFBD_API_KEY = os.getenv("CFBD_API_KEY")


def main():
    if not CFBD_API_KEY:
        print("CFBD_API_KEY not found in environment. Create a .env with CFBD_API_KEY.")
        sys.exit(1)

    # Small smoke test: call the CFBD ping or status endpoint if available.
    # This is a stub — implement real ingestion tasks per pipeline design.
    print("Stub ingestion would run here. API key found.")


if __name__ == "__main__":
    main()
