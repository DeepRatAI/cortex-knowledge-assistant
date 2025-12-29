"""Advanced semantic chunking for RAG pipelines.

Implements state-of-the-art chunking strategies:
- Semantic chunking (respects sentence boundaries)
- Sliding window with overlap for context preservation
- Metadata-aware chunking (preserves document structure)
- Recursive character text splitting as fallback

Best practices from LangChain, LlamaIndex, and research papers.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Iterator, Sequence


@dataclass(frozen=True)
class ChunkMetadata:
    """Metadata attached to each chunk for traceability."""

    doc_id: str
    chunk_index: int
    total_chunks: int
    start_char: int
    end_char: int
    has_overlap: bool = False
    section_title: str | None = None


@dataclass(frozen=True)
class TextChunk:
    """A chunk of text with associated metadata."""

    text: str
    metadata: ChunkMetadata
    chunk_hash: str = field(default="")

    def __post_init__(self):
        if not self.chunk_hash:
            # Compute content hash for deduplication
            object.__setattr__(
                self,
                "chunk_hash",
                hashlib.md5(self.text.encode("utf-8")).hexdigest()[:12],
            )


class SemanticChunker:
    """Advanced chunking that respects semantic boundaries.

    Features:
    - Respects sentence boundaries (no mid-sentence splits)
    - Preserves paragraph structure when possible
    - Sliding window overlap for context preservation
    - Section header detection for documents
    - Configurable chunk sizes based on token estimates

    Args:
        chunk_size: Target chunk size in characters (default: 500)
        chunk_overlap: Overlap between consecutive chunks (default: 50)
        min_chunk_size: Minimum chunk size to avoid tiny fragments (default: 100)
        respect_sentences: Whether to avoid splitting mid-sentence (default: True)
    """

    # Sentence boundary patterns for Spanish and English
    SENTENCE_ENDINGS = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ])|(?<=[.!?])\s*\n")

    # Paragraph separators
    PARAGRAPH_SEP = re.compile(r"\n\s*\n")

    # Section headers (common patterns in Spanish documents)
    SECTION_HEADERS = re.compile(
        r"^(?:UNIDAD|CAPÍTULO|SECCIÓN|TEMA|MÓDULO|PARTE)\s*(?:N[º°]?)?\s*\d+",
        re.IGNORECASE | re.MULTILINE,
    )

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        min_chunk_size: int = 100,
        respect_sentences: bool = True,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.respect_sentences = respect_sentences

    def chunk_text(self, text: str, doc_id: str) -> list[TextChunk]:
        """Split text into semantically coherent chunks.

        Args:
            text: The full document text
            doc_id: Document identifier for metadata

        Returns:
            List of TextChunk objects with metadata
        """
        if not text or not text.strip():
            return []

        # Normalize whitespace
        text = self._normalize_text(text)

        # First, try to split by sections if document has clear structure
        sections = self._extract_sections(text)

        chunks: list[TextChunk] = []

        if sections:
            # Process each section separately
            for section_title, section_text, start_pos in sections:
                section_chunks = self._chunk_section(
                    section_text,
                    doc_id,
                    section_title=section_title,
                    offset=start_pos,
                )
                chunks.extend(section_chunks)
        else:
            # No clear sections, chunk the whole document
            chunks = self._chunk_section(text, doc_id)

        # Update total_chunks in metadata
        total = len(chunks)
        final_chunks = []
        for i, chunk in enumerate(chunks):
            new_meta = ChunkMetadata(
                doc_id=chunk.metadata.doc_id,
                chunk_index=i,
                total_chunks=total,
                start_char=chunk.metadata.start_char,
                end_char=chunk.metadata.end_char,
                has_overlap=chunk.metadata.has_overlap,
                section_title=chunk.metadata.section_title,
            )
            final_chunks.append(TextChunk(text=chunk.text, metadata=new_meta))

        return final_chunks

    def _normalize_text(self, text: str) -> str:
        """Normalize whitespace while preserving structure."""
        # Replace multiple spaces with single space
        text = re.sub(r"[ \t]+", " ", text)
        # Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # Reduce multiple newlines to max 2
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _extract_sections(self, text: str) -> list[tuple[str, str, int]]:
        """Extract sections with headers from document.

        Returns:
            List of (section_title, section_text, start_position)
        """
        matches = list(self.SECTION_HEADERS.finditer(text))

        if len(matches) < 2:
            # Not enough sections to be meaningful
            return []

        sections = []
        for i, match in enumerate(matches):
            title = match.group(0).strip()
            start = match.start()

            # End is start of next section or end of text
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            section_text = text[start:end].strip()

            if len(section_text) > self.min_chunk_size:
                sections.append((title, section_text, start))

        return sections

    def _chunk_section(
        self,
        text: str,
        doc_id: str,
        section_title: str | None = None,
        offset: int = 0,
    ) -> list[TextChunk]:
        """Chunk a section of text with overlap."""
        if len(text) <= self.chunk_size:
            # Small enough to be a single chunk
            meta = ChunkMetadata(
                doc_id=doc_id,
                chunk_index=0,
                total_chunks=1,
                start_char=offset,
                end_char=offset + len(text),
                has_overlap=False,
                section_title=section_title,
            )
            return [TextChunk(text=text, metadata=meta)]

        # Split into paragraphs first
        paragraphs = self.PARAGRAPH_SEP.split(text)

        chunks: list[TextChunk] = []
        current_chunk = ""
        chunk_start = offset

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk) + len(para) + 2 <= self.chunk_size:
                # Add paragraph to current chunk
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
            else:
                # Current chunk is full
                if current_chunk and len(current_chunk) >= self.min_chunk_size:
                    meta = ChunkMetadata(
                        doc_id=doc_id,
                        chunk_index=len(chunks),
                        total_chunks=0,  # Will be updated
                        start_char=chunk_start,
                        end_char=chunk_start + len(current_chunk),
                        has_overlap=len(chunks) > 0,
                        section_title=section_title,
                    )
                    chunks.append(TextChunk(text=current_chunk, metadata=meta))

                # Start new chunk with overlap from previous
                if self.chunk_overlap > 0 and current_chunk:
                    overlap_text = self._get_overlap_text(current_chunk)
                    current_chunk = overlap_text + "\n\n" + para if overlap_text else para
                else:
                    current_chunk = para

                chunk_start = offset + (len(text) - len(current_chunk))

                # If paragraph itself is too large, split it by sentences
                if len(para) > self.chunk_size:
                    sentence_chunks = self._split_by_sentences(para, doc_id, section_title, chunk_start)
                    chunks.extend(sentence_chunks)
                    current_chunk = ""

        # Don't forget the last chunk
        if current_chunk and len(current_chunk) >= self.min_chunk_size:
            meta = ChunkMetadata(
                doc_id=doc_id,
                chunk_index=len(chunks),
                total_chunks=0,
                start_char=chunk_start,
                end_char=chunk_start + len(current_chunk),
                has_overlap=len(chunks) > 0,
                section_title=section_title,
            )
            chunks.append(TextChunk(text=current_chunk, metadata=meta))

        return chunks

    def _split_by_sentences(
        self,
        text: str,
        doc_id: str,
        section_title: str | None,
        offset: int,
    ) -> list[TextChunk]:
        """Split text by sentence boundaries when paragraphs are too long."""
        sentences = self.SENTENCE_ENDINGS.split(text)

        chunks: list[TextChunk] = []
        current_chunk = ""
        chunk_start = offset

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            if len(current_chunk) + len(sentence) + 1 <= self.chunk_size:
                current_chunk = (current_chunk + " " + sentence).strip()
            else:
                if current_chunk and len(current_chunk) >= self.min_chunk_size:
                    meta = ChunkMetadata(
                        doc_id=doc_id,
                        chunk_index=len(chunks),
                        total_chunks=0,
                        start_char=chunk_start,
                        end_char=chunk_start + len(current_chunk),
                        has_overlap=len(chunks) > 0,
                        section_title=section_title,
                    )
                    chunks.append(TextChunk(text=current_chunk, metadata=meta))

                current_chunk = sentence
                chunk_start = offset

        if current_chunk and len(current_chunk) >= self.min_chunk_size:
            meta = ChunkMetadata(
                doc_id=doc_id,
                chunk_index=len(chunks),
                total_chunks=0,
                start_char=chunk_start,
                end_char=chunk_start + len(current_chunk),
                has_overlap=len(chunks) > 0,
                section_title=section_title,
            )
            chunks.append(TextChunk(text=current_chunk, metadata=meta))

        return chunks

    def _get_overlap_text(self, text: str) -> str:
        """Get the last N characters for overlap, respecting word boundaries."""
        if len(text) <= self.chunk_overlap:
            return text

        overlap_region = text[-self.chunk_overlap * 2 :]

        # Find a good word boundary
        words = overlap_region.split()
        result = []
        char_count = 0

        for word in reversed(words):
            if char_count + len(word) + 1 > self.chunk_overlap:
                break
            result.insert(0, word)
            char_count += len(word) + 1

        return " ".join(result) if result else ""


def simple_chunks(text: str, max_len: int = 400) -> list[str]:
    """Legacy simple chunking for backward compatibility.

    This is the original word-based splitting. For new code, prefer
    SemanticChunker for better results.
    """
    words = text.split()
    acc: list[str] = []
    cur: list[str] = []

    for w in words:
        cur.append(w)
        if sum(len(x) + 1 for x in cur) > max_len:
            if cur[:-1]:
                acc.append(" ".join(cur[:-1]))
            cur = [w]

    if cur:
        acc.append(" ".join(cur))

    return acc


def chunk_document(
    text: str,
    doc_id: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    use_semantic: bool = True,
) -> list[str]:
    """High-level API for chunking documents.

    Args:
        text: Document text
        doc_id: Document identifier
        chunk_size: Target chunk size
        chunk_overlap: Overlap between chunks
        use_semantic: Use semantic chunking (recommended)

    Returns:
        List of chunk texts
    """
    if use_semantic:
        chunker = SemanticChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        chunks = chunker.chunk_text(text, doc_id)
        return [c.text for c in chunks]
    else:
        return simple_chunks(text, max_len=chunk_size)
