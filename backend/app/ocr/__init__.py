"""
OCR and text extraction package.
"""
from app.ocr.engine import extract_text_from_file
from app.ocr.parsers import parse_document_text, normalize_date, extract_gender

__all__ = [
    "extract_text_from_file",
    "parse_document_text",
    "normalize_date",
    "extract_gender",
]
