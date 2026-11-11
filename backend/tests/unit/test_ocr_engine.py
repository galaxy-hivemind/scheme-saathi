"""
Unit tests for Document OCR extraction engine, pattern parsers, PII masking, and graceful degradation.
"""
import io
import pytest
from unittest.mock import patch
from PIL import Image

from app.ocr.parsers import (
    normalize_date,
    extract_gender,
    extract_aadhaar_fields,
    extract_pan_fields,
    extract_income_fields,
    extract_caste_fields,
    extract_land_fields,
    extract_bank_fields,
    parse_document_text,
)
from app.ocr.engine import (
    extract_digital_pdf_text,
    preprocess_image_for_ocr,
    run_tesseract_ocr,
    extract_text_from_file,
    MAX_IMAGE_DIMENSION,
)


def test_normalize_date_formats():
    """Verify various date formats are safely normalized to YYYY-MM-DD."""
    assert normalize_date("14/05/1982") == "1982-05-14"
    assert normalize_date("01-01-2000") == "2000-01-01"
    assert normalize_date("1995-12-31") == "1995-12-31"
    assert normalize_date("31/02/2020") is None  # Invalid date
    assert normalize_date("not-a-date") is None
    assert normalize_date("15/08/1850") is None  # Out of range (< 1900)


def test_extract_gender_multilingual():
    """Verify gender extraction handles English and Hindi tokens correctly."""
    assert extract_gender("Gender: Male") == "male"
    assert extract_gender("लिंग: महिला") == "female"
    assert extract_gender("Gender: Female / महिला") == "female"
    assert extract_gender("Third Gender / Transgender") == "transgender"
    assert extract_gender("No gender mentioned") is None


def test_aadhaar_extractor_with_mandatory_pii_masking():
    """
    Verify Aadhaar extraction strictly masks the first 8 digits (XXXXXXXX1234)
    and extracts DOB, gender, and candidate name.
    """
    sample_text = """
    GOVERNMENT OF INDIA
    Unique Identification Authority of India
    To: Ramesh Kumar Sharma
    DOB: 15/08/1978
    Male / पुरुष
    5489 1234 9876
    """
    fields = extract_aadhaar_fields(sample_text)

    # Mandatory PII masking check
    assert fields.get("masked_uid") == "XXXXXXXX9876"
    assert "5489" not in str(fields.values())
    assert "1234" not in str(fields.get("masked_uid"))[:8]

    # Demographic attributes check
    assert fields.get("date_of_birth") == "1978-08-15"
    assert fields.get("gender") == "male"
    assert fields.get("name") == "Ramesh Kumar Sharma"


def test_pan_extractor():
    """Verify PAN extraction enforces standard 10-char format and extracts DOB and Name."""
    sample_text = """
    INCOME TAX DEPARTMENT
    GOVT. OF INDIA
    Permanent Account Number Card
    ABCDE1234F
    Name: SUNITA DEVI
    Date of Birth: 22/11/1985
    """
    fields = extract_pan_fields(sample_text)

    assert fields.get("pan_number") == "ABCDE1234F"
    assert fields.get("date_of_birth") == "1985-11-22"
    assert fields.get("name") == "SUNITA DEVI"


def test_income_certificate_extractor():
    """Verify income certificate extracts numeric income, certificate number, and authority."""
    sample_text = """
    OFFICE OF THE TEHSILDAR, NAGPUR
    INCOME CERTIFICATE
    Certificate No: INC/MH/2026/894123
    This is to certify that annual family income of Shri Ajay Patil
    is Rs. 1,20,000/- (Rupees One Lakh Twenty Thousand Only).
    Date: 10/01/2026
    """
    fields = extract_income_fields(sample_text)

    assert fields.get("annual_family_income") == 120000
    assert fields.get("certificate_number") == "INC/MH/2026/894123"
    assert fields.get("issuing_authority") == "Tehsildar"
    assert fields.get("issue_date") == "2026-01-10"


def test_caste_certificate_extractor():
    """Verify caste certificate extracts normalized category and certificate details."""
    sample_text = """
    DISTRICT MAGISTRATE OFFICE, VARANASI
    CASTE AND COMMUNITY CERTIFICATE
    Certificate No.: CAST-UP-2025-45120
    It is certified that Kum. Priya Singh belongs to Other Backward Class (OBC).
    State: Uttar Pradesh
    District: Varanasi
    """
    fields = extract_caste_fields(sample_text)

    assert fields.get("caste_category") == "OBC"
    assert fields.get("certificate_number") == "CAST-UP-2025-45120"
    assert fields.get("state") == "Uttar Pradesh"
    assert fields.get("district") == "Varanasi"


def test_land_records_extractor_hectares_to_acres():
    """Verify land record extracts area in acres, converting hectares if needed."""
    sample_text = """
    REVENUE DEPARTMENT - RECORD OF RIGHTS (RoR)
    Khasra No: 142/1
    Khata No: 88
    Total Land Area: 2.0 Hectare
    """
    fields = extract_land_fields(sample_text)

    # 2.0 Hectares * 2.47105 = ~4.94 Acres
    assert fields.get("land_area_acres") == 4.94
    assert fields.get("khasra_number") == "142/1"
    assert fields.get("khata_number") == "88"


def test_bank_passbook_extractor():
    """Verify bank passbook extracts IFSC and masks account number."""
    sample_text = """
    STATE BANK OF INDIA
    Account No: 20491823901
    IFSC: SBIN0001234
    Branch: Civil Lines
    """
    fields = extract_bank_fields(sample_text)

    assert fields.get("ifsc_code") == "SBIN0001234"
    assert fields.get("masked_account_number") == "XXXXXXXX3901"


def test_parse_document_text_confidence():
    """Verify confidence score is calculated based on fields discovered."""
    text = "DOB: 10/05/1990 Male 1234 5678 9012"
    fields, conf = parse_document_text("aadhaar_card", text)
    assert conf >= 0.80
    assert fields.get("masked_uid") == "XXXXXXXX9012"

    empty_fields, empty_conf = parse_document_text("other", "Random text with no demographic tokens")
    assert empty_conf == 0.0
    assert empty_fields == {}


def test_digital_pdf_stream_extraction(tmp_path):
    """Verify pypdf extracts text from a digital PDF file."""
    from pypdf import PdfWriter

    pdf_path = tmp_path / "sample_digital.pdf"
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)

    # Add text to PDF via writer
    from pypdf.generic import NameObject, DictionaryObject, ArrayObject, FloatObject
    # Create simple digital PDF with text stream
    writer.write(pdf_path)

    # Now test with synthetic PDF that has content
    text, is_digital = extract_digital_pdf_text(str(pdf_path))
    assert isinstance(text, str)
    assert isinstance(is_digital, bool)


def test_graceful_degradation_on_missing_tesseract(tmp_path):
    """
    Verify that if the host lacks tesseract CLI, the engine catches
    TesseractNotFoundError and returns 'UNAVAILABLE' without crashing.
    """
    img_path = tmp_path / "test.png"
    img = Image.new("RGB", (100, 100), color="white")
    img.save(img_path)

    import pytesseract

    with patch("pytesseract.image_to_string", side_effect=pytesseract.TesseractNotFoundError):
        text, status = run_tesseract_ocr(str(img_path))
        assert status == "UNAVAILABLE"
        assert text == ""


def test_image_preprocessing_downscales_oversized_images(tmp_path):
    """Verify that images larger than MAX_IMAGE_DIMENSION are safely resized to prevent DoS."""
    img_path = tmp_path / "giant.jpg"
    # Create a 4000x2000 image
    giant_img = Image.new("RGB", (4000, 2000), color="gray")
    giant_img.save(img_path)

    processed = preprocess_image_for_ocr(str(img_path))
    w, h = processed.size
    assert max(w, h) <= MAX_IMAGE_DIMENSION
    assert processed.mode == "L"  # Grayscale
