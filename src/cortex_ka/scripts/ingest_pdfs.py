"""Utilities for ingesting PDF documents into the RAG corpus.

At this stage we focus on **robust extraction** from local PDF files,
keeping it orthogonal to the existing JSONL banking corpus pipeline.

The goal is to expose a small, well‑typed API that higher‑level
ingestion code can call to obtain plain‑text documents ready for
chunking and embedding, without coupling PDF parsing logic to Qdrant
or the domain models.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List

from pypdf import PdfReader

from cortex_ka.logging import logger
from cortex_ka.scripts.ingest_docs import IngestDoc, upsert_documents


@dataclass(frozen=True)
class PdfDocument:
    """Simple representation of a PDF turned into a text document.

    Attributes:
        doc_id: Stable identifier derived from the filename (without suffix).
        source: Short source label, typically the stem of the file.
        content: Concatenated text of all pages.
        path: Absolute path to the original PDF file.
    """

    doc_id: str
    source: str
    content: str
    path: Path


def _extract_text_from_pdf(path: Path) -> str:
    """Extract Unicode text from a single PDF.

    This function is deliberately conservative: if anything goes wrong
    during parsing, we log a warning and return an empty string instead
    of propagating parser‑specific exceptions to the caller.
    """

    try:
        reader = PdfReader(path)
    except Exception as exc:  # pragma: no cover - defensive path
        logger.warning("pdf_open_failed", path=str(path), error=str(exc))
        return ""

    texts: List[str] = []
    for idx, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text() or ""
        except Exception as exc:  # pragma: no cover - defensive path
            logger.warning(
                "pdf_page_extract_failed",
                path=str(path),
                page_index=idx,
                error=str(exc),
            )
            continue
        page_text = page_text.strip()
        if page_text:
            texts.append(page_text)

    return "\n\n".join(texts)


def discover_pdfs(root: str | Path) -> List[Path]:
    """Recursively discover PDF files under ``root``.

    Returns absolute paths sorted for deterministic ordering.
    """

    base = Path(root).expanduser().resolve()
    pdfs = sorted(p for p in base.rglob("*.pdf") if p.is_file())
    logger.info("pdf_discovered", root=str(base), count=len(pdfs))
    return pdfs


def load_pdf_documents(paths: Iterable[str | Path]) -> Iterator[PdfDocument]:
    """Yield :class:`PdfDocument` instances for the given PDF paths.

    Empty or unreadable PDFs are skipped with a warning.
    """

    for raw in paths:
        path = Path(raw).expanduser().resolve()
        if not path.is_file():
            logger.warning("pdf_missing", path=str(path))
            continue
        content = _extract_text_from_pdf(path)
        if not content:
            logger.warning("pdf_empty_content", path=str(path))
            continue
        # Normalize the stem: strip whitespace and convert to lowercase
        # for consistent case-insensitive filename matching in queries
        stem = path.stem.strip().lower()
        yield PdfDocument(doc_id=stem, source=stem, content=content, path=path)


def load_banking_pdfs_default() -> List[PdfDocument]:
    """Convenience helper for the attached synthetic banking PDFs.

    Looks for a ``documentacion`` directory at the project root or in /app/data,
    which is where the user attached the sample banking PDFs (e.g.
    ``atencion_al_cliente.pdf``, ``tarjetas_de_credito.pdf``, etc.).

    This function searches recursively, including subdirectories like
    ``documentacion/publica/`` where admin-uploaded documents are stored.
    """
    import os

    # Check multiple possible locations for the documentacion directory
    possible_roots = [
        Path(os.environ.get("CKA_DATA_DIR", "/app/data")) / "documentacion",
        Path("documentacion"),
        Path("/app/data/documentacion"),
    ]

    all_pdfs: List[Path] = []
    for root in possible_roots:
        if root.exists():
            pdf_paths = sorted(p for p in root.rglob("*.pdf") if p.is_file())
            all_pdfs.extend(pdf_paths)
            logger.info("pdf_load_from_root", root=str(root), count=len(pdf_paths))

    if not all_pdfs:
        logger.warning("pdf_root_missing", roots=[str(r) for r in possible_roots])
        return []

    # Deduplicate by absolute path
    unique_pdfs = list({p.resolve(): p for p in all_pdfs}.values())
    logger.info("pdf_load_default", total_count=len(unique_pdfs))
    return list(load_pdf_documents(unique_pdfs))


def load_text_documents_default() -> List[PdfDocument]:
    """Load plain text documents (.txt, .md) from the documentacion directory.

    This complements load_banking_pdfs_default() by handling text-based
    documentation files that admins may upload via the web interface.

    Returns PdfDocument instances (reusing the dataclass) for consistency
    with the existing ingestion pipeline.
    """
    import os

    # Check multiple possible locations
    possible_roots = [
        Path(os.environ.get("CKA_DATA_DIR", "/app/data")) / "documentacion",
        Path("documentacion"),
        Path("/app/data/documentacion"),
    ]

    text_docs: List[PdfDocument] = []

    for root in possible_roots:
        if not root.exists():
            continue

        # Find all .txt and .md files recursively
        for ext in ("*.txt", "*.md"):
            for path in sorted(root.rglob(ext)):
                if not path.is_file():
                    continue
                try:
                    content = path.read_text(encoding="utf-8", errors="replace")
                    content = content.strip()
                    if not content:
                        logger.warning("text_doc_empty", path=str(path))
                        continue
                    stem = path.stem
                    text_docs.append(PdfDocument(doc_id=stem, source=stem, content=content, path=path))
                except Exception as exc:
                    logger.warning("text_doc_read_failed", path=str(path), error=str(exc))
                    continue

    # Deduplicate by doc_id
    seen_ids = set()
    unique_docs = []
    for doc in text_docs:
        if doc.doc_id not in seen_ids:
            seen_ids.add(doc.doc_id)
            unique_docs.append(doc)

    if unique_docs:
        logger.info("text_docs_loaded", count=len(unique_docs))
    return unique_docs


def ingest_banking_pdfs_into_qdrant() -> int:
    """Ingest public documentation (PDFs, TXT, MD) into Qdrant.

    Security & data-handling notes:

    * The attached documents are *public* documentation (manuales,
        guias, terminos y condiciones). No datos personales de clientes.
    * En consecuencia, no se adjunta ningun bloque de metadata con
        `metadata.info_personal.id_cliente` y no se genera PII asociada a
        personas.
    * Cada documento se indexa independientemente identificado por
        su nombre de archivo (sin extension), lo que evita mezclar
        accidentalmente estos contenidos con el corpus bancario
        personalizado por cliente.
    * Supports PDF, TXT, and MD files from documentacion/ and subdirectories.
    """

    # Load PDFs
    pdf_docs = load_banking_pdfs_default()

    # Load text documents (TXT, MD)
    text_docs = load_text_documents_default()

    # Combine all documents
    all_docs = pdf_docs + text_docs

    if not all_docs:
        logger.warning("doc_ingest_no_documents_found")
        return 0

    # Convert documents into the generic IngestDoc shape expected by the
    # existing ingestion pipeline. We deliberately omit metadata to avoid
    # introducir identificadores personales o campos sensibles aqui.
    ingest_docs: List[IngestDoc] = []
    for d in all_docs:
        # Determine source type based on file extension
        ext = d.path.suffix.lower()
        if ext == ".pdf":
            source_type = "documentacion_publica_pdf"
        elif ext == ".md":
            source_type = "documentacion_publica_md"
        else:
            source_type = "documentacion_publica_txt"

        # Extract clean filename for better context in search results
        # Remove hash prefix if present (e.g., "5c21596e_libro_ortodoncia" -> "libro_ortodoncia")
        # Defensive: ensure we trim any whitespace from the doc_id before
        # deriving the human-friendly filename used as `filename` in payloads.
        original_name = (d.doc_id or "").strip()
        if "_" in original_name and len(original_name.split("_")[0]) == 8:
            # Looks like a hash prefix, extract the rest
            original_name = "_".join(original_name.split("_")[1:])

        ingest_docs.append(
            IngestDoc(
                doc_id=d.doc_id,
                content=d.content,
                source=source_type,
                metadata={},
                filename=original_name,
            )
        )

    logger.info(
        "doc_ingest_start",
        total_documents=len(ingest_docs),
        pdfs=len(pdf_docs),
        text_files=len(text_docs),
    )
    return upsert_documents(ingest_docs)


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    # Simple CLI behaviour: cargar PDFs y opcionalmente ingestar en Qdrant
    docs = load_banking_pdfs_default()
    print(f"Loaded {len(docs)} PDF documents from 'documentacion/'")
    for d in docs[:3]:
        preview = d.content[:400].replace("\n", " ")
        print(f"- {d.doc_id}: {len(d.content)} chars :: {preview!r}...")

    # Si además el entorno tiene Qdrant accesible, se puede llamar
    # explícitamente a `ingest_banking_pdfs_into_qdrant()` desde tooling o
    # scripts externos; no lo invocamos automáticamente aquí para evitar
    # efectos laterales inesperados.
