"""
Authoritative Scheme Application Form Schemas and Document Sourcing Knowledge Base.
Provides structured field schemas for key Indian welfare schemes:
- PM-KISAN (Pradhan Mantri Kisan Samman Nidhi)
- KCC (Kisan Credit Card)
- PM-SVANIDHI (PM Street Vendor's AtmaNirbhar Nidhi)
- NSP-CSSS (National Scholarship Portal - Central Sector Scheme)
- PMMVY (Pradhan Mantri Matru Vandana Yojana)
- WIDOW-PENSION / IGNWPS (Indira Gandhi National Widow Pension Scheme / State Widow Pension)

Also contains verified document sourcing metadata (issuing authorities, fees, SLAs, portals).
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


# ── Authoritative Document Sourcing Knowledge ────────────────────────────────

DOCUMENT_SOURCING_REGISTRY: Dict[str, Dict[str, Any]] = {
    "aadhaar_card": {
        "title": "Aadhaar Card (आधार कार्ड)",
        "why_needed": "Statutory identity and biometric verification under Section 7 of the Aadhaar Act for Direct Benefit Transfer (DBT).",
        "where_to_obtain": "Aadhaar Seva Kendra, authorized Post Office, nationalized Bank branch, or online via UIDAI.",
        "issuing_authority": "Unique Identification Authority of India (UIDAI), Ministry of Electronics & IT.",
        "official_url": "https://myaadhaar.uidai.gov.in",
        "verified_fee": "Free for new enrolment; ₹50 for demographic update, ₹100 for biometric update.",
        "expected_processing_days": "7 to 15 working days for PVC card or update generation.",
        "is_verified": True,
        "is_digitally_verifiable": True,
    },
    "income_certificate": {
        "title": "Income Certificate (आय प्रमाण पत्र / उत्पन्न प्रमाणपत्र)",
        "why_needed": "To establish household income compliance below scheme-specific eligibility ceiling.",
        "where_to_obtain": "Tehsil / Taluka Revenue Office, Common Service Center (CSC / Jan Seva Kendra / Aaple Sarkar), or State e-District portal.",
        "issuing_authority": "Revenue Department (Tahsildar / Sub-Divisional Magistrate / Sub-Divisional Officer).",
        "official_url": "https://services.india.gov.in",
        "verified_fee": "₹15 to ₹30 at authorized CSC / state e-District service portal.",
        "expected_processing_days": "7 to 14 working days depending on state citizen service guarantee charters.",
        "is_verified": True,
        "is_digitally_verifiable": True,
    },
    "death_certificate": {
        "title": "Death Certificate of Husband (पतीचे मृत्यू प्रमाणपत्र / पति का मृत्यु प्रमाण पत्र)",
        "why_needed": "Mandatory statutory proof of husband's demise required for Indira Gandhi National Widow Pension Scheme (IGNWPS) and State Widow Pension.",
        "where_to_obtain": "Urban: Municipal Corporation / Municipality Registrar. Rural: Gram Panchayat / Block Development Office / Civil Registration System.",
        "issuing_authority": "Registrar of Births and Deaths (Office of the Registrar General of India / State Health & Family Welfare).",
        "official_url": "https://crsorgi.gov.in",
        "verified_fee": "Free if registered within 21 days; ₹10–₹50 search/late fee if delayed.",
        "expected_processing_days": "7 to 10 working days from application submission.",
        "is_verified": True,
        "is_digitally_verifiable": True,
    },
    "land_records": {
        "title": "Land Ownership Records (7/12 उतारा / Khasra-Khatauni / RoR)",
        "why_needed": "Official verification of cultivable landholding, survey number, and farmer ownership classification.",
        "where_to_obtain": "Tehsil Office, Talathi / Patwari Office, or computerized State Land Records portal (e.g. Mahabhumi, UP Bhulekh).",
        "issuing_authority": "Revenue & Land Reforms Department / Directorate of Land Records.",
        "official_url": "https://dilrmp.gov.in",
        "verified_fee": "Free online viewing; ₹15 to ₹30 for digitally signed government-certified copy.",
        "expected_processing_days": "Instant digital download if computerized; 3 to 5 days at local Talathi/Tehsil office.",
        "is_verified": True,
        "is_digitally_verifiable": True,
    },
    "bank_passbook": {
        "title": "Bank Passbook / Cancelled Cheque (बँक पासबुक)",
        "why_needed": "Verification of Aadhaar-seeded DBT active bank account number and branch IFSC code for direct cash transfer.",
        "where_to_obtain": "Home branch of Scheduled Commercial Bank, Regional Rural Bank (RRB), District Co-operative Bank, or India Post Payments Bank.",
        "issuing_authority": "Account-holding Banking Institution (RBI regulated).",
        "official_url": "https://financialservices.gov.in",
        "verified_fee": "Free for initial passbook; nominal replacement fee if lost.",
        "expected_processing_days": "Instant over the counter at bank branch.",
        "is_verified": True,
        "is_digitally_verifiable": True,
    },
    "vending_certificate": {
        "title": "Certificate of Vending / Letter of Recommendation (विक्री प्रमाणपत्र / LoR)",
        "why_needed": "Proof of street vending activity required under the Street Vendors Act, 2014 for PM-SVANidhi micro-credit.",
        "where_to_obtain": "Local Municipal Corporation / Urban Local Body (ULB) office or Town Vending Committee (TVC).",
        "issuing_authority": "Urban Local Body (ULB) / Town Vending Committee (TVC).",
        "official_url": "https://pmsvanidhi.mohua.gov.in",
        "verified_fee": "Free as prescribed under Street Vendors (Protection of Livelihood and Regulation of Street Vending) Act.",
        "expected_processing_days": "15 to 30 days following ULB survey or TVC recommendation meeting.",
        "is_verified": True,
        "is_digitally_verifiable": False,
    },
    "mcp_card": {
        "title": "Mother and Child Protection (MCP) Card (माता आणि बाल संरक्षण कार्ड)",
        "why_needed": "Statutory record of early pregnancy registration, Ante-Natal Check-ups (ANC), and institutional delivery under PMMVY.",
        "where_to_obtain": "Nearest Primary Health Centre (PHC), Sub-Centre, Anganwadi Centre, or Government Hospital.",
        "issuing_authority": "Ministry of Health & Family Welfare / Ministry of Women & Child Development.",
        "official_url": "https://pmmvy.wcd.gov.in",
        "verified_fee": "Completely Free at all public healthcare facilities.",
        "expected_processing_days": "Issued immediately upon first ANC registration.",
        "is_verified": True,
        "is_digitally_verifiable": False,
    },
    "marksheet_12th": {
        "title": "Class 12 Passing Marksheet & Certificate (१२वी गुणपत्रिका)",
        "why_needed": "Academic merit verification (above 80th percentile) and roll number validation for National Scholarship Scheme (NSP-CSSS).",
        "where_to_obtain": "Respective Higher Secondary School / Junior College, or instant fetch via DigiLocker.",
        "issuing_authority": "State Secondary and Higher Secondary Education Board, CBSE, or CISCE.",
        "official_url": "https://digilocker.gov.in",
        "verified_fee": "Free via DigiLocker; original copy provided by school.",
        "expected_processing_days": "Instant on DigiLocker; original issued as per board schedule.",
        "is_verified": True,
        "is_digitally_verifiable": True,
    },
    "caste_certificate": {
        "title": "Caste / Category Certificate (जातीचे प्रमाणपत्र / जाति प्रमाण पत्र)",
        "why_needed": "Verification of SC/ST/OBC category entitlement for targeted welfare benefits and fee exemptions.",
        "where_to_obtain": "Tehsil / Taluka Office, Sub-Divisional Magistrate (SDM) Office, CSC, or State e-District portal.",
        "issuing_authority": "Revenue Department (SDM / Sub-Collector / Tahsildar).",
        "official_url": "https://services.india.gov.in",
        "verified_fee": "₹15 to ₹30 at CSC / e-District.",
        "expected_processing_days": "15 to 21 working days.",
        "is_verified": True,
        "is_digitally_verifiable": True,
    },
    "domicile_certificate": {
        "title": "Domicile / Residence Certificate (अधिवास प्रमाणपत्र / निवास प्रमाण पत्र)",
        "why_needed": "Proof of permanent residency in the scheme jurisdiction (e.g. Uttar Pradesh or Maharashtra).",
        "where_to_obtain": "Tehsil Office, Sub-Divisional Magistrate Office, or State e-District portal.",
        "issuing_authority": "Revenue Department (SDM / Tahsildar).",
        "official_url": "https://services.india.gov.in",
        "verified_fee": "₹15 to ₹30 at CSC / e-District.",
        "expected_processing_days": "7 to 15 working days.",
        "is_verified": True,
        "is_digitally_verifiable": True,
    },
    "ration_card": {
        "title": "Ration Card (BPL / Antyodaya / Priority Household)",
        "why_needed": "Proof of household socioeconomic classification and poverty line status.",
        "where_to_obtain": "District Food and Civil Supplies Office or State Food Portal / CSC.",
        "issuing_authority": "Department of Food, Civil Supplies & Consumer Protection.",
        "official_url": "https://nfsa.gov.in",
        "verified_fee": "₹10 to ₹50 as per state notification.",
        "expected_processing_days": "15 to 30 working days.",
        "is_verified": True,
        "is_digitally_verifiable": True,
    },
}


def get_document_sourcing_info(doc_name: str) -> Dict[str, Any]:
    """
    Retrieves verified sourcing information for a document, or provides an authoritative fallback.
    """
    norm_key = doc_name.lower().replace(" ", "_").replace("-", "_").replace("/", "_")
    
    # Fuzzy match known types
    for key, info in DOCUMENT_SOURCING_REGISTRY.items():
        if key in norm_key or norm_key in key:
            return dict(info)
        # Match tokens
        if "death" in norm_key and "husband" in norm_key and key == "death_certificate":
            return dict(info)
        if ("income" in norm_key or "aay" in norm_key or "utpann" in norm_key) and key == "income_certificate":
            return dict(info)
        if ("aadhaar" in norm_key or "aadhar" in norm_key) and key == "aadhaar_card":
            return dict(info)
        if ("land" in norm_key or "khasra" in norm_key or "7/12" in norm_key or "khatauni" in norm_key) and key == "land_records":
            return dict(info)
        if ("bank" in norm_key or "passbook" in norm_key) and key == "bank_passbook":
            return dict(info)
        if ("vending" in norm_key or "lor" in norm_key or "vendor" in norm_key) and key == "vending_certificate":
            return dict(info)
        if ("mcp" in norm_key or "mother" in norm_key or "pregnancy" in norm_key) and key == "mcp_card":
            return dict(info)
        if ("12th" in norm_key or "marksheet" in norm_key or "scholarship" in norm_key) and key == "marksheet_12th":
            return dict(info)
        if ("caste" in norm_key or "jati" in norm_key) and key == "caste_certificate":
            return dict(info)
        if ("domicile" in norm_key or "niwas" in norm_key or "residence" in norm_key) and key == "domicile_certificate":
            return dict(info)

    # General verified fallback
    return {
        "title": doc_name.replace("_", " ").title(),
        "why_needed": f"Required for statutory eligibility assessment under scheme guidelines.",
        "where_to_obtain": "Nearest Tehsil / Block Office, Common Service Center (CSC), or relevant State Department portal.",
        "issuing_authority": "Designated State / Central Competent Authority.",
        "official_url": "https://services.india.gov.in",
        "verified_fee": "Nominal government prescribed service charge (confirm at local center).",
        "expected_processing_days": "Standard state service charter (typically 7 to 21 working days).",
        "is_verified": False,
        "is_digitally_verifiable": False,
    }


# ── Scheme-Specific Form Schemas ──────────────────────────────────────────────

SCHEME_FORM_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "PM-KISAN": {
        "scheme_code": "PM-KISAN",
        "title": "Pradhan Mantri Kisan Samman Nidhi Application Form",
        "form_supported": True,
        "official_portal": "https://pmkisan.gov.in",
        "sections": [
            {
                "section_id": "personal_info",
                "title": "Applicant Personal Details",
                "fields": [
                    {"name": "applicant_name", "label": "Farmer Full Name", "type": "text", "required": True, "profile_field": "full_name"},
                    {"name": "gender", "label": "Gender", "type": "select", "options": ["MALE", "FEMALE", "OTHER"], "required": True, "profile_field": "gender"},
                    {"name": "category", "label": "Social Category", "type": "select", "options": ["General", "OBC", "SC", "ST"], "required": True, "profile_field": "caste_category"},
                    {"name": "aadhaar_number", "label": "12-Digit Aadhaar Number", "type": "text", "required": True, "profile_field": "aadhaar_number", "pattern": r"^[0-9]{12}$"},
                    {"name": "mobile_number", "label": "Aadhaar-Linked Mobile Number", "type": "text", "required": True, "profile_field": "phone_number", "pattern": r"^[6-9][0-9]{9}$"},
                ],
            },
            {
                "section_id": "location_info",
                "title": "Residential & Agricultural Location",
                "fields": [
                    {"name": "state", "label": "State", "type": "text", "required": True, "profile_field": "state"},
                    {"name": "district", "label": "District", "type": "text", "required": True, "profile_field": "district"},
                    {"name": "sub_district_block", "label": "Sub-District / Tehsil / Block", "type": "text", "required": True, "profile_field": "sub_district"},
                    {"name": "village", "label": "Village", "type": "text", "required": True, "profile_field": "village"},
                ],
            },
            {
                "section_id": "land_info",
                "title": "Agricultural Landholding Details",
                "fields": [
                    {"name": "land_ownership_type", "label": "Ownership Type", "type": "select", "options": ["Single", "Joint"], "required": True, "default": "Single"},
                    {"name": "khasra_khatauni_no", "label": "Survey / Khasra / Khatauni Number", "type": "text", "required": True, "profile_field": "khasra_number"},
                    {"name": "land_area_acres", "label": "Cultivable Land Holding (Acres)", "type": "number", "required": True, "profile_field": "land_holding_acres"},
                    {"name": "land_transfer_date", "label": "Land Ownership Registration Date", "type": "date", "required": False, "profile_field": "land_registration_date"},
                ],
            },
            {
                "section_id": "bank_info",
                "title": "DBT Bank Account Details",
                "fields": [
                    {"name": "bank_account_number", "label": "Bank Account Number (Aadhaar Seeded)", "type": "text", "required": True, "profile_field": "bank_account_number"},
                    {"name": "ifsc_code", "label": "Bank Branch IFSC Code", "type": "text", "required": True, "profile_field": "bank_ifsc", "pattern": r"^[A-Z]{4}0[A-Z0-9]{6}$"},
                ],
            },
        ],
    },
    "KCC": {
        "scheme_code": "KCC",
        "title": "Kisan Credit Card (KCC) Loan Application Form",
        "form_supported": True,
        "official_portal": "https://agricoop.nic.in",
        "sections": [
            {
                "section_id": "applicant_info",
                "title": "Applicant Details",
                "fields": [
                    {"name": "applicant_name", "label": "Farmer Full Name", "type": "text", "required": True, "profile_field": "full_name"},
                    {"name": "age", "label": "Age in Years (18-75)", "type": "number", "required": True, "profile_field": "age"},
                    {"name": "gender", "label": "Gender", "type": "select", "options": ["MALE", "FEMALE", "OTHER"], "required": True, "profile_field": "gender"},
                    {"name": "aadhaar_number", "label": "Aadhaar Number", "type": "text", "required": True, "profile_field": "aadhaar_number"},
                    {"name": "mobile_number", "label": "Contact Mobile Number", "type": "text", "required": True, "profile_field": "phone_number"},
                    {"name": "state", "label": "State", "type": "text", "required": True, "profile_field": "state"},
                    {"name": "district", "label": "District", "type": "text", "required": True, "profile_field": "district"},
                    {"name": "village", "label": "Village", "type": "text", "required": True, "profile_field": "village"},
                ],
            },
            {
                "section_id": "farming_details",
                "title": "Cultivation & Crop Details",
                "fields": [
                    {"name": "farming_type", "label": "Farming Status", "type": "select", "options": ["Owner Cultivator", "Tenant Farmer", "Sharecropper", "Oral Lessee"], "required": True, "default": "Owner Cultivator"},
                    {"name": "cultivable_land_acres", "label": "Cultivable Land Area (Acres)", "type": "number", "required": True, "profile_field": "land_holding_acres"},
                    {"name": "crops_grown", "label": "Main Crops Cultivated (Kharif / Rabi)", "type": "text", "required": True, "placeholder": "e.g. Paddy, Wheat, Soybean, Sugarcane"},
                    {"name": "allied_activities", "label": "Allied Activities (Dairy/Poultry/Fisheries)", "type": "text", "required": False, "placeholder": "e.g. 2 Dairy Cows"},
                ],
            },
            {
                "section_id": "loan_requirements",
                "title": "Credit Facility Requested",
                "fields": [
                    {"name": "requested_credit_limit", "label": "Credit Limit Requested (₹)", "type": "number", "required": True, "placeholder": "e.g. 150000"},
                    {"name": "preferred_bank", "label": "Lending Institution / Bank", "type": "text", "required": True, "placeholder": "e.g. State Bank of India / Bank of Maharashtra"},
                    {"name": "branch_name", "label": "Home Branch Name", "type": "text", "required": True, "placeholder": "e.g. Pune Rural Branch"},
                    {"name": "existing_outstanding_debt", "label": "Existing Outstanding Agriculture Loan (₹)", "type": "number", "required": True, "default": 0},
                ],
            },
        ],
    },
    "PM-SVANIDHI": {
        "scheme_code": "PM-SVANIDHI",
        "title": "PM Street Vendor's AtmaNirbhar Nidhi Application",
        "form_supported": True,
        "official_portal": "https://pmsvanidhi.mohua.gov.in",
        "sections": [
            {
                "section_id": "vendor_profile",
                "title": "Street Vendor Profile",
                "fields": [
                    {"name": "vendor_name", "label": "Vendor Full Name", "type": "text", "required": True, "profile_field": "full_name"},
                    {"name": "gender", "label": "Gender", "type": "select", "options": ["MALE", "FEMALE", "OTHER"], "required": True, "profile_field": "gender"},
                    {"name": "aadhaar_number", "label": "12-Digit Aadhaar Number", "type": "text", "required": True, "profile_field": "aadhaar_number"},
                    {"name": "mobile_number", "label": "Mobile Number (Aadhaar linked)", "type": "text", "required": True, "profile_field": "phone_number"},
                    {"name": "state", "label": "State", "type": "text", "required": True, "profile_field": "state"},
                    {"name": "district", "label": "District / City", "type": "text", "required": True, "profile_field": "district"},
                ],
            },
            {
                "section_id": "vending_activity",
                "title": "Vending Details & ULB Certification",
                "fields": [
                    {"name": "vending_activity", "label": "Vending Activity Category", "type": "select", "options": ["Fruits & Vegetables", "Fast Food & Snacks", "Clothing & Apparel", "Electronics & Accessories", "Artisan / Handicraft", "Services (Barber / Cobbler)"], "required": True},
                    {"name": "vending_location_ulb", "label": "Urban Local Body (Municipal Corp / Municipality)", "type": "text", "required": True, "placeholder": "e.g. Municipal Corporation of Greater Mumbai / Lucknow Nagar Nigam"},
                    {"name": "ward_name_number", "label": "Vending Zone / Ward Name / Number", "type": "text", "required": True, "placeholder": "e.g. Ward 12, Market Area"},
                    {"name": "vending_proof_type", "label": "Vending Proof Document", "type": "select", "options": ["Certificate of Vending (CoV)", "Identity Card issued by ULB", "Letter of Recommendation (LoR) from ULB/TVC"], "required": True},
                    {"name": "certificate_number", "label": "Certificate / Identity / LoR Number", "type": "text", "required": True, "placeholder": "e.g. LOR/2026/89412"},
                ],
            },
            {
                "section_id": "loan_amount",
                "title": "Working Capital Loan Request",
                "fields": [
                    {"name": "loan_tranche", "label": "Loan Tranche", "type": "select", "options": ["1st Tranche (Up to ₹10,000)", "2nd Tranche (Up to ₹20,000)", "3rd Tranche (Up to ₹50,000)"], "required": True, "default": "1st Tranche (Up to ₹10,000)"},
                    {"name": "requested_amount", "label": "Requested Loan Amount (₹)", "type": "number", "required": True, "default": 10000},
                    {"name": "bank_account_number", "label": "DBT Bank Account Number", "type": "text", "required": True, "profile_field": "bank_account_number"},
                    {"name": "ifsc_code", "label": "Bank Branch IFSC Code", "type": "text", "required": True, "profile_field": "bank_ifsc"},
                ],
            },
        ],
    },
    "NSP-CSSS": {
        "scheme_code": "NSP-CSSS",
        "title": "Central Sector Scheme of Scholarship for College and University Students (NSP)",
        "form_supported": True,
        "official_portal": "https://scholarships.gov.in",
        "sections": [
            {
                "section_id": "student_info",
                "title": "Student Personal Details",
                "fields": [
                    {"name": "student_name", "label": "Student Full Name (as on Class 10/12 certificate)", "type": "text", "required": True, "profile_field": "full_name"},
                    {"name": "date_of_birth", "label": "Date of Birth", "type": "date", "required": True, "profile_field": "date_of_birth"},
                    {"name": "gender", "label": "Gender", "type": "select", "options": ["MALE", "FEMALE", "OTHER"], "required": True, "profile_field": "gender"},
                    {"name": "category", "label": "Category", "type": "select", "options": ["General", "OBC", "SC", "ST"], "required": True, "profile_field": "caste_category"},
                    {"name": "state_of_domicile", "label": "State of Domicile", "type": "text", "required": True, "profile_field": "state"},
                    {"name": "district", "label": "District", "type": "text", "required": True, "profile_field": "district"},
                    {"name": "aadhaar_number", "label": "12-Digit Aadhaar Number", "type": "text", "required": True, "profile_field": "aadhaar_number"},
                    {"name": "mobile_number", "label": "Mobile Number", "type": "text", "required": True, "profile_field": "phone_number"},
                ],
            },
            {
                "section_id": "academic_details",
                "title": "Class 12 Board Examination Details",
                "fields": [
                    {"name": "class_12_board", "label": "State / Central Examination Board", "type": "select", "options": ["State Board (MSBSHSE / UPMSP)", "CBSE", "CISCE", "Other State Board"], "required": True},
                    {"name": "class_12_roll_no", "label": "Class 12 Roll / Registration Number", "type": "text", "required": True, "placeholder": "e.g. M120984"},
                    {"name": "class_12_passing_year", "label": "Year of Passing Class 12", "type": "number", "required": True, "default": 2026},
                    {"name": "class_12_percentage", "label": "Class 12 Marks Percentage (%)", "type": "number", "required": True, "placeholder": "e.g. 88.5"},
                ],
            },
            {
                "section_id": "higher_education",
                "title": "Current College / University Enrolment",
                "fields": [
                    {"name": "college_university_name", "label": "College / University Name & AISHE Code", "type": "text", "required": True, "placeholder": "e.g. University of Mumbai / Fergusson College"},
                    {"name": "course_degree", "label": "Current Degree / Course", "type": "text", "required": True, "placeholder": "e.g. B.Sc. Computer Science / B.A. / B.Com / B.Tech"},
                    {"name": "annual_family_income", "label": "Gross Annual Family Income (₹)", "type": "number", "required": True, "profile_field": "annual_income"},
                    {"name": "bank_account_number", "label": "Aadhaar Seeded Bank Account Number", "type": "text", "required": True, "profile_field": "bank_account_number"},
                    {"name": "ifsc_code", "label": "Bank Branch IFSC Code", "type": "text", "required": True, "profile_field": "bank_ifsc"},
                ],
            },
        ],
    },
    "PMMVY": {
        "scheme_code": "PMMVY",
        "title": "Pradhan Mantri Matru Vandana Yojana Maternity Benefit Application",
        "form_supported": True,
        "official_portal": "https://pmmvy.wcd.gov.in",
        "sections": [
            {
                "section_id": "beneficiary_info",
                "title": "Beneficiary Pregnant / Lactating Mother Details",
                "fields": [
                    {"name": "beneficiary_name", "label": "Beneficiary Mother's Full Name", "type": "text", "required": True, "profile_field": "full_name"},
                    {"name": "age", "label": "Age in Years (Must be 19 or above)", "type": "number", "required": True, "profile_field": "age"},
                    {"name": "husband_name", "label": "Husband's Full Name", "type": "text", "required": True, "placeholder": "Husband's name as in Aadhaar"},
                    {"name": "state", "label": "State", "type": "text", "required": True, "profile_field": "state"},
                    {"name": "district", "label": "District", "type": "text", "required": True, "profile_field": "district"},
                    {"name": "aadhaar_number", "label": "Beneficiary's Aadhaar Number", "type": "text", "required": True, "profile_field": "aadhaar_number"},
                    {"name": "mobile_number", "label": "Mobile Number", "type": "text", "required": True, "profile_field": "phone_number"},
                ],
            },
            {
                "section_id": "pregnancy_details",
                "title": "Maternal & Child Health Details",
                "fields": [
                    {"name": "mcp_card_registration_number", "label": "MCP Card Registration Number (RCH Portal)", "type": "text", "required": True, "placeholder": "e.g. MCP-MH-2026-4421"},
                    {"name": "child_order", "label": "Child Order", "type": "select", "options": ["1st Living Child", "2nd Child (Eligible if Girl Child)"], "required": True, "default": "1st Living Child"},
                    {"name": "lmp_date", "label": "Last Menstrual Period (LMP) Date", "type": "date", "required": True},
                    {"name": "anc_date", "label": "First Ante-Natal Check-up (ANC) Date", "type": "date", "required": True},
                    {"name": "institutional_delivery_hospital", "label": "Public / Accredited Delivery Hospital", "type": "text", "required": False, "placeholder": "e.g. District Civil Hospital / PHC"},
                ],
            },
            {
                "section_id": "bank_info",
                "title": "Direct Benefit Transfer Account",
                "fields": [
                    {"name": "bank_account_number", "label": "Beneficiary Mother's Aadhaar Seeded Account", "type": "text", "required": True, "profile_field": "bank_account_number"},
                    {"name": "ifsc_code", "label": "Bank Branch IFSC Code", "type": "text", "required": True, "profile_field": "bank_ifsc"},
                ],
            },
        ],
    },
    "WIDOW-PENSION": {
        "scheme_code": "WIDOW-PENSION",
        "title": "Indira Gandhi National Widow Pension Scheme (IGNWPS / State Widow Pension)",
        "form_supported": True,
        "official_portal": "https://nsap.nic.in",
        "state_portals": {
            "Uttar Pradesh": "https://sspy-up.gov.in",
            "Maharashtra": "https://sjsa.maharashtra.gov.in",
            "Default": "https://nsap.nic.in",
        },
        "sections": [
            {
                "section_id": "widow_info",
                "title": "Applicant Personal Details",
                "fields": [
                    {"name": "beneficiary_name", "label": "Applicant Full Name", "type": "text", "required": True, "profile_field": "full_name"},
                    {"name": "age", "label": "Age in Years (Must be 40 to 79 for IGNWPS; 18+ for UP State)", "type": "number", "required": True, "profile_field": "age"},
                    {"name": "gender", "label": "Gender", "type": "select", "options": ["FEMALE"], "required": True, "default": "FEMALE"},
                    {"name": "marital_status", "label": "Marital Status", "type": "select", "options": ["Widowed"], "required": True, "default": "Widowed"},
                    {"name": "state", "label": "State of Residence", "type": "text", "required": True, "profile_field": "state"},
                    {"name": "district", "label": "District", "type": "text", "required": True, "profile_field": "district"},
                    {"name": "block_tehsil", "label": "Tehsil / Block / Ward", "type": "text", "required": True, "profile_field": "sub_district"},
                    {"name": "aadhaar_number", "label": "12-Digit Aadhaar Number", "type": "text", "required": True, "profile_field": "aadhaar_number"},
                    {"name": "mobile_number", "label": "Mobile Number", "type": "text", "required": True, "profile_field": "phone_number"},
                ],
            },
            {
                "section_id": "demise_info",
                "title": "Deceased Husband's Details & Statutory Proof",
                "fields": [
                    {"name": "deceased_husband_name", "label": "Late Husband's Full Name", "type": "text", "required": True, "placeholder": "e.g. Ramesh Kumar"},
                    {"name": "date_of_husband_demise", "label": "Date of Husband's Demise", "type": "date", "required": True},
                    {"name": "death_certificate_number", "label": "Husband's Death Certificate Registration Number", "type": "text", "required": True, "placeholder": "e.g. CRSO-2024-81729"},
                    {"name": "issuing_registrar", "label": "Death Certificate Issuing Authority", "type": "text", "required": True, "placeholder": "e.g. Registrar of Births & Deaths, Tehsil Sadar"},
                ],
            },
            {
                "section_id": "income_bpl_info",
                "title": "Income & Socio-Economic Assessment",
                "fields": [
                    {"name": "annual_family_income", "label": "Annual Household Income (₹) (Must be within state limit)", "type": "number", "required": True, "profile_field": "annual_income"},
                    {"name": "bpl_ration_card_number", "label": "BPL / Antyodaya / SECC Ration Card Number", "type": "text", "required": False, "placeholder": "e.g. BPL-UP-981245"},
                    {"name": "receiving_other_pension", "label": "Receiving any other Central/State Social Security Pension?", "type": "select", "options": ["No", "Yes"], "required": True, "default": "No"},
                ],
            },
            {
                "section_id": "bank_info",
                "title": "DBT Monthly Pension Bank Account",
                "fields": [
                    {"name": "bank_account_number", "label": "Aadhaar Seeded Single Bank Account Number", "type": "text", "required": True, "profile_field": "bank_account_number"},
                    {"name": "ifsc_code", "label": "Bank Branch IFSC Code", "type": "text", "required": True, "profile_field": "bank_ifsc"},
                ],
            },
        ],
    },
}

# Alias mapping
SCHEME_CODE_ALIASES: Dict[str, str] = {
    "PMKISAN": "PM-KISAN",
    "PM KISAN": "PM-KISAN",
    "KISAN CREDIT CARD": "KCC",
    "KISAN CREDIT": "KCC",
    "PMSVANIDHI": "PM-SVANIDHI",
    "PM SVANIDHI": "PM-SVANIDHI",
    "SVANIDHI": "PM-SVANIDHI",
    "NSP CSSS": "NSP-CSSS",
    "NSP": "NSP-CSSS",
    "CSSS": "NSP-CSSS",
    "MATRU VANDANA": "PMMVY",
    "WIDOW PENSION": "WIDOW-PENSION",
    "IGNWPS": "WIDOW-PENSION",
    "VIDHWA PENSION": "WIDOW-PENSION",
    "SANJAY GANDHI NIRADHAR": "WIDOW-PENSION",
    "NSAP WIDOW": "WIDOW-PENSION",
}


def get_form_schema_for_scheme(scheme_code_or_name: str) -> Optional[Dict[str, Any]]:
    """
    Returns the authoritative form schema for supported schemes.
    Returns None if the scheme does not have a supported pre-fill form schema.
    """
    cleaned = scheme_code_or_name.strip().upper()
    resolved_code = SCHEME_CODE_ALIASES.get(cleaned, cleaned)
    
    if resolved_code in SCHEME_FORM_SCHEMAS:
        return SCHEME_FORM_SCHEMAS[resolved_code]
    
    # Try substring matches
    for key, schema in SCHEME_FORM_SCHEMAS.items():
        if key in resolved_code or resolved_code in key:
            return schema
    
    if "WIDOW" in resolved_code or "VIDHWA" in resolved_code or "PENSION" in resolved_code and "WIDOW" in scheme_code_or_name.upper():
        return SCHEME_FORM_SCHEMAS["WIDOW-PENSION"]
        
    return None
