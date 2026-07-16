"""
app/services/parser/pdf_parser.py — PDF → raw text extractor.

Uses PyMuPDF (fitz) as primary for column-aware extraction,
falls back to pdfplumber if PyMuPDF fails or returns empty text.
Falls back to OCR (pytesseract + pdf2image) if both return < 50 chars.

Explicitly does NOT fake success — raises ParseError if no method
can extract usable text from the file.
"""
import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ParseError(Exception):
    """Raised when a file cannot be parsed into usable text."""
    pass


def extract_text_from_pdf(file_bytes: bytes, filename: str = "unknown.pdf") -> str:
    """
    Extract raw text from a PDF file.

    Args:
        file_bytes: Raw bytes of the PDF file.
        filename: Original filename (used for logging only).

    Returns:
        Extracted text as a single string with page breaks preserved.

    Raises:
        ParseError: If no extraction method can extract usable text.
    """
    text = _try_pymupdf(file_bytes, filename)
    if text and len(text.strip()) > 50:
        logger.info("PyMuPDF extracted %d chars from '%s'", len(text), filename)
        return text

    logger.warning(
        "PyMuPDF returned insufficient text (%d chars) from '%s', trying pdfplumber",
        len(text) if text else 0,
        filename,
    )
    text = _try_pdfplumber(file_bytes, filename)
    if text and len(text.strip()) > 50:
        logger.info("pdfplumber extracted %d chars from '%s'", len(text), filename)
        return text

    logger.warning(
        "pdfplumber returned insufficient text (%d chars) from '%s', trying OCR",
        len(text) if text else 0,
        filename,
    )
    text = _try_ocr(file_bytes, filename)
    if text and len(text.strip()) > 50:
        logger.info("OCR extracted %d chars from '%s'", len(text), filename)
        return text

    raise ParseError(
        f"Could not extract usable text from '{filename}'. "
        "The file may be a corrupted/encrypted PDF, or OCR dependencies are missing."
    )


def _try_pdfplumber(file_bytes: bytes, filename: str) -> str:
    """Attempt extraction with pdfplumber."""
    try:
        import pdfplumber

        pages_text: list[str] = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            if len(pdf.pages) == 0:
                logger.warning("pdfplumber: '%s' has 0 pages", filename)
                return ""
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text(
                    x_tolerance=2,
                    y_tolerance=2,
                    layout=True,
                    x_density=7.25,
                    y_density=13,
                ) or ""
                pages_text.append(page_text)
                logger.debug("pdfplumber page %d: %d chars", i + 1, len(page_text))
        return "\n\n".join(pages_text)

    except Exception as exc:
        logger.warning("pdfplumber failed on '%s': %s", filename, exc)
        return ""


def _try_pymupdf(file_bytes: bytes, filename: str) -> str:
    """Attempt extraction with PyMuPDF (fitz) using column-aware sorting."""
    try:
        import fitz  # PyMuPDF

        pages_text: list[str] = []
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            if doc.page_count == 0:
                logger.warning("PyMuPDF: '%s' has 0 pages", filename)
                return ""
            for i, page in enumerate(doc):
                # get_text("blocks") returns list of tuples: (x0, y0, x1, y1, "text", block_no, block_type)
                # block_type == 0 is text
                blocks = [b for b in page.get_text("blocks") if b[6] == 0]
                
                # Heuristic for multi-column: sort blocks primarily by x0 coordinate (left-to-right),
                # rounded to group columns together. Then by y0 (top-to-bottom) within a column.
                # A reasonable threshold for horizontal grouping is 50 points.
                blocks.sort(key=lambda b: (round(b[0] / 50.0), b[1]))
                
                page_text = "\n\n".join([b[4].strip() for b in blocks if b[4].strip()])
                pages_text.append(page_text)
                logger.debug("PyMuPDF page %d: %d chars", i + 1, len(page_text))
        return "\n\n".join(pages_text)

    except Exception as exc:
        logger.warning("PyMuPDF failed on '%s': %s", filename, exc)
        return ""


def _try_ocr(file_bytes: bytes, filename: str) -> str:
    """
    Attempt OCR extraction using pytesseract + pdf2image.
    Only used as last resort after PyMuPDF and pdfplumber fail.
    
    Requires:
    - pytesseract (Python package)
    - pdf2image (Python package)  
    - Tesseract OCR (system binary)
    - Poppler (system binary for pdf2image)
    
    Args:
        file_bytes: Raw PDF bytes
        filename: Original filename (logging only)
        
    Returns:
        Extracted text or empty string if OCR fails
    """
    try:
        import pytesseract
        from pdf2image import convert_from_bytes
        from PIL import Image
        
        logger.info("Attempting OCR on '%s'", filename)
        
        # Convert PDF pages to images
        images = convert_from_bytes(file_bytes, dpi=300)
        if not images:
            logger.warning("OCR: No images extracted from '%s'", filename)
            return ""
        
        pages_text: list[str] = []
        for i, image in enumerate(images):
            # Run tesseract OCR on each page image
            page_text = pytesseract.image_to_string(image, lang='eng')
            pages_text.append(page_text.strip())
            logger.debug("OCR page %d: %d chars", i + 1, len(page_text))
        
        return "\n\n".join(pages_text)
        
    except ImportError as exc:
        logger.warning(
            "OCR dependencies not installed for '%s': %s. "
            "Install pytesseract, pdf2image, and system binaries (tesseract, poppler).",
            filename,
            exc
        )
        return ""
    except Exception as exc:
        logger.warning("OCR failed on '%s': %s", filename, exc)
        return ""
