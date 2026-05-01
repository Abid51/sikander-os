"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS DOCUMENT PARSER
  Parse: PDF, DOCX, TXT, CSV, JSON, XLSX
  Features: text extraction, summarization via LLM, chunking
  No fake stubs — real file parsing with graceful fallbacks
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Optional dependencies ────────────────────────────────────────────────────
try:
    import PyPDF2
    _PDF = True
except ImportError:
    _PDF = False
    logger.warning("[DOC] PyPDF2 not installed. Run: pip install PyPDF2")

try:
    from docx import Document as DocxDocument
    _DOCX = True
except ImportError:
    _DOCX = False
    logger.warning("[DOC] python-docx not installed. Run: pip install python-docx")

try:
    import openpyxl
    _XLSX = True
except ImportError:
    _XLSX = False

try:
    import pdfplumber
    _PDFPLUMBER = True
except ImportError:
    _PDFPLUMBER = False


# ─────────────────────────────────────────────────────────────────────────────
#  DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ParseResult:
    filename: str
    file_type: str
    text: str
    page_count: int
    word_count: int
    char_count: int
    metadata: Dict[str, Any]
    chunks: List[str]
    latency_ms: float
    success: bool = True
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        d = asdict(self)
        # Truncate text for API response
        if len(d["text"]) > 5000:
            d["text_preview"] = d["text"][:5000] + "..."
            d["text_full_length"] = len(self.text)
        return d


@dataclass
class DocumentSummary:
    filename: str
    summary: str
    key_points: List[str]
    model_used: str
    latency_ms: float
    success: bool = True
    error: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
#  DOCUMENT PARSER
# ─────────────────────────────────────────────────────────────────────────────

class IgrisDocumentParser:
    """
    Multi-format document parser for Igris.

    Supported formats:
    ──────────────────
    • PDF  (via PyPDF2 or pdfplumber)
    • DOCX (via python-docx)
    • TXT  (built-in)
    • CSV  (built-in)
    • JSON (built-in)
    • XLSX (via openpyxl)

    Usage:
    ──────
    result = await parser.parse_file("/path/to/doc.pdf")
    result = await parser.parse_bytes(data, "report.pdf")
    summary = await parser.summarize_file("/path/to/doc.pdf")
    chunks = parser.chunk_text(text, chunk_size=500)
    """

    SUPPORTED = {".pdf", ".docx", ".doc", ".txt", ".csv", ".json", ".xlsx", ".xls", ".md", ".log"}
    MAX_TEXT_LENGTH = 100_000  # 100k chars max extraction

    def __init__(self) -> None:
        self._history: List[Dict[str, Any]] = []
        logger.info(
            f"[DOC] Parser online — PDF={'yes' if _PDF or _PDFPLUMBER else 'no'}, "
            f"DOCX={'yes' if _DOCX else 'no'}, XLSX={'yes' if _XLSX else 'no'}"
        )

    async def parse_file(self, file_path: str) -> ParseResult:
        """Parse a document file from disk."""
        file_path = os.path.abspath(file_path)
        if not os.path.isfile(file_path):
            return ParseResult(
                filename=os.path.basename(file_path), file_type="unknown",
                text="", page_count=0, word_count=0, char_count=0,
                metadata={}, chunks=[], latency_ms=0,
                success=False, error=f"File not found: {file_path}",
            )
        with open(file_path, "rb") as f:
            data = f.read()
        return await self.parse_bytes(data, os.path.basename(file_path))

    async def parse_bytes(self, data: bytes, filename: str) -> ParseResult:
        """Parse document bytes."""
        t = time.time()
        ext = os.path.splitext(filename)[1].lower()

        try:
            if ext == ".pdf":
                text, pages, meta = await asyncio.to_thread(self._parse_pdf, data)
            elif ext in (".docx", ".doc"):
                text, pages, meta = await asyncio.to_thread(self._parse_docx, data)
            elif ext == ".txt" or ext == ".md" or ext == ".log":
                text, pages, meta = self._parse_text(data)
            elif ext == ".csv":
                text, pages, meta = self._parse_csv(data)
            elif ext == ".json":
                text, pages, meta = self._parse_json(data)
            elif ext in (".xlsx", ".xls"):
                text, pages, meta = await asyncio.to_thread(self._parse_xlsx, data)
            else:
                return ParseResult(
                    filename=filename, file_type=ext,
                    text="", page_count=0, word_count=0, char_count=0,
                    metadata={}, chunks=[], latency_ms=(time.time() - t) * 1000,
                    success=False, error=f"Unsupported format: {ext}. Supported: {self.SUPPORTED}",
                )

            # Truncate if too long
            text = text[:self.MAX_TEXT_LENGTH]
            words = len(text.split())
            chunks = self.chunk_text(text, chunk_size=500)

            result = ParseResult(
                filename=filename, file_type=ext, text=text,
                page_count=pages, word_count=words, char_count=len(text),
                metadata=meta, chunks=chunks,
                latency_ms=(time.time() - t) * 1000,
            )

            self._history.append({
                "filename": filename, "type": ext, "pages": pages,
                "words": words, "ts": time.time(),
            })
            return result

        except Exception as e:
            logger.error(f"[DOC] Parse error for {filename}: {e}")
            return ParseResult(
                filename=filename, file_type=ext,
                text="", page_count=0, word_count=0, char_count=0,
                metadata={}, chunks=[], latency_ms=(time.time() - t) * 1000,
                success=False, error=str(e),
            )

    # ── Format-specific parsers ───────────────────────────────────────────────

    def _parse_pdf(self, data: bytes) -> tuple:
        """Parse PDF file bytes."""
        text_parts = []
        pages = 0
        meta = {}

        # Try pdfplumber first (better text extraction)
        if _PDFPLUMBER:
            try:
                import pdfplumber
                with pdfplumber.open(io.BytesIO(data)) as pdf:
                    pages = len(pdf.pages)
                    meta = dict(pdf.metadata) if pdf.metadata else {}
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(page_text)
                return "\n\n".join(text_parts), pages, meta
            except Exception:
                pass

        # Fallback: PyPDF2
        if _PDF:
            reader = PyPDF2.PdfReader(io.BytesIO(data))
            pages = len(reader.pages)
            if reader.metadata:
                for key, val in reader.metadata.items():
                    meta[key.lstrip("/")] = str(val)[:200]
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            return "\n\n".join(text_parts), pages, meta

        raise ImportError("No PDF library available. Install: pip install PyPDF2 pdfplumber")

    def _parse_docx(self, data: bytes) -> tuple:
        """Parse DOCX file bytes."""
        if not _DOCX:
            raise ImportError("python-docx not installed. Run: pip install python-docx")

        doc = DocxDocument(io.BytesIO(data))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n".join(paragraphs)

        # Extract metadata
        meta = {}
        if doc.core_properties:
            props = doc.core_properties
            if props.author:
                meta["author"] = props.author
            if props.title:
                meta["title"] = props.title
            if props.created:
                meta["created"] = str(props.created)
            if props.modified:
                meta["modified"] = str(props.modified)

        # Approximate pages (DOCX doesn't have native page count)
        page_estimate = max(1, len(text) // 3000)

        return text, page_estimate, meta

    def _parse_text(self, data: bytes) -> tuple:
        """Parse plain text file."""
        for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                text = data.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = data.decode("utf-8", errors="replace")

        lines = text.count("\n") + 1
        return text, 1, {"lines": lines, "encoding": encoding}

    def _parse_csv(self, data: bytes) -> tuple:
        """Parse CSV file."""
        text = data.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)

        # Build readable text
        if not rows:
            return "", 0, {"rows": 0, "columns": 0}

        headers = rows[0] if rows else []
        formatted = []
        formatted.append("| " + " | ".join(headers) + " |")
        formatted.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in rows[1:]:
            formatted.append("| " + " | ".join(row) + " |")

        return "\n".join(formatted), 1, {
            "rows": len(rows) - 1,
            "columns": len(headers),
            "headers": headers,
        }

    def _parse_json(self, data: bytes) -> tuple:
        """Parse JSON file."""
        text = data.decode("utf-8", errors="replace")
        parsed = json.loads(text)
        pretty = json.dumps(parsed, indent=2, ensure_ascii=False)

        meta = {"type": type(parsed).__name__}
        if isinstance(parsed, list):
            meta["items"] = len(parsed)
        elif isinstance(parsed, dict):
            meta["keys"] = list(parsed.keys())[:20]

        return pretty, 1, meta

    def _parse_xlsx(self, data: bytes) -> tuple:
        """Parse Excel file."""
        if not _XLSX:
            raise ImportError("openpyxl not installed. Run: pip install openpyxl")

        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        sheets_text = []
        total_rows = 0
        meta = {"sheets": wb.sheetnames}

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                continue
            total_rows += len(rows)
            sheets_text.append(f"## Sheet: {sheet_name}")
            for row in rows[:200]:  # Limit per sheet
                cells = [str(c) if c is not None else "" for c in row]
                sheets_text.append(" | ".join(cells))

        wb.close()
        return "\n".join(sheets_text), 1, {**meta, "total_rows": total_rows}

    # ── Utilities ─────────────────────────────────────────────────────────────

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks for RAG/embedding."""
        if not text:
            return []
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i:i + chunk_size])
            if chunk.strip():
                chunks.append(chunk)
        return chunks

    async def summarize(
        self,
        text: str,
        filename: str = "document",
        max_tokens: int = 500,
    ) -> DocumentSummary:
        """Use LLM to summarize document text."""
        try:
            from app.core.llm_manager import universal_llm
            prompt = (
                f"Summarize this document ({filename}) concisely.\n\n"
                f"Document text (first 4000 chars):\n{text[:4000]}\n\n"
                "Provide:\n1. A brief summary (2-3 paragraphs)\n2. Key points (bullet list)"
            )
            response = await universal_llm.generate_response(
                system_prompt="You are a document summarizer. Be concise and accurate.",
                user_prompt=prompt,
                max_tokens=max_tokens,
            )

            # Try to split into summary + key points
            key_points = []
            summary = response
            if "key point" in response.lower() or "•" in response or "- " in response:
                lines = response.split("\n")
                summary_lines = []
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith(("•", "- ", "* ", "1.", "2.", "3.", "4.", "5.")):
                        key_points.append(stripped.lstrip("•-* 0123456789.").strip())
                    else:
                        summary_lines.append(line)
                summary = "\n".join(summary_lines).strip()

            return DocumentSummary(
                filename=filename,
                summary=summary,
                key_points=key_points,
                model_used=getattr(universal_llm, "current_model", "unknown"),
                latency_ms=0,
            )
        except Exception as e:
            return DocumentSummary(
                filename=filename, summary="", key_points=[],
                model_used="none", latency_ms=0,
                success=False, error=str(e),
            )

    async def summarize_file(self, file_path: str) -> DocumentSummary:
        """Parse + summarize a document file."""
        parsed = await self.parse_file(file_path)
        if not parsed.success:
            return DocumentSummary(
                filename=parsed.filename, summary="", key_points=[],
                model_used="", latency_ms=0,
                success=False, error=parsed.error,
            )
        return await self.summarize(parsed.text, parsed.filename)

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._history[-limit:]

    def get_status(self) -> Dict[str, Any]:
        return {
            "supported_formats": sorted(self.SUPPORTED),
            "pdf_available": _PDF or _PDFPLUMBER,
            "docx_available": _DOCX,
            "xlsx_available": _XLSX,
            "total_parsed": len(self._history),
        }


# ─────────────────────────────────────────────────────────────────────────────
#  SINGLETON
# ─────────────────────────────────────────────────────────────────────────────

_instance: Optional[IgrisDocumentParser] = None


def get_document_parser() -> IgrisDocumentParser:
    global _instance
    if _instance is None:
        _instance = IgrisDocumentParser()
    return _instance
