#!/usr/bin/env python3
# CLI compatibility wrapper for Pawdf release metadata generation.

from pawdf.release_manifest import generate_release_metadata, main

__all__ = ["generate_release_metadata", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
