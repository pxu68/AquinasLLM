"""Operator CLI: python -m app.ingestion.cli ingest ..."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.db.session import SessionLocal
from app.ingestion.pipeline import IngestRequest, IngestionPipeline


def main() -> None:
    parser = argparse.ArgumentParser(prog="aquinas-ingest")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Ingest a source file")
    ingest.add_argument("--source", type=Path, required=True)
    ingest.add_argument("--parser", choices=["summa", "treatise"], required=True)
    ingest.add_argument("--author", required=True, help="Canonical author name")
    ingest.add_argument("--author-display", default=None)
    ingest.add_argument("--work-title", required=True)
    ingest.add_argument("--work-code", required=True)
    ingest.add_argument("--genre", required=True)
    ingest.add_argument("--original-language", default="la")
    ingest.add_argument("--edition-label", required=True)
    ingest.add_argument("--edition-language", required=True)
    ingest.add_argument("--corpus-version", default="v0.1.0")
    ingest.add_argument("--translation", action="store_true")
    ingest.add_argument("--force", action="store_true")

    args = parser.parse_args()
    if args.command == "ingest":
        session = SessionLocal()
        try:
            pipeline = IngestionPipeline(session)
            result = pipeline.ingest(
                IngestRequest(
                    source_path=args.source,
                    parser_key=args.parser,
                    author_canonical_name=args.author,
                    author_display_name=args.author_display or args.author,
                    work_title=args.work_title,
                    work_short_code=args.work_code,
                    work_genre=args.genre,
                    original_language=args.original_language,
                    edition_label=args.edition_label,
                    edition_language=args.edition_language,
                    corpus_version=args.corpus_version,
                    is_translation=args.translation,
                    force=args.force,
                )
            )
            print(result.message)
            if result.ingestion_run_id:
                print(f"run_id={result.ingestion_run_id}")
        finally:
            session.close()


if __name__ == "__main__":
    main()
