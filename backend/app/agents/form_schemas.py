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
        "title": "Aadhaar Card",
        "title_en": "Aadhaar Card",
        "title_hi": "आधार कार्ड",
        "title_mr": "आधार कार्ड",
        "why_needed": "Statutory identity and biometric verification under Section 7 of the Aadhaar Act for Direct Benefit Transfer (DBT).",
        "why_needed_en": "Statutory identity and biometric verification under Section 7 of the Aadhaar Act for Direct Benefit Transfer (DBT).",
        "why_needed_hi": "प्रत्यक्ष लाभ अंतरण (DBT) हेतु आधार अधिनियम की धारा 7 के तहत वैधानिक पहचान और बायोमेट्रिक सत्यापन।",
        "why_needed_mr": "थेट लाभ हस्तांतरण (DBT) साठी आधार कायद्याच्या कलम ७ अन्वये वैधानिक ओळख आणि बायोमेट्रिक पडताळणी.",
        "where_to_obtain": "Aadhaar Seva Kendra, authorized Post Office, nationalized Bank branch, or online via UIDAI.",
        "where_to_obtain_en": "Aadhaar Seva Kendra, authorized Post Office, nationalized Bank branch, or online via UIDAI.",
        "where_to_obtain_hi": "आधार सेवा केंद्र, अधिकृत डाकघर, राष्ट्रीयकृत बैंक शाखा या यूआईडीएआई (UIDAI) ऑनलाइन पोर्टल।",
        "where_to_obtain_mr": "आधार सेवा केंद्र, अधिकृत पोस्ट ऑफिस, राष्ट्रीयीकृत बँक शाखा किंवा UIDAI ऑनलाइन पोर्टल.",
        "issuing_authority": "Unique Identification Authority of India (UIDAI), Ministry of Electronics & IT.",
        "issuing_authority_en": "Unique Identification Authority of India (UIDAI), Ministry of Electronics & IT.",
        "issuing_authority_hi": "भारतीय विशिष्ट पहचान प्राधिकरण (UIDAI), इलेक्ट्रॉनिक्स एवं आईटी मंत्रालय।",
        "issuing_authority_mr": "भारतीय विशिष्ट ओळख प्राधिकरण (UIDAI), इलेक्ट्रॉनिक्स आणि माहिती तंत्रज्ञान मंत्रालय.",
        "official_url": "https://myaadhaar.uidai.gov.in",
        "verified_fee": "Free for new enrolment; ₹50 for demographic update, ₹100 for biometric update.",
        "expected_processing_days": "7 to 15 working days for PVC card or update generation.",
        "is_verified": True,
        "is_digitally_verifiable": True,
    },
    "income_certificate": {
        "title": "Income Certificate",
        "title_en": "Income Certificate",
        "title_hi": "आय प्रमाण पत्र",
        "title_mr": "उत्पन्न प्रमाणपत्र",
        "why_needed": "To establish household income compliance below scheme-specific eligibility ceiling.",
        "why_needed_en": "To establish household income compliance below scheme-specific eligibility ceiling.",
        "why_needed_hi": "योजना की पात्रता सीमा के तहत पारिवारिक आय प्रमाणित करने के लिए।",
        "why_needed_mr": "योजनेच्या विहित उत्पन्न मर्यादेखालील कौटुंबिक उत्पन्न सिद्ध करण्यासाठी.",
        "where_to_obtain": "Tehsil / Taluka Revenue Office, Common Service Center (CSC / Jan Seva Kendra / Aaple Sarkar), or State e-District portal.",
        "where_to_obtain_en": "Tehsil / Taluka Revenue Office, Common Service Center (CSC / Jan Seva Kendra / Aaple Sarkar), or State e-District portal.",
        "where_to_obtain_hi": "तहसील / ब्लॉक कार्यालय, सीएससी (CSC) या राज्य ई-डिस्ट्रिक्ट पोर्टल।",
        "where_to_obtain_mr": "तहसील / तालुका महसूल कार्यालय, आपले सरकार सेवा केंद्र किंवा राज्य ई-डिस्ट्रिक्ट पोर्टल.",
        "issuing_authority": "Revenue Department (Tahsildar / Sub-Divisional Magistrate / Sub-Divisional Officer).",
        "issuing_authority_en": "Revenue Department (Tahsildar / Sub-Divisional Magistrate / Sub-Divisional Officer).",
        "issuing_authority_hi": "राजस्व विभाग (तहसीलदार / उप-विभागीय मजिस्ट्रेट / एसडीएम)।",
        "issuing_authority_mr": "महसूल विभाग (तहसीलदार / उपविभागीय अधिकारी / प्रांत अधिकारी).",
        "official_url": "https://services.india.gov.in",
        "verified_fee": "₹15 to ₹30 at authorized CSC / state e-District service portal.",
        "expected_processing_days": "7 to 14 working days depending on state citizen service guarantee charters.",
        "is_verified": True,
        "is_digitally_verifiable": True,
    },
    "death_certificate": {
        "title": "Death Certificate of Husband",
        "title_en": "Death Certificate of Husband",
        "title_hi": "पति का मृत्यु प्रमाण पत्र",
        "title_mr": "पतीचे मृत्यू प्रमाणपत्र",
        "why_needed": "Mandatory statutory proof of husband's demise required for Indira Gandhi National Widow Pension Scheme (IGNWPS) and State Widow Pension.",
        "why_needed_en": "Mandatory statutory proof of husband's demise required for Indira Gandhi National Widow Pension Scheme (IGNWPS) and State Widow Pension.",
        "why_needed_hi": "विधवा पेंशन योजना के लिए पति के देहांत का अनिवार्य वैधानिक प्रमाण।",
        "why_needed_mr": "विधवा पेन्शन योजनेसाठी पतीच्या निधनाचा अनिवार्य वैधानिक पुरावा.",
        "where_to_obtain": "Urban: Municipal Corporation / Municipality Registrar. Rural: Gram Panchayat / Block Development Office / Civil Registration System.",
        "where_to_obtain_en": "Urban: Municipal Corporation / Municipality Registrar. Rural: Gram Panchayat / Block Development Office / Civil Registration System.",
        "where_to_obtain_hi": "शहरी: नगर निगम / नगर पालिका। ग्रामीण: ग्राम पंचायत / ब्लॉक विकास कार्यालय (CRS पोर्टल)।",
        "where_to_obtain_mr": "शहरी: महानगरपालिका / नगरपालिका निबंधक. ग्रामीण: ग्रामपंचायत / गट विकास अधिकारी.",
        "issuing_authority": "Registrar of Births and Deaths (Office of the Registrar General of India / State Health & Family Welfare).",
        "issuing_authority_en": "Registrar of Births and Deaths (Office of the Registrar General of India / State Health & Family Welfare).",
        "issuing_authority_hi": "जन्म एवं मृत्यु रजिस्ट्रार (स्वास्थ्य एवं परिवार कल्याण विभाग)।",
        "issuing_authority_mr": "जन्म आणि मृत्यू निबंधक (आरोग्य व कुटुंब कल्याण विभाग).",
        "official_url": "https://crsorgi.gov.in",
        "verified_fee": "Free if registered within 21 days; ₹10–₹50 search/late fee if delayed.",
        "expected_processing_days": "7 to 10 working days from application submission.",
        "is_verified": True,
        "is_digitally_verifiable": True,
    },
    "land_records": {
        "title": "Land Ownership Records (7/12 / Khasra-Khatauni / RoR)",
        "title_en": "Land Ownership Records (7/12 / Khasra-Khatauni / RoR)",
        "title_hi": "भूमि स्वामित्व रिकॉर्ड (खसरा-खतौनी / 7/12 / RoR)",
        "title_mr": "जमीन मालकी नोंद (७/१२ व ८-अ उतारा / RoR)",
        "why_needed": "Official verification of cultivable landholding, survey number, and farmer ownership classification.",
        "why_needed_en": "Official verification of cultivable landholding, survey number, and farmer ownership classification.",
        "why_needed_hi": "कृषि भूमि का रकबा, खसरा संख्या और किसान स्वामित्व की आधिकारिक पुष्टि हेतु।",
        "why_needed_mr": "शेतजमिनीचे क्षेत्रफळ, गट क्रमांक आणि शेतकरी मालकी हक्काची अधिकृत खात्री करण्यासाठी.",
        "where_to_obtain": "Tehsil Office, Talathi / Patwari Office, or computerized State Land Records portal (e.g. Mahabhumi, UP Bhulekh).",
        "where_to_obtain_en": "Tehsil Office, Talathi / Patwari Office, or computerized State Land Records portal (e.g. Mahabhumi, UP Bhulekh).",
        "where_to_obtain_hi": "तहसील कार्यालय, लेखपाल/पटवारी या राज्य भूलेख पोर्टल (उदा. महाभूमि, यूपी भूलेख)।",
        "where_to_obtain_mr": "तलाठी कार्यालय, तहसील कार्यालय किंवा महाभूमी (mahabhumi.gov.in) डिजिटल पोर्टल.",
        "issuing_authority": "Revenue & Land Reforms Department / Directorate of Land Records.",
        "issuing_authority_en": "Revenue & Land Reforms Department / Directorate of Land Records.",
        "issuing_authority_hi": "राजस्व एवं भूमि सुधार विभाग / भू-अभिलेख निदेशालय।",
        "issuing_authority_mr": "महसूल आणि भूमी अभिलेख विभाग.",
        "official_url": "https://dilrmp.gov.in",
        "verified_fee": "Free online viewing; ₹15 to ₹30 for digitally signed government-certified copy.",
        "expected_processing_days": "Instant digital download if computerized; 3 to 5 days at local Talathi/Tehsil office.",
        "is_verified": True,
        "is_digitally_verifiable": True,
    },
    "bank_passbook": {
        "title": "Bank Passbook / Cancelled Cheque",
        "title_en": "Bank Passbook / Cancelled Cheque",
        "title_hi": "बैंक पासबुक / रद्द चेक",
        "title_mr": "बँक पासबुक / रद्द केलेला धनादेश",
        "why_needed": "Verification of Aadhaar-seeded DBT active bank account number and branch IFSC code for direct cash transfer.",
        "why_needed_en": "Verification of Aadhaar-seeded DBT active bank account number and branch IFSC code for direct cash transfer.",
        "why_needed_hi": "प्रत्यक्ष नकद अंतरण हेतु आधार-सीडेड सक्रिय बैंक खाता संख्या और आईएफएससी कोड का सत्यापन।",
        "why_needed_mr": "थेट रोख अनुदानासाठी आधार-संलग्न सक्रिय बँक खाते क्रमांक आणि IFSC कोडची पडताळणी.",
        "where_to_obtain": "Home branch of Scheduled Commercial Bank, Regional Rural Bank (RRB), District Co-operative Bank, or India Post Payments Bank.",
        "where_to_obtain_en": "Home branch of Scheduled Commercial Bank, Regional Rural Bank (RRB), District Co-operative Bank, or India Post Payments Bank.",
        "where_to_obtain_hi": "संबंधित बैंक शाखा (वाणिज्यिक बैंक, ग्रामीण बैंक या डाकघर भुगतान बैंक)।",
        "where_to_obtain_mr": "तुमचे खाते असलेल्या राष्ट्रीयीकृत बँक, ग्रामीण बँक किंवा पोस्ट पेमेंट बँकेची शाखा.",
        "issuing_authority": "Account-holding Banking Institution (RBI regulated).",
        "issuing_authority_en": "Account-holding Banking Institution (RBI regulated).",
        "issuing_authority_hi": "संबंधित बैंक संस्थान (भारतीय रिज़र्व बैंक द्वारा विनियमित)।",
        "issuing_authority_mr": "संबंधित बँक संस्था (RBI नियंत्रित).",
        "official_url": "https://financialservices.gov.in",
        "verified_fee": "Free for initial passbook; nominal replacement fee if lost.",
        "expected_processing_days": "Instant over the counter at bank branch.",
        "is_verified": True,
        "is_digitally_verifiable": True,
    },
    "vending_certificate": {
        "title": "Certificate of Vending / Letter of Recommendation (LoR)",
        "title_en": "Certificate of Vending / Letter of Recommendation (LoR)",
        "title_hi": "वेंडिंग प्रमाण पत्र / सिफारिश पत्र (LoR)",
        "title_mr": "विक्री प्रमाणपत्र / शिफारस पत्र (LoR)",
        "why_needed": "Proof of street vending activity required under the Street Vendors Act, 2014 for PM-SVANidhi micro-credit.",
        "why_needed_en": "Proof of street vending activity required under the Street Vendors Act, 2014 for PM-SVANidhi micro-credit.",
        "why_needed_hi": "पीएम स्वनिधि ऋण हेतु स्ट्रीट वेंडर्स अधिनियम 2014 के तहत पथविक्रेता होने का वैधानिक प्रमाण।",
        "why_needed_mr": "पीएम स्वनिधी कर्जासाठी पथविक्रेता कायदा २०१४ अन्वये फेरीवाला असण्याचा अधिकृत पुरावा.",
        "where_to_obtain": "Local Municipal Corporation / Urban Local Body (ULB) office or Town Vending Committee (TVC).",
        "where_to_obtain_en": "Local Municipal Corporation / Urban Local Body (ULB) office or Town Vending Committee (TVC).",
        "where_to_obtain_hi": "स्थानीय नगर निगम / नगर पालिका कार्यालय या टाउन वेंडिंग कमेटी (TVC)।",
        "where_to_obtain_mr": "स्थानिक महानगरपालिका / नगरपालिका कार्यालय किंवा टाऊन वेंडिंग समिती (TVC).",
        "issuing_authority": "Urban Local Body (ULB) / Town Vending Committee (TVC).",
        "issuing_authority_en": "Urban Local Body (ULB) / Town Vending Committee (TVC).",
        "issuing_authority_hi": "शहरी स्थानीय निकाय (ULB) / टाउन वेंडिंग कमेटी (TVC)।",
        "issuing_authority_mr": "शहरी स्थानिक स्वराज्य संस्था (ULB) / टाऊन वेंडिंग समिती.",
        "official_url": "https://pmsvanidhi.mohua.gov.in",
        "verified_fee": "Free as prescribed under Street Vendors (Protection of Livelihood and Regulation of Street Vending) Act.",
        "expected_processing_days": "15 to 30 days following ULB survey or TVC recommendation meeting.",
        "is_verified": True,
        "is_digitally_verifiable": False,
    },
    "mcp_card": {
        "title": "Mother and Child Protection (MCP) Card",
        "title_en": "Mother and Child Protection (MCP) Card",
        "title_hi": "मातृ एवं बाल सुरक्षा (MCP) कार्ड",
        "title_mr": "माता आणि बाल संरक्षण (MCP) कार्ड",
        "why_needed": "Statutory record of early pregnancy registration, Ante-Natal Check-ups (ANC), and institutional delivery under PMMVY.",
        "why_needed_en": "Statutory record of early pregnancy registration, Ante-Natal Check-ups (ANC), and institutional delivery under PMMVY.",
        "why_needed_hi": "मातृ वंदना योजना (PMMVY) हेतु प्रारंभिक गर्भावस्था पंजीकरण और स्वास्थ्य जांच (ANC) का वैधानिक रिकॉर्ड।",
        "why_needed_mr": "मातृ वंदना योजनेसाठी (PMMVY) गर्भधारणा नोंदणी आणि आरोग्य तपासणीचा (ANC) अधिकृत पुरावा.",
        "where_to_obtain": "Nearest Primary Health Centre (PHC), Sub-Centre, Anganwadi Centre, or Government Hospital.",
        "where_to_obtain_en": "Nearest Primary Health Centre (PHC), Sub-Centre, Anganwadi Centre, or Government Hospital.",
        "where_to_obtain_hi": "नजदीकी प्राथमिक स्वास्थ्य केंद्र (PHC), उप-केंद्र, आंगनवाड़ी केंद्र या सरकारी अस्पताल।",
        "where_to_obtain_mr": "जवळचे प्राथमिक आरोग्य केंद्र (PHC), उपकेंद्र, अंगणवाडी किंवा शासकीय रुग्णालय.",
        "issuing_authority": "Ministry of Health & Family Welfare / Ministry of Women & Child Development.",
        "issuing_authority_en": "Ministry of Health & Family Welfare / Ministry of Women & Child Development.",
        "issuing_authority_hi": "स्वास्थ्य एवं परिवार कल्याण मंत्रालय / महिला एवं बाल विकास मंत्रालय।",
        "issuing_authority_mr": "सार्वजनिक आरोग्य विभाग / महिला व बाल विकास विभाग.",
        "official_url": "https://pmmvy.wcd.gov.in",
        "verified_fee": "Completely Free at all public healthcare facilities.",
        "expected_processing_days": "Issued immediately upon first ANC registration.",
        "is_verified": True,
        "is_digitally_verifiable": False,
    },
    "marksheet_12th": {
        "title": "Class 12 Passing Marksheet & Certificate",
        "title_en": "Class 12 Passing Marksheet & Certificate",
        "title_hi": "12वीं कक्षा की अंकतालिका एवं प्रमाण पत्र",
        "title_mr": "१२वी उत्तीर्ण गुणपत्रिका व प्रमाणपत्र",
        "why_needed": "Academic merit verification (above 80th percentile) and roll number validation for National Scholarship Scheme (NSP-CSSS).",
        "why_needed_en": "Academic merit verification (above 80th percentile) and roll number validation for National Scholarship Scheme (NSP-CSSS).",
        "why_needed_hi": "राष्ट्रीय छात्रवृत्ति (NSP) हेतु 80वें पर्सेंटाइल से अधिक शैक्षणिक योग्यता और अनुक्रमांक सत्यापन।",
        "why_needed_mr": "राष्ट्रीय शिष्यवृत्तीसाठी (NSP) ८० पर्सेंटाईलपेक्षा जास्त गुण आणि परीक्षा बैठक क्रमांकाची पडताळणी.",
        "where_to_obtain": "Respective Higher Secondary School / Junior College, or instant fetch via DigiLocker.",
        "where_to_obtain_en": "Respective Higher Secondary School / Junior College, or instant fetch via DigiLocker.",
        "where_to_obtain_hi": "संबंधित उच्च माध्यमिक विद्यालय / कॉलेज अथवा डिजिलॉकर (DigiLocker) द्वारा।",
        "where_to_obtain_mr": "संबंधित कनिष्ठ महाविद्यालय / शाळा किंवा डिजीलॉकर (DigiLocker) द्वारे.",
        "issuing_authority": "State Secondary and Higher Secondary Education Board, CBSE, or CISCE.",
        "issuing_authority_en": "State Secondary and Higher Secondary Education Board, CBSE, or CISCE.",
        "issuing_authority_hi": "राज्य माध्यमिक एवं उच्च माध्यमिक शिक्षा बोर्ड, सीबीएसई (CBSE) या सीआईएससीई।",
        "issuing_authority_mr": "महाराष्ट्र राज्य माध्यमिक व उच्च माध्यमिक शिक्षण मंडळ किंवा CBSE.",
        "official_url": "https://digilocker.gov.in",
        "verified_fee": "Free via DigiLocker; original copy provided by school.",
        "expected_processing_days": "Instant on DigiLocker; original issued as per board schedule.",
        "is_verified": True,
        "is_digitally_verifiable": True,
    },
    "caste_certificate": {
        "title": "Caste / Category Certificate",
        "title_en": "Caste / Category Certificate",
        "title_hi": "जाति प्रमाण पत्र",
        "title_mr": "जातीचे प्रमाणपत्र",
        "why_needed": "Verification of SC/ST/OBC category entitlement for targeted welfare benefits and fee exemptions.",
        "why_needed_en": "Verification of SC/ST/OBC category entitlement for targeted welfare benefits and fee exemptions.",
        "why_needed_hi": "अनुसूचित जाति/जनजाति/अन्य पिछड़ा वर्ग हेतु आरक्षित सरकारी योजनाओं और शुल्क छूट का सत्यापन।",
        "why_needed_mr": "SC/ST/OBC प्रवर्गातील आरक्षित योजनांचे लाभ आणि सवलती मिळवण्यासाठी अधिकृत पडताळणी.",
        "where_to_obtain": "Tehsil / Taluka Office, Sub-Divisional Magistrate (SDM) Office, CSC, or State e-District portal.",
        "where_to_obtain_en": "Tehsil / Taluka Office, Sub-Divisional Magistrate (SDM) Office, CSC, or State e-District portal.",
        "where_to_obtain_hi": "तहसील कार्यालय, उप-विभागीय मजिस्ट्रेट (SDM) कार्यालय, सीएससी या ई-डिस्ट्रिक्ट पोर्टल।",
        "where_to_obtain_mr": "तहसील / उपविभागीय अधिकारी (SDO) कार्यालय, आपले सरकार केंद्र किंवा ई-डिस्ट्रिक्ट पोर्टल.",
        "issuing_authority": "Revenue Department (SDM / Sub-Collector / Tahsildar).",
        "issuing_authority_en": "Revenue Department (SDM / Sub-Collector / Tahsildar).",
        "issuing_authority_hi": "राजस्व विभाग (एसडीएम / उप-कलेक्टर / तहसीलदार)।",
        "issuing_authority_mr": "महसूल विभाग (उपविभागीय अधिकारी / तहसीलदार).",
        "official_url": "https://services.india.gov.in",
        "verified_fee": "₹15 to ₹30 at CSC / e-District.",
        "expected_processing_days": "15 to 21 working days.",
        "is_verified": True,
        "is_digitally_verifiable": True,
    },
    "domicile_certificate": {
        "title": "Domicile / Residence Certificate",
        "title_en": "Domicile / Residence Certificate",
        "title_hi": "निवास / अधिवास प्रमाण पत्र",
        "title_mr": "अधिवास / रहिवासी प्रमाणपत्र",
        "why_needed": "Proof of permanent residency in the scheme jurisdiction (e.g. Uttar Pradesh or Maharashtra).",
        "why_needed_en": "Proof of permanent residency in the scheme jurisdiction (e.g. Uttar Pradesh or Maharashtra).",
        "why_needed_hi": "संबंधित राज्य (जैसे महाराष्ट्र या उत्तर प्रदेश) के स्थायी निवासी होने का वैधानिक प्रमाण।",
        "why_needed_mr": "महाराष्ट्र राज्याचे कायमस्वरूपी रहिवासी असल्याचा अधिकृत अधिवास पुरावा.",
        "where_to_obtain": "Tehsil Office, Sub-Divisional Magistrate Office, or State e-District portal.",
        "where_to_obtain_en": "Tehsil Office, Sub-Divisional Magistrate Office, or State e-District portal.",
        "where_to_obtain_hi": "तहसील कार्यालय, उप-विभागीय मजिस्ट्रेट कार्यालय या राज्य ई-डिस्ट्रिक्ट पोर्टल।",
        "where_to_obtain_mr": "तहसील कार्यालय, सेतू सुविधा केंद्र किंवा आपले सरकार पोर्टल.",
        "issuing_authority": "Revenue Department (SDM / Tahsildar).",
        "issuing_authority_en": "Revenue Department (SDM / Tahsildar).",
        "issuing_authority_hi": "राजस्व विभाग (एसडीएम / तहसीलदार)।",
        "issuing_authority_mr": "महसूल विभाग (तहसीलदार / उपविभागीय अधिकारी).",
        "official_url": "https://services.india.gov.in",
        "verified_fee": "₹15 to ₹30 at CSC / e-District.",
        "expected_processing_days": "7 to 15 working days.",
        "is_verified": True,
        "is_digitally_verifiable": True,
    },
    "ration_card": {
        "title": "Ration Card (BPL / Antyodaya / Priority Household)",
        "title_en": "Ration Card (BPL / Antyodaya / Priority Household)",
        "title_hi": "राशन कार्ड (बीपीएल / अंत्योदय / प्राथमिकता गृहस्थी)",
        "title_mr": "रेशन कार्ड (पिवळे / केशरी / अंत्योदय / प्राधान्य कुटुंब)",
        "why_needed": "Proof of household socioeconomic classification and poverty line status.",
        "why_needed_en": "Proof of household socioeconomic classification and poverty line status.",
        "why_needed_hi": "पारिवारिक सामाजिक-आर्थिक स्थिति और गरीबी रेखा श्रेणी का आधिकारिक प्रमाण।",
        "why_needed_mr": "कुटुंबाची सामाजिक-आर्थिक वर्गवारी आणि दारिद्र्यरेषेखालील स्थितीचा पुरावा.",
        "where_to_obtain": "District Food and Civil Supplies Office or State Food Portal / CSC.",
        "where_to_obtain_en": "District Food and Civil Supplies Office or State Food Portal / CSC.",
        "where_to_obtain_hi": "जिला खाद्य एवं रसद कार्यालय अथवा राज्य खाद्य सुरक्षा पोर्टल / सीएससी।",
        "where_to_obtain_mr": "जिल्हा पुरवठा अधिकारी कार्यालय किंवा अन्न व नागरी पुरवठा पोर्टल / स्वस्त धान्य दुकान.",
        "issuing_authority": "Department of Food, Civil Supplies & Consumer Protection.",
        "issuing_authority_en": "Department of Food, Civil Supplies & Consumer Protection.",
        "issuing_authority_hi": "खाद्य, नागरिक आपूर्ति एवं उपभोक्ता संरक्षण विभाग।",
        "issuing_authority_mr": "अन्न, नागरी पुरवठा व ग्राहक संरक्षण विभाग.",
        "official_url": "https://nfsa.gov.in",
        "verified_fee": "₹10 to ₹50 as per state notification.",
        "expected_processing_days": "15 to 30 working days.",
        "is_verified": True,
        "is_digitally_verifiable": True,
    },
    "job_card": {
        "title": "MGNREGA Job Card",
        "title_en": "MGNREGA Job Card",
        "title_hi": "मनरेगा जॉब कार्ड",
        "title_mr": "मनरेगा जॉब कार्ड",
        "why_needed": "Required under PMAY-G only for beneficiaries registered under MGNREGA seeking 90/95 days unskilled wage convergence.",
        "why_needed_en": "Required under PMAY-G only for beneficiaries registered under MGNREGA seeking 90/95 days unskilled wage convergence.",
        "why_needed_hi": "केवल मनरेगा में पंजीकृत लाभार्थियों के लिए 90/95 दिनों की अकुशल मजदूरी सहायता जोड़ने हेतु आवश्यक।",
        "why_needed_mr": "केवळ मनरेगा अंतर्गत नोंदणीकृत लाभार्थ्यांसाठी ९०/९५ दिवसांच्या अकुशल मजुरीच्या संलग्नतेसाठी आवश्यक.",
        "where_to_obtain": "Local Gram Panchayat office or Block Development Officer (BDO) via nrega.nic.in.",
        "where_to_obtain_en": "Local Gram Panchayat office or Block Development Officer (BDO) via nrega.nic.in.",
        "where_to_obtain_hi": "स्थानीय ग्राम पंचायत कार्यालय या ब्लॉक विकास अधिकारी (BDO) कार्यालय।",
        "where_to_obtain_mr": "स्थानिक ग्रामपंचायत कार्यालय किंवा पंचायत समिती (गटविकास अधिकारी कार्यालय).",
        "issuing_authority": "Gram Panchayat / Block Programme Officer (MGNREGA).",
        "issuing_authority_en": "Gram Panchayat / Block Programme Officer (MGNREGA).",
        "issuing_authority_hi": "ग्राम पंचायत / प्रखंड कार्यक्रम अधिकारी (मनरेगा)।",
        "issuing_authority_mr": "ग्रामपंचायत / गट कार्यक्रम अधिकारी (मनरेगा).",
        "official_url": "https://nrega.nic.in",
        "verified_fee": "Free under Mahatma Gandhi NREGA Act.",
        "expected_processing_days": "Within 15 days of application to Gram Panchayat.",
        "is_verified": True,
        "is_digitally_verifiable": True,
    },
    "land_possession": {
        "title": "Homestead Land Title / Gram Panchayat Allotment Certificate",
        "title_en": "Homestead Land Title / Gram Panchayat Allotment Certificate",
        "title_hi": "आवासीय भूमि स्वामित्व / ग्राम पंचायत आवंटन प्रमाण पत्र",
        "title_mr": "निवासी जागा मालकी / ग्रामपंचायत वाटप प्रमाणपत्र",
        "why_needed": "Proof of homestead plot ownership or Gram Panchayat land allotment for house construction (not required prior to landless state allotment).",
        "why_needed_en": "Proof of homestead plot ownership or Gram Panchayat land allotment for house construction (not required prior to landless state allotment).",
        "why_needed_hi": "आवास निर्माण हेतु आवासीय भूमि स्वामित्व या ग्राम पंचायत आवंटन का प्रमाण (भूमिहीन आवेदकों के लिए आवंटन से पूर्व अनिवार्य नहीं)।",
        "why_needed_mr": "घर बांधकामासाठी निवासी जागेची मालकी किंवा ग्रामपंचायत वाटप प्रमाणपत्र (भूमिहीन अर्जदारांना जागा वाटपापूर्वी अनिवार्य नाही).",
        "where_to_obtain": "Tehsil Revenue Office (7/12 / Patta) or Gram Panchayat Allotment Register.",
        "where_to_obtain_en": "Tehsil Revenue Office (7/12 / Patta) or Gram Panchayat Allotment Register.",
        "where_to_obtain_hi": "तहसील राजस्व कार्यालय (खतौनी/पट्टा) अथवा ग्राम पंचायत आवंटन पंजिका।",
        "where_to_obtain_mr": "तहसीलदार कार्यालय (७/१२ उतारा / पट्टा) किंवा ग्रामपंचायत जागा वाटप नोंदवही.",
        "issuing_authority": "Revenue Department / Gram Panchayat.",
        "issuing_authority_en": "Revenue Department / Gram Panchayat.",
        "issuing_authority_hi": "राजस्व विभाग / ग्राम पंचायत।",
        "issuing_authority_mr": "महसूल विभाग / ग्रामपंचायत.",
        "official_url": "https://pmayg.nic.in",
        "verified_fee": "Nominal revenue extract fee (₹15–₹30) or free for Gram Panchayat allotment.",
        "expected_processing_days": "7 to 15 working days.",
        "is_verified": True,
        "is_digitally_verifiable": True,
    },
}


def get_document_sourcing_info(doc_name: str, lang: str = "en") -> Dict[str, Any]:
    """
    Retrieves verified sourcing information for a document in the requested language ('en', 'hi', 'mr').
    Ensures 100% clean, non-mixed titles, descriptions, and issuing authorities.
    """
    norm_key = doc_name.lower().replace(" ", "_").replace("-", "_").replace("/", "_")
    matched_entry: Optional[Dict[str, Any]] = None

    for key, info in DOCUMENT_SOURCING_REGISTRY.items():
        if key in norm_key or norm_key in key:
            matched_entry = info
            break
        if "death" in norm_key and "husband" in norm_key and key == "death_certificate":
            matched_entry = info
            break
        if ("income" in norm_key or "aay" in norm_key or "utpann" in norm_key) and key == "income_certificate":
            matched_entry = info
            break
        if ("aadhaar" in norm_key or "aadhar" in norm_key) and key == "aadhaar_card":
            matched_entry = info
            break
        if ("job" in norm_key or "mgnrega" in norm_key) and key == "job_card":
            matched_entry = info
            break
        if ("possession" in norm_key or "allotment" in norm_key) and key == "land_possession":
            matched_entry = info
            break
        if ("land" in norm_key or "khasra" in norm_key or "7/12" in norm_key or "khatauni" in norm_key) and key == "land_records":
            matched_entry = info
            break
        if ("bank" in norm_key or "passbook" in norm_key) and key == "bank_passbook":
            matched_entry = info
            break
        if ("vending" in norm_key or "lor" in norm_key or "vendor" in norm_key) and key == "vending_certificate":
            matched_entry = info
            break
        if ("mcp" in norm_key or "mother" in norm_key or "pregnancy" in norm_key) and key == "mcp_card":
            matched_entry = info
            break
        if ("12th" in norm_key or "marksheet" in norm_key or "scholarship" in norm_key) and key == "marksheet_12th":
            matched_entry = info
            break
        if ("caste" in norm_key or "jati" in norm_key) and key == "caste_certificate":
            matched_entry = info
            break
        if ("domicile" in norm_key or "niwas" in norm_key or "residence" in norm_key) and key == "domicile_certificate":
            matched_entry = info
            break

    if not matched_entry:
        # Honest transparency: never fabricate fees, URLs, or processing times for unknown documents.
        unavail_label = (
            "अधिकृत माहिती उपलब्ध नाही"
            if lang == "mr"
            else "आधिकारिक जानकारी उपलब्ध नहीं"
            if lang == "hi"
            else "Information unavailable"
        )
        return {
            "title": doc_name.replace("_", " ").title(),
            "why_needed": None,
            "where_to_obtain": None,
            "issuing_authority": None,
            "official_url": None,
            "verified_fee": None,
            "expected_processing_days": None,
            "availability_note": unavail_label,
            "is_verified": False,
            "is_digitally_verifiable": False,
            "info_unavailable": True,
        }

    # Format cleanly according to language
    res = dict(matched_entry)
    lang_code = lang if lang in ("mr", "hi", "en") else "en"
    if f"title_{lang_code}" in matched_entry:
        res["title"] = matched_entry[f"title_{lang_code}"]
    if f"why_needed_{lang_code}" in matched_entry:
        res["why_needed"] = matched_entry[f"why_needed_{lang_code}"]
    if f"where_to_obtain_{lang_code}" in matched_entry:
        res["where_to_obtain"] = matched_entry[f"where_to_obtain_{lang_code}"]
    if f"issuing_authority_{lang_code}" in matched_entry:
        res["issuing_authority"] = matched_entry[f"issuing_authority_{lang_code}"]

    return res


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
                    {"name": "land_ownership_type", "label": "Ownership Type", "type": "select", "options": ["Single", "Joint"], "required": True, "profile_field": "land_ownership_type"},
                    {"name": "khasra_khatauni_no", "label": "Survey / Khasra / Khatauni Number", "type": "text", "required": True, "profile_field": "khasra_number"},
                    {"name": "land_area_acres", "label": "Cultivable Land Holding (Acres)", "type": "number", "required": True, "profile_field": "land_holding_acres"},
                    {"name": "land_transfer_date", "label": "Land Ownership Registration Date", "type": "date", "required": False, "profile_field": "land_registration_date"},
                ],
            },
            {
                "section_id": "bank_info",
                "title": "DBT Bank Account Details",
                "fields": [
                    {"name": "bank_account_number", "label": "Bank Account Number (Aadhaar Seeded)", "type": "text", "required": True, "profile_field": "bank_account_number", "pattern": r"^[0-9]{9,18}$"},
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
                    {"name": "aadhaar_number", "label": "Aadhaar Number", "type": "text", "required": True, "profile_field": "aadhaar_number", "pattern": r"^[0-9]{12}$"},
                    {"name": "mobile_number", "label": "Contact Mobile Number", "type": "text", "required": True, "profile_field": "phone_number", "pattern": r"^[6-9][0-9]{9}$"},
                    {"name": "state", "label": "State", "type": "text", "required": True, "profile_field": "state"},
                    {"name": "district", "label": "District", "type": "text", "required": True, "profile_field": "district"},
                    {"name": "village", "label": "Village", "type": "text", "required": True, "profile_field": "village"},
                ],
            },
            {
                "section_id": "farming_details",
                "title": "Cultivation & Crop Details",
                "fields": [
                    {"name": "farming_type", "label": "Farming Status", "type": "select", "options": ["Owner Cultivator", "Tenant Farmer", "Sharecropper", "Oral Lessee"], "required": True},
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
                    {"name": "existing_outstanding_debt", "label": "Existing Outstanding Agriculture Loan (₹)", "type": "number", "required": True, "placeholder": "Enter 0 if none"},
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
                    {"name": "aadhaar_number", "label": "12-Digit Aadhaar Number", "type": "text", "required": True, "profile_field": "aadhaar_number", "pattern": r"^[0-9]{12}$"},
                    {"name": "mobile_number", "label": "Mobile Number (Aadhaar linked)", "type": "text", "required": True, "profile_field": "phone_number", "pattern": r"^[6-9][0-9]{9}$"},
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
                    {"name": "loan_tranche", "label": "Loan Tranche", "type": "select", "options": ["1st Tranche (Up to ₹10,000)", "2nd Tranche (Up to ₹20,000)", "3rd Tranche (Up to ₹50,000)"], "required": True},
                    {"name": "requested_amount", "label": "Requested Loan Amount (₹)", "type": "number", "required": True, "placeholder": "e.g. 10000"},
                    {"name": "bank_account_number", "label": "DBT Bank Account Number", "type": "text", "required": True, "profile_field": "bank_account_number", "pattern": r"^[0-9]{9,18}$"},
                    {"name": "ifsc_code", "label": "Bank Branch IFSC Code", "type": "text", "required": True, "profile_field": "bank_ifsc", "pattern": r"^[A-Z]{4}0[A-Z0-9]{6}$"},
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
                    {"name": "aadhaar_number", "label": "12-Digit Aadhaar Number", "type": "text", "required": True, "profile_field": "aadhaar_number", "pattern": r"^[0-9]{12}$"},
                    {"name": "mobile_number", "label": "Mobile Number", "type": "text", "required": True, "profile_field": "phone_number", "pattern": r"^[6-9][0-9]{9}$"},
                ],
            },
            {
                "section_id": "academic_details",
                "title": "Class 12 Board Examination Details",
                "fields": [
                    {"name": "class_12_board", "label": "State / Central Examination Board", "type": "select", "options": ["State Board (MSBSHSE / UPMSP)", "CBSE", "CISCE", "Other State Board"], "required": True},
                    {"name": "class_12_roll_no", "label": "Class 12 Roll / Registration Number", "type": "text", "required": True, "placeholder": "e.g. M120984"},
                    {"name": "class_12_passing_year", "label": "Year of Passing Class 12", "type": "number", "required": True, "placeholder": "e.g. 2026"},
                    {"name": "class_12_percentage", "label": "Class 12 Marks Percentage (%)", "type": "number", "required": True, "profile_field": "student_percentage", "placeholder": "e.g. 88.5"},
                ],
            },
            {
                "section_id": "higher_education",
                "title": "Current College / University Enrolment",
                "fields": [
                    {"name": "college_university_name", "label": "College / University Name & AISHE Code", "type": "text", "required": True, "placeholder": "e.g. University of Mumbai / Fergusson College"},
                    {"name": "course_degree", "label": "Current Degree / Course", "type": "text", "required": True, "placeholder": "e.g. B.Sc. Computer Science / B.A. / B.Com / B.Tech"},
                    {"name": "annual_family_income", "label": "Gross Annual Family Income (₹)", "type": "number", "required": True, "profile_field": "annual_income"},
                    {"name": "bank_account_number", "label": "Aadhaar Seeded Bank Account Number", "type": "text", "required": True, "profile_field": "bank_account_number", "pattern": r"^[0-9]{9,18}$"},
                    {"name": "ifsc_code", "label": "Bank Branch IFSC Code", "type": "text", "required": True, "profile_field": "bank_ifsc", "pattern": r"^[A-Z]{4}0[A-Z0-9]{6}$"},
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
                    {"name": "aadhaar_number", "label": "Beneficiary's Aadhaar Number", "type": "text", "required": True, "profile_field": "aadhaar_number", "pattern": r"^[0-9]{12}$"},
                    {"name": "mobile_number", "label": "Mobile Number", "type": "text", "required": True, "profile_field": "phone_number", "pattern": r"^[6-9][0-9]{9}$"},
                ],
            },
            {
                "section_id": "pregnancy_details",
                "title": "Maternal & Child Health Details",
                "fields": [
                    {"name": "mcp_card_registration_number", "label": "MCP Card Registration Number (RCH Portal)", "type": "text", "required": True, "placeholder": "e.g. MCP-MH-2026-4421"},
                    {"name": "child_order", "label": "Child Order", "type": "select", "options": ["1st Living Child", "2nd Child (Eligible if Girl Child)"], "required": True},
                    {"name": "lmp_date", "label": "Last Menstrual Period (LMP) Date", "type": "date", "required": True},
                    {"name": "anc_date", "label": "First Ante-Natal Check-up (ANC) Date", "type": "date", "required": True},
                    {"name": "institutional_delivery_hospital", "label": "Public / Accredited Delivery Hospital", "type": "text", "required": False, "placeholder": "e.g. District Civil Hospital / PHC"},
                ],
            },
            {
                "section_id": "bank_info",
                "title": "Direct Benefit Transfer Account",
                "fields": [
                    {"name": "bank_account_number", "label": "Beneficiary Mother's Aadhaar Seeded Account", "type": "text", "required": True, "profile_field": "bank_account_number", "pattern": r"^[0-9]{9,18}$"},
                    {"name": "ifsc_code", "label": "Bank Branch IFSC Code", "type": "text", "required": True, "profile_field": "bank_ifsc", "pattern": r"^[A-Z]{4}0[A-Z0-9]{6}$"},
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
                    {"name": "gender", "label": "Gender", "type": "select", "options": ["FEMALE"], "required": True, "profile_field": "gender"},
                    {"name": "marital_status", "label": "Marital Status", "type": "select", "options": ["Widowed"], "required": True, "profile_field": "marital_status"},
                    {"name": "state", "label": "State of Residence", "type": "text", "required": True, "profile_field": "state"},
                    {"name": "district", "label": "District", "type": "text", "required": True, "profile_field": "district"},
                    {"name": "block_tehsil", "label": "Tehsil / Block / Ward", "type": "text", "required": True, "profile_field": "sub_district"},
                    {"name": "aadhaar_number", "label": "12-Digit Aadhaar Number", "type": "text", "required": True, "profile_field": "aadhaar_number", "pattern": r"^[0-9]{12}$"},
                    {"name": "mobile_number", "label": "Mobile Number", "type": "text", "required": True, "profile_field": "phone_number", "pattern": r"^[6-9][0-9]{9}$"},
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
                    {"name": "receiving_other_pension", "label": "Receiving any other Central/State Social Security Pension?", "type": "select", "options": ["No", "Yes"], "required": True},
                ],
            },
            {
                "section_id": "bank_info",
                "title": "DBT Monthly Pension Bank Account",
                "fields": [
                    {"name": "bank_account_number", "label": "Aadhaar Seeded Single Bank Account Number", "type": "text", "required": True, "profile_field": "bank_account_number", "pattern": r"^[0-9]{9,18}$"},
                    {"name": "ifsc_code", "label": "Bank Branch IFSC Code", "type": "text", "required": True, "profile_field": "bank_ifsc", "pattern": r"^[A-Z]{4}0[A-Z0-9]{6}$"},
                ],
            },
        ],
    },
    "MLBY-MH": {
        "scheme_code": "MLBY-MH",
        "title": "Mukhyamantri Majhi Ladki Bahin Yojana — Application Readiness Draft (मुख्यमंत्री माझी लाडकी बहीण योजना)",
        "form_supported": True,
        "schema_nature": "application_readiness_draft",
        "official_portal": "https://ladkibahin.maharashtra.gov.in/",
        "sections": [
            {
                "section_id": "personal_info",
                "title": "Applicant Personal Details (अर्जदाराची वैयक्तिक माहिती)",
                "fields": [
                    {"name": "applicant_name", "label": "Beneficiary Full Name (as per Aadhaar)", "type": "text", "required": True, "profile_field": "full_name"},
                    {"name": "gender", "label": "Gender (Must be Female)", "type": "select", "options": ["FEMALE", "MALE", "OTHER"], "required": True, "profile_field": "gender"},
                    {"name": "age", "label": "Age in Years (Must be 21 to 65)", "type": "number", "required": True, "profile_field": "age"},
                    {"name": "marital_status", "label": "Marital Status", "type": "select", "options": ["Married", "Unmarried", "Widowed", "Divorced", "Destitute"], "required": True, "profile_field": "marital_status"},
                    {"name": "aadhaar_number", "label": "12-Digit Aadhaar Number", "type": "text", "required": True, "profile_field": "aadhaar_number", "pattern": r"^[0-9]{12}$"},
                    {"name": "mobile_number", "label": "Aadhaar-Linked Mobile Number", "type": "text", "required": True, "profile_field": "phone_number", "pattern": r"^[6-9][0-9]{9}$"},
                ],
            },
            {
                "section_id": "domicile_info",
                "title": "Maharashtra Domicile & Residence (अधिवास व रहिवासी माहिती)",
                "fields": [
                    {"name": "state", "label": "State of Residence (Must be Maharashtra)", "type": "text", "required": True, "profile_field": "state"},
                    {"name": "district", "label": "District in Maharashtra", "type": "text", "required": True, "profile_field": "district"},
                    {"name": "domicile_proof_type", "label": "Maharashtra Domicile Proof Document", "type": "select", "options": ["Maharashtra Domicile Certificate", "15-Year Old Ration Card", "Voter ID Card (Issued ≥ 15 Years)", "School Leaving Certificate (Maharashtra Birth)"], "required": True},
                    {"name": "domicile_certificate_number", "label": "Domicile / Document Certificate Number", "type": "text", "required": False, "placeholder": "e.g. DOM/MH/2026/89124"},
                ],
            },
            {
                "section_id": "economic_status",
                "title": "Income & Household Economic Verification (उत्पन्न व आर्थिक पात्रता)",
                "fields": [
                    {"name": "annual_family_income", "label": "Gross Annual Family Income (₹) (Must be ≤ ₹2,50,000)", "type": "number", "required": True, "profile_field": "annual_income"},
                    {"name": "ration_card_type", "label": "Ration Card Type", "type": "select", "options": ["Yellow Ration Card (BPL)", "Orange Ration Card (Priority)", "White / Other"], "required": True},
                    {"name": "family_owns_four_wheeler", "label": "Does any family member own a 4-wheeler (excluding tractor)?", "type": "select", "options": ["No", "Yes"], "required": True},
                    {"name": "income_tax_payer_in_family", "label": "Is any family member an active Income Tax payer?", "type": "select", "options": ["No", "Yes"], "required": True},
                ],
            },
            {
                "section_id": "bank_dbt_info",
                "title": "Aadhaar-Seeded DBT Bank Account (बँक व थेट लाभ हस्तांतरण तपशील)",
                "fields": [
                    {"name": "bank_account_number", "label": "Individual Bank Account Number (Aadhaar DBT Enabled)", "type": "text", "required": True, "profile_field": "bank_account_number", "pattern": r"^[0-9]{9,18}$"},
                    {"name": "ifsc_code", "label": "Bank Branch IFSC Code", "type": "text", "required": True, "profile_field": "bank_ifsc", "pattern": r"^[A-Z]{4}0[A-Z0-9]{6}$"},
                ],
            },
        ],
    },
    "AB-PMJAY": {
        "scheme_code": "AB-PMJAY",
        "title": "Ayushman Bharat PM-JAY / Senior Citizen Vaya Vandana — Application Readiness Draft (आयुष्मान भारत)",
        "form_supported": True,
        "schema_nature": "application_readiness_draft",
        "official_portal": "https://beneficiary.nha.gov.in/",
        "sections": [
            {
                "section_id": "beneficiary_info",
                "title": "Beneficiary Details (लाभार्थी तपशील)",
                "fields": [
                    {"name": "beneficiary_name", "label": "Beneficiary Full Name (as per Aadhaar)", "type": "text", "required": True, "profile_field": "full_name"},
                    {"name": "age", "label": "Age in Years", "type": "number", "required": True, "profile_field": "age"},
                    {"name": "gender", "label": "Gender", "type": "select", "options": ["MALE", "FEMALE", "OTHER"], "required": True, "profile_field": "gender"},
                    {"name": "coverage_category", "label": "Coverage Eligibility Category", "type": "select", "options": ["Senior Citizen (70+ Universal Cover)", "SECC Deprived Household", "PM-JAY NFSA Ration Card Holder"], "required": True},
                    {"name": "aadhaar_number", "label": "12-Digit Aadhaar Number (Mandatory for e-KYC)", "type": "text", "required": True, "profile_field": "aadhaar_number", "pattern": r"^[0-9]{12}$"},
                    {"name": "mobile_number", "label": "Aadhaar-Linked Mobile Number (for OTP e-KYC)", "type": "text", "required": True, "profile_field": "phone_number", "pattern": r"^[6-9][0-9]{9}$"},
                ],
            },
            {
                "section_id": "residential_location",
                "title": "Residential Location (पत्ता व निवास स्थान)",
                "fields": [
                    {"name": "state", "label": "State of Residence", "type": "text", "required": True, "profile_field": "state"},
                    {"name": "district", "label": "District", "type": "text", "required": True, "profile_field": "district"},
                    {"name": "sub_district", "label": "Sub-District / Tehsil / Ward", "type": "text", "required": True, "profile_field": "sub_district"},
                    {"name": "village_town", "label": "Village / Town / City", "type": "text", "required": False, "profile_field": "village", "placeholder": "e.g. Rampur / Ward No. 5"},
                ],
            },
            {
                "section_id": "ekyc_verification",
                "title": "e-KYC & Card Generation Mode (ई-केवायसी पडताळणी)",
                "fields": [
                    {"name": "ekyc_mode", "label": "Preferred e-KYC Mode", "type": "select", "options": ["Aadhaar OTP Authentication", "Biometric (Fingerprint/Iris at Hospital/CSC)", "Face Authentication via Ayushman App"], "required": True, "default": "Aadhaar OTP Authentication"},
                    {"name": "ration_card_number", "label": "Ration Card / Family ID Number (Optional for 70+ Senior Citizens)", "type": "text", "required": False, "placeholder": "e.g. RC-MH-981240"},
                    {"name": "existing_ayushman_card", "label": "Does any family member currently hold an Ayushman Card?", "type": "select", "options": ["No", "Yes"], "required": True},
                ],
            },
        ],
    },
    "PMAY-G": {
        "scheme_code": "PMAY-G",
        "title": "Pradhan Mantri Awaas Yojana - Gramin Application Form (PMAY-G)",
        "form_supported": True,
        "schema_nature": "application_readiness_draft",
        "official_portal": "https://pmayg.nic.in/",
        "sections": [
            {
                "section_id": "personal_info",
                "title": "Head of Household Details",
                "fields": [
                    {"name": "applicant_name", "label": "Full Name (as per Aadhaar)", "type": "text", "required": True, "profile_field": "full_name"},
                    {"name": "gender", "label": "Gender", "type": "select", "options": ["MALE", "FEMALE", "OTHER"], "required": True, "profile_field": "gender"},
                    {"name": "category", "label": "Social Category", "type": "select", "options": ["General", "OBC", "SC", "ST"], "required": True, "profile_field": "caste_category"},
                    {"name": "aadhaar_number", "label": "12-Digit Aadhaar Number", "type": "text", "required": True, "profile_field": "aadhaar_number", "pattern": r"^[0-9]{12}$"},
                    {"name": "mobile_number", "label": "Aadhaar-Linked Mobile Number", "type": "text", "required": True, "profile_field": "phone_number", "pattern": r"^[6-9][0-9]{9}$"},
                ],
            },
            {
                "section_id": "housing_deprivation",
                "title": "Housing & SECC Deprivation Status",
                "fields": [
                    {"name": "current_house_type", "label": "Current Housing Condition", "type": "select", "options": ["Houseless / Kutcha (Zero or One Room)", "Kutcha (Two Rooms)", "Semi-Pucca (Dilapidated)"], "required": True},
                    {"name": "ownership_of_pucca_house", "label": "Do you or any family member own a pucca house in India?", "type": "select", "options": ["No", "Yes"], "required": True},
                    {"name": "secc_tin_or_awaas_plus_id", "label": "SECC TIN / Awaas+ Registration ID", "type": "text", "required": False, "placeholder": "e.g. AWAAS-UP-2024-98124"},
                ],
            },
            {
                "section_id": "location_info",
                "title": "Rural Location & Panchayat Details",
                "fields": [
                    {"name": "state", "label": "State", "type": "text", "required": True, "profile_field": "state"},
                    {"name": "district", "label": "District", "type": "text", "required": True, "profile_field": "district"},
                    {"name": "block_panchayat", "label": "Block / Gram Panchayat", "type": "text", "required": True, "profile_field": "sub_district"},
                    {"name": "village", "label": "Village Name", "type": "text", "required": True, "profile_field": "village"},
                ],
            },
            {
                "section_id": "bank_and_labour",
                "title": "Bank Account & Conditional MGNREGA Convergence",
                "fields": [
                    {"name": "bank_account_number", "label": "Bank Account Number (DBT active)", "type": "text", "required": True, "profile_field": "bank_account_number", "pattern": r"^[0-9]{9,18}$"},
                    {"name": "ifsc_code", "label": "Bank Branch IFSC Code", "type": "text", "required": True, "profile_field": "ifsc_code", "pattern": r"^[A-Z]{4}0[A-Z0-9]{6}$"},
                    {"name": "mgnrega_wage_convergence", "label": "Enrolled under MGNREGA for 90/95 days wage convergence?", "type": "select", "options": ["No", "Yes"], "required": False},
                    {"name": "mgnrega_job_card_number", "label": "MGNREGA Job Card Number (if enrolled above)", "type": "text", "required": False, "placeholder": "e.g. UP-01-001-002-003/1234"},
                    {"name": "land_plot_availability", "label": "Homestead Plot Availability", "type": "select", "options": ["Own Land with Clear Title", "Gram Panchayat Allotted Land", "Landless / Assistance Required"], "required": True},
                ],
            },
        ],
    },
    "PMAY-U": {
        "scheme_code": "PMAY-U",
        "title": "Pradhan Mantri Awas Yojana - Urban 2.0 Application Form (PMAY-U)",
        "form_supported": True,
        "schema_nature": "application_readiness_draft",
        "official_portal": "https://pmay-urban.gov.in/",
        "sections": [
            {
                "section_id": "personal_info",
                "title": "Applicant Identity & Economic Group",
                "fields": [
                    {"name": "applicant_name", "label": "Full Name (as per Aadhaar)", "type": "text", "required": True, "profile_field": "full_name"},
                    {"name": "gender", "label": "Gender", "type": "select", "options": ["MALE", "FEMALE", "OTHER"], "required": True, "profile_field": "gender"},
                    {"name": "aadhaar_number", "label": "12-Digit Aadhaar Number", "type": "text", "required": True, "profile_field": "aadhaar_number", "pattern": r"^[0-9]{12}$"},
                    {"name": "mobile_number", "label": "Aadhaar-Linked Mobile Number", "type": "text", "required": True, "profile_field": "phone_number", "pattern": r"^[6-9][0-9]{9}$"},
                    {"name": "annual_family_income", "label": "Annual Family Income (INR)", "type": "number", "required": True, "profile_field": "annual_income"},
                ],
            },
            {
                "section_id": "urban_housing_eligibility",
                "title": "Urban Housing Eligibility & Vertical",
                "fields": [
                    {"name": "pmay_u_vertical", "label": "Scheme Vertical", "type": "select", "options": ["BLC (Beneficiary-Led Construction)", "AHP (Affordable Housing in Partnership)", "ISS (Interest Subsidy Scheme)", "ARHC (Affordable Rental Housing)"], "required": True},
                    {"name": "owns_pucca_house_in_india", "label": "Does any family member own a pucca house in India?", "type": "select", "options": ["No", "Yes"], "required": True},
                    {"name": "income_group", "label": "Income Category (EWS <= ₹3L / LIG <= ₹6L / MIG <= ₹9L)", "type": "select", "options": ["EWS", "LIG", "MIG"], "required": True},
                ],
            },
            {
                "section_id": "urban_location",
                "title": "Urban Local Body & Town Details",
                "fields": [
                    {"name": "state", "label": "State", "type": "text", "required": True, "profile_field": "state"},
                    {"name": "district", "label": "District", "type": "text", "required": True, "profile_field": "district"},
                    {"name": "city_town_ulb", "label": "City / Municipal Body (ULB)", "type": "text", "required": True, "profile_field": "sub_district"},
                    {"name": "ward_locality", "label": "Ward / Urban Locality", "type": "text", "required": True, "profile_field": "village"},
                ],
            },
            {
                "section_id": "bank_info",
                "title": "Bank Account Details",
                "fields": [
                    {"name": "bank_account_number", "label": "Bank Account Number", "type": "text", "required": True, "profile_field": "bank_account_number", "pattern": r"^[0-9]{9,18}$"},
                    {"name": "ifsc_code", "label": "Bank IFSC Code", "type": "text", "required": True, "profile_field": "ifsc_code", "pattern": r"^[A-Z]{4}0[A-Z0-9]{6}$"},
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
    # MLBY-MH aliases
    "MLBY-MH": "MLBY-MH",
    "MLBY": "MLBY-MH",
    "MAJHI LADKI BAHIN": "MLBY-MH",
    "MAJHI LADKI BAHIN YOJANA": "MLBY-MH",
    "LADKI BAHIN": "MLBY-MH",
    "LADKI BAHIN YOJANA": "MLBY-MH",
    "LADLI BEHNA MH": "MLBY-MH",
    "MUKHYAMANTRI MAJHI LADKI BAHIN": "MLBY-MH",
    "लाडकी बहीण": "MLBY-MH",
    "लाडकी बहीण योजना": "MLBY-MH",
    "लडकी बहिन": "MLBY-MH",
    "लडकी बहिन योजना": "MLBY-MH",
    "माझी लाडकी बहीण": "MLBY-MH",
    "माझी लाडकी बहीण योजना": "MLBY-MH",
    # AB-PMJAY aliases
    "AB-PMJAY": "AB-PMJAY",
    "PMJAY": "AB-PMJAY",
    "PM-JAY": "AB-PMJAY",
    "AYUSHMAN BHARAT": "AB-PMJAY",
    "AYUSHMAN": "AB-PMJAY",
    "VAYA VANDANA": "AB-PMJAY",
    "AYUSHMAN VAYA VANDANA": "AB-PMJAY",
    "SENIOR AYUSHMAN": "AB-PMJAY",
    "AB PMJAY": "AB-PMJAY",
    "आयुष्मान भारत": "AB-PMJAY",
    "आयुष्मान": "AB-PMJAY",
    "वय वंदना": "AB-PMJAY",
    "वय वंदना योजना": "AB-PMJAY",
    # PMAY-G (Rural) & PMAY-U (Urban) kept strictly separate
    "PMAY-G": "PMAY-G",
    "PMAY_G": "PMAY-G",
    "PMAYG": "PMAY-G",
    "PRADHAN MANTRI AWAAS YOJANA - GRAMIN": "PMAY-G",
    "PRADHAN MANTRI AWAS YOJANA GRAMIN": "PMAY-G",
    "PMAY-U": "PMAY-U",
    "PMAY_U": "PMAY-U",
    "PMAYU": "PMAY-U",
    "PMAY-U 2.0": "PMAY-U",
    "PRADHAN MANTRI AWAS YOJANA - URBAN 2.0": "PMAY-U",
    "PRADHAN MANTRI AWAS YOJANA URBAN": "PMAY-U",
}


def get_form_schema_for_scheme(scheme_code_or_name: str) -> Optional[Dict[str, Any]]:
    """
    Returns the authoritative form schema for supported schemes.
    Returns None if the scheme does not have a supported pre-fill form schema.
    """
    raw_cleaned = scheme_code_or_name.strip()
    cleaned = raw_cleaned.upper()
    resolved_code = SCHEME_CODE_ALIASES.get(cleaned) or SCHEME_CODE_ALIASES.get(raw_cleaned) or cleaned

    if resolved_code in SCHEME_FORM_SCHEMAS:
        return SCHEME_FORM_SCHEMAS[resolved_code]

    # Try substring matches cleanly, distinguishing Urban (-U / URBAN) vs Rural (-G / GRAMIN)
    if "PMAY" in resolved_code or "AWAS" in resolved_code or "AWAAS" in resolved_code or "आवास" in raw_cleaned:
        if any(tok in resolved_code for tok in ("PMAY-U", "PMAY_U", "PMAYU", "URBAN")):
            return SCHEME_FORM_SCHEMAS["PMAY-U"]
        return SCHEME_FORM_SCHEMAS["PMAY-G"]

    import re

    for key, schema in SCHEME_FORM_SCHEMAS.items():
        if re.search(r"(?:^|[^A-Z0-9])" + re.escape(key) + r"(?:$|[^A-Z0-9])", resolved_code):
            return schema

    if "WIDOW" in resolved_code or "VIDHWA" in resolved_code or ("PENSION" in resolved_code and "WIDOW" in scheme_code_or_name.upper()):
        return SCHEME_FORM_SCHEMAS["WIDOW-PENSION"]
    if any(k in resolved_code or k in raw_cleaned for k in ["LADKI", "BAHIN", "लाडकी", "लडकी", "बहीण", "बहिन"]):
        return SCHEME_FORM_SCHEMAS["MLBY-MH"]
    if any(k in resolved_code or k in raw_cleaned for k in ["PMJAY", "AYUSHMAN", "VAYA VANDANA", "आयुष्मान", "वय वंदना"]):
        return SCHEME_FORM_SCHEMAS["AB-PMJAY"]

    return None


def get_unavailable_schema_payload(
    scheme_code: str,
    scheme_name: str = "",
    official_url: str = "https://india.gov.in",
    lang: str = "en",
) -> Dict[str, Any]:
    """
    Explicit, transparent response when a seeded or requested scheme does not have a verified
    structured application schema or field mapping. Never fabricates generic form fields.
    """
    display_name = scheme_name or scheme_code
    lang_code = lang if lang in ("en", "hi", "mr") else "en"
    messages = {
        "en": (
            f"Verified application form schema and field mapping are unavailable for {display_name} ({scheme_code}). "
            f"Eligibility evaluation and document guidance remain available, while final form submission must be completed directly on the official government portal."
        ),
        "hi": (
            f"{display_name} ({scheme_code}) के लिए सत्यापित आवेदन फ़ॉर्म स्कीमा और फ़ील्ड मैपिंग उपलब्ध नहीं है। "
            f"पात्रता जांच और दस्तावेज़ मार्गदर्शन उपलब्ध हैं, लेकिन आवेदन सीधे आधिकारिक सरकारी पोर्टल पर पूरा करना होगा।"
        ),
        "mr": (
            f"{display_name} ({scheme_code}) साठी पडताळलेला अर्ज फॉर्म नमुना व रकान्यांची जोडणी उपलब्ध नाही. "
            f"पात्रता तपासणी आणि कागदपत्र मार्गदर्शन उपलब्ध आहे, परंतु अंतिम अर्ज थेट अधिकृत शासकीय पोर्टलवर भरावा लागेल."
        ),
    }
    return {
        "scheme_code": scheme_code,
        "scheme_name": display_name,
        "title": f"{display_name} — Official Portal Application",
        "form_supported": False,
        "schema_available": False,
        "schema_status": "unavailable",
        "official_portal": official_url or "https://india.gov.in",
        "sections": [],
        "message": messages[lang_code],
    }
