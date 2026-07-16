"""
tests/test_ocr.py — Unit tests for OCR fallback in PDF parser (Phase 8).

Tests the _try_ocr fallback function and its integration with
extract_text_from_pdf when standard extraction methods return < 50 chars.
"""
import io
from unittest.mock import patch, MagicMock

import pytest

from app.services.parser.pdf_parser import _try_ocr, extract_text_from_pdf, ParseError


class TestTryOcr:
    """Unit tests for the _try_ocr fallback function."""

    @patch("app.services.parser.pdf_parser._try_pymupdf", return_value="short")
    @patch("app.services.parser.pdf_parser._try_pdfplumber", return_value="short")
    def test_ocr_called_when_standard_extraction_returns_less_than_50_chars(
        self, mock_pdfplumber: MagicMock, mock_pymupdf: MagicMock
    ) -> None:
        """_try_ocr is called ONLY when both PyMuPDF and pdfplumber return < 50 chars."""
        with patch("app.services.parser.pdf_parser._try_ocr", return_value="") as mock_ocr:
            with pytest.raises(ParseError):
                extract_text_from_pdf(b"fake-pdf-bytes", filename="test.pdf")
            mock_ocr.assert_called_once_with(b"fake-pdf-bytes", "test.pdf")

    @patch("app.services.parser.pdf_parser._try_pymupdf", return_value="a" * 60)
    @patch("app.services.parser.pdf_parser._try_pdfplumber", return_value="b" * 60)
    def test_ocr_not_called_when_standard_extraction_succeeds(
        self, mock_pdfplumber: MagicMock, mock_pymupdf: MagicMock
    ) -> None:
        """_try_ocr is NOT called when standard extraction returns >= 50 chars."""
        with patch("app.services.parser.pdf_parser._try_ocr", return_value="") as mock_ocr:
            extract_text_from_pdf(b"fake-pdf-bytes", filename="test.pdf")
            mock_ocr.assert_not_called()

    def test_ocr_import_error_returns_empty_string_and_raises_parse_error(self) -> None:
        """If pytesseract is missing (ImportError), parser returns empty string and raises ParseError."""
        with patch("app.services.parser.pdf_parser._try_pymupdf", return_value=""):
            with patch("app.services.parser.pdf_parser._try_pdfplumber", return_value=""):
                with patch.dict(
                    "sys.modules", {"pytesseract": None, "pdf2image": None}
                ):
                    with pytest.raises(ParseError):
                        extract_text_from_pdf(b"fake-pdf-bytes", filename="test.pdf")
