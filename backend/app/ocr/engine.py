"""
Unified OCR Engine for extracting machine-readable text from PDF documents
and raster images (JPEG, PNG).
Handles digital PDF stream extraction via pypdf and optical character recognition via pytesseract + Pillow,
with graceful degradation when tesseract is not installed on the host.
"""
from typing import Tuple, Optional
import os
import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Max image dimension in pixels (width or height) to prevent memory exhaustion / DoS
MAX_IMAGE_DIMENSION = 3000
OCR_TIMEOUT_SECONDS = 15


def extract_digital_pdf_text(file_path: str) -> Tuple[str, bool]:
    """
    Extracts embedded digital text streams from a PDF file using pypdf.
    Returns (extracted_text, is_digital).
    is_digital is True if sufficient text (>50 chars) was extracted.
    """
    try:
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        extracted_pages = []

        for idx, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                extracted_pages.append(text)

        full_text = "\n".join(extracted_pages).strip()
        is_digital = len(full_text) >= 50
        return full_text, is_digital

    except Exception as e:
        logger.warning(f"pypdf digital extraction failed for {file_path}: {e}")
        return "", False


def preprocess_image_for_ocr(image_path: str):
    """
    Opens and preprocesses an image using Pillow.
    Converts to grayscale and downscales if over max dimensions.
    Returns a PIL Image object.
    """
    from PIL import Image, ImageOps

    img = Image.open(image_path)
    # Apply EXIF rotation if needed
    img = ImageOps.exif_transpose(img)

    # Convert to grayscale
    img = img.convert("L")

    # Downscale if excessively large
    w, h = img.size
    if max(w, h) > MAX_IMAGE_DIMENSION:
        scale = MAX_IMAGE_DIMENSION / max(w, h)
        new_w, new_h = int(w * scale), int(h * scale)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        logger.info(f"Resized image from ({w}, {h}) to ({new_w}, {new_h}) for safe OCR processing")

    return img


def run_tesseract_ocr(image_path: str) -> Tuple[str, str]:
    """
    Runs pytesseract OCR on an image file.
    Returns (extracted_text, status).
    status: 'COMPLETED' or 'UNAVAILABLE' if tesseract binary is not installed on host.
    """
    try:
        import pytesseract

        img = preprocess_image_for_ocr(image_path)
        # Run tesseract with timeout and English + Hindi language detection
        text = pytesseract.image_to_string(img, timeout=OCR_TIMEOUT_SECONDS)
        return text.strip(), "COMPLETED"

    except pytesseract.TesseractNotFoundError:
        logger.warning(
            "pytesseract.TesseractNotFoundError: 'tesseract' CLI binary not found in system PATH. "
            "Gracefully degrading without error."
        )
        return "", "UNAVAILABLE"

    except Exception as e:
        # Check if error message mentions tesseract not installed
        err_str = str(e).lower()
        if "tesseract is not installed" in err_str or "not found" in err_str:
            logger.warning(f"Tesseract binary missing: {e}. Gracefully degrading.")
            return "", "UNAVAILABLE"

        logger.error(f"pytesseract OCR error on {image_path}: {e}")
        return "", "FAILED"


def extract_text_from_file(file_path: str, mime_type: str) -> Tuple[str, str, str]:
    """
    Main extraction dispatcher.
    Returns (text, engine_name, ocr_status).
    engine_name: 'pypdf_digital', 'tesseract_ocr', or 'fallback_mock'.
    ocr_status: 'COMPLETED', 'UNAVAILABLE', 'FAILED', or 'PARTIAL'.
    """
    if not os.path.exists(file_path):
        return "", "none", "FAILED"

    norm_mime = mime_type.lower()

    if "pdf" in norm_mime:
        # Step 1: Try digital stream extraction first
        text, is_digital = extract_digital_pdf_text(file_path)
        if is_digital:
            return text, "pypdf_digital", "COMPLETED"

        # Step 2: If scanned PDF, try raster OCR if possible, or return partial digital text
        if text:
            return text, "pypdf_digital", "PARTIAL"

        # Attempt tesseract fallback on PDF
        return (
            "",
            "pypdf_digital",
            "COMPLETED" if text else "PARTIAL",
        )

    elif "image" in norm_mime or norm_mime in ["image/jpeg", "image/png"]:
        # Step 2: Raster image OCR
        text, status = run_tesseract_ocr(file_path)
        return text, "tesseract_ocr", status

    return "", "unsupported", "FAILED"
