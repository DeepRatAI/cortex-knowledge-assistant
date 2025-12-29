"""Ingestion script for the FCE-IUC university demo corpus.

Ingests all synthetic documentation from the documentacion_sintetica directory
into Qdrant, preserving document structure and metadata.

This is a demo-specific script that:
- Reads all .md files from documentacion_sintetica/documentos/
- Reads all PDF files from documentacion_sintetica/referencias_reales/libros/
- Assigns appropriate metadata based on folder structure
- Uses the existing ingestion infrastructure
- Does NOT modify or replace banking corpus (uses same collection by default)

Usage:
    python -m cortex_ka.demos.ingest_university_corpus [--clean]

Options:
    --clean     Remove existing documents before ingestion
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Generator, List

# Add project root to path if running as script
if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    sys.path.insert(0, str(project_root / "src"))

from qdrant_client import QdrantClient

from cortex_ka.config import settings
from cortex_ka.logging import logger
from cortex_ka.scripts.ingest_docs import IngestDoc, upsert_documents
from cortex_ka.scripts.ingest_pdfs import PdfDocument, load_pdf_documents

# =============================================================================
# CORPUS CONFIGURATION
# =============================================================================

# Base path for university documentation (markdown files)
CORPUS_BASE = Path("documentacion_sintetica/documentos")

# Path for reference books (PDFs)
BOOKS_BASE = Path("documentacion_sintetica/referencias_reales/libros")

# Mapping of folder names to semantic categories
CATEGORY_MAP = {
    "institucional": "institutional",
    "carreras": "academic_programs",
    "materias": "courses",
    "extension": "extension_courses",
    "posgrados": "postgraduate",
    "noticias": "news",
    "servicios": "services",
    "financiero": "financial",
    "calendario": "calendar",
    "datos_demo": "demo_data",
}


def _extract_metadata(file_path: Path, content: str) -> dict:
    """Extract metadata from file path and content.

    Creates structured metadata for better retrieval and filtering.
    """
    # Get category from parent folder
    parent = file_path.parent.name
    category = CATEGORY_MAP.get(parent, parent)

    # Try to extract title from markdown heading
    title = file_path.stem.replace("_", " ").replace("-", " ").title()
    lines = content.split("\n")
    for line in lines[:10]:  # Check first 10 lines for heading
        if line.startswith("# "):
            title = line[2:].strip()
            break

    return {
        "category": category,
        "title": title,
        "folder": parent,
        "filename": file_path.name,
        "demo_domain": "university",
        "institution": "fce-iuc",
    }


def iter_corpus_docs(base_path: Path) -> Generator[IngestDoc, None, None]:
    """Iterate over all markdown documents in the corpus.

    Yields IngestDoc objects for each .md file found recursively.
    """
    if not base_path.exists():
        logger.error("corpus_path_not_found", path=str(base_path))
        return

    for folder in sorted(base_path.iterdir()):
        if not folder.is_dir():
            continue

        category = folder.name
        for md_file in sorted(folder.glob("*.md")):
            try:
                content = md_file.read_text(encoding="utf-8")
                if not content.strip():
                    continue

                # Create unique doc ID
                doc_id = f"fce-iuc_{category}_{md_file.stem}"

                # Extract metadata
                metadata = _extract_metadata(md_file, content)

                yield IngestDoc(
                    doc_id=doc_id,
                    content=content,
                    source="fce_iuc_demo",
                    metadata=metadata,
                    filename=str(md_file.relative_to(base_path)),
                )

            except Exception as e:
                logger.warning(
                    "corpus_file_read_error",
                    file=str(md_file),
                    error=str(e),
                )


def iter_book_docs(base_path: Path) -> Generator[IngestDoc, None, None]:
    """Iterate over all PDF books in the references directory.

    Yields IngestDoc objects for each PDF file found.
    """
    if not base_path.exists():
        logger.warning("books_path_not_found", path=str(base_path))
        return

    pdf_files = list(base_path.glob("*.pdf"))
    if not pdf_files:
        logger.warning("no_pdf_books_found", path=str(base_path))
        return

    logger.info("books_discovered", count=len(pdf_files))

    for pdf_doc in load_pdf_documents(pdf_files):
        # Create human-readable title from filename
        title = pdf_doc.doc_id.replace("_", " ").replace("-", " ").title()

        # Create unique doc ID for the book
        doc_id = f"fce-iuc_libro_{pdf_doc.doc_id}"

        metadata = {
            "category": "reference_book",
            "title": title,
            "folder": "libros",
            "filename": pdf_doc.path.name,
            "demo_domain": "university",
            "institution": "fce-iuc",
            "doc_type": "textbook",
        }

        yield IngestDoc(
            doc_id=doc_id,
            content=pdf_doc.content,
            source="fce_iuc_demo",
            metadata=metadata,
            filename=pdf_doc.path.name,
        )


def count_corpus_files(base_path: Path) -> tuple[int, int]:
    """Count files and folders in the corpus.

    Returns:
        Tuple of (file_count, folder_count)
    """
    files = 0
    folders = 0

    if not base_path.exists():
        return 0, 0

    for folder in base_path.iterdir():
        if folder.is_dir():
            folders += 1
            files += len(list(folder.glob("*.md")))

    return files, folders


def ingest_university_corpus(
    base_path: Path | str = CORPUS_BASE,
    books_path: Path | str | None = BOOKS_BASE,
    clean: bool = False,
) -> int:
    """Ingest the university demo corpus into Qdrant.

    Args:
        base_path: Path to the corpus base directory (markdown docs)
        books_path: Path to the books directory (PDFs), or None to skip
        clean: If True, remove existing fce_iuc documents before ingestion

    Returns:
        Number of points ingested
    """
    base_path = Path(base_path)

    # Stats for markdown docs
    file_count, folder_count = count_corpus_files(base_path)
    logger.info(
        "university_corpus_ingest_start",
        base_path=str(base_path),
        folders=folder_count,
        files=file_count,
    )

    # Optional cleanup of existing university documents
    if clean:
        try:
            from qdrant_client.http import models as qmodels

            client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key or None,
            )
            # Delete points with source="fce_iuc_demo"
            client.delete(
                collection_name=settings.qdrant_collection_docs,
                points_selector=qmodels.FilterSelector(
                    filter=qmodels.Filter(
                        must=[
                            qmodels.FieldCondition(
                                key="source",
                                match=qmodels.MatchValue(value="fce_iuc_demo"),
                            )
                        ]
                    )
                ),
            )
            logger.info("university_corpus_cleaned")
        except Exception as e:
            logger.warning("university_corpus_cleanup_failed", error=str(e))

    # Collect all documents
    all_docs: List[IngestDoc] = []

    # 1. Ingest markdown documents
    md_docs = list(iter_corpus_docs(base_path))
    if md_docs:
        logger.info("university_corpus_md_docs", count=len(md_docs))
        all_docs.extend(md_docs)
    else:
        logger.warning("university_corpus_no_md_docs")

    # 2. Ingest PDF books if path provided
    if books_path:
        books_path = Path(books_path)
        # Resolve relative to project root if needed
        if not books_path.exists():
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            books_path = project_root / books_path

        if books_path.exists():
            book_docs = list(iter_book_docs(books_path))
            if book_docs:
                logger.info("university_corpus_book_docs", count=len(book_docs))
                all_docs.extend(book_docs)
            else:
                logger.warning("university_corpus_no_book_docs")
        else:
            logger.warning("university_corpus_books_path_not_found", path=str(books_path))

    if not all_docs:
        logger.warning("university_corpus_no_docs_parsed")
        return 0

    logger.info("university_corpus_docs_prepared", total=len(all_docs))

    total = upsert_documents(all_docs)

    logger.info(
        "university_corpus_ingest_complete",
        documents=len(all_docs),
        points=total,
    )

    return total


def main() -> None:
    """CLI entry point for university corpus ingestion."""
    parser = argparse.ArgumentParser(description="Ingest FCE-IUC university demo corpus into Qdrant")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove existing university documents before ingestion",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=str(CORPUS_BASE),
        help="Path to corpus base directory (markdown docs)",
    )
    parser.add_argument(
        "--books-path",
        type=str,
        default=str(BOOKS_BASE),
        help="Path to books directory (PDFs)",
    )
    parser.add_argument(
        "--no-books",
        action="store_true",
        help="Skip ingestion of PDF books",
    )
    args = parser.parse_args()

    print("🎓 FCE-IUC Corpus Ingestion")
    print(f"   Docs path: {args.path}")
    print(f"   Books path: {args.books_path}")
    print(f"   Include books: {not args.no_books}")
    print(f"   Clean mode: {args.clean}")
    print()

    # Ensure we're in the project root
    project_root = Path(__file__).resolve().parent.parent.parent.parent

    # Resolve docs path
    docs_path = Path(args.path)
    if not docs_path.exists():
        alt_path = project_root / args.path
        if alt_path.exists():
            docs_path = alt_path
        else:
            print(f"❌ Corpus path not found: {args.path}")
            sys.exit(1)

    # Resolve books path
    books_path = None
    if not args.no_books:
        books_path = Path(args.books_path)
        if not books_path.exists():
            alt_path = project_root / args.books_path
            if alt_path.exists():
                books_path = alt_path
            else:
                print(f"⚠️  Books path not found: {args.books_path} (will skip books)")
                books_path = None

    total = ingest_university_corpus(docs_path, books_path=books_path, clean=args.clean)

    if total > 0:
        print(f"✅ Ingested {total} points into Qdrant")
    else:
        print("⚠️  No documents were ingested")


if __name__ == "__main__":
    main()
