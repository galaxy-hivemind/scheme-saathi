"""
Missing-Document Preparation Assistance & Epistemic Guidance Service.

Helps citizens actually obtain missing or unverified documents rather than merely
listing a checklist. Every response integrates with:
- Active scheme context (`Scheme` + `SchemeDocument` DB metadata & JSON catalog)
- Canonical document equivalence (`document_service.doc_types_match`)
- Citizen Document Vault lifecycle state (`missing` / `uploaded` / `awaiting_citizen_review` / `reviewed` / `rejected` / `verified`)
- Authoritative sourcing & preparation steps in pure English (`en`), Hindi (`hi`), and Marathi (`mr`)

Strict Epistemic Honesty Guarantee:
Every guidance response separates:
1. Verified information (statutory/scheme rules, authorities, verified URLs, uniform statutory fees/SLAs)
2. Estimated information (typical state/CSC processing times or state-dependent fee ranges when verified ranges exist)
3. Information unavailable (exact local office street addresses, unverified fees/SLAs, or unrecognized document types)

Never fabricates fees, processing timelines, URLs, or local office addresses.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import re

from sqlalchemy.orm import Session

from app.agents.form_schemas import DOCUMENT_SOURCING_REGISTRY, SCHEME_CODE_ALIASES, get_document_sourcing_info
from app.models.scheme import Scheme
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services.document_service import (
    DOC_STATE_VERIFIED,
    doc_types_match,
    get_localized_doc_label,
    get_localized_status_label,
    normalize_vault_document,
)
from app.services.language_registry import get_localized_scheme_metadata
from app.services.readiness_service import (
    _evaluate_doc_applicability,
    get_authoritative_scheme_documents,
)

SUPPORTED_FOCUS_MODES = ("all", "process", "cost", "where_to_apply", "fallback", "why_required")


def _t(lang: str, en: str, hi: str, mr: str) -> str:
    if lang == "hi":
        return hi
    if lang == "mr":
        return mr
    return en


# Extended metadata for all 27 document types used across the 31 schemes,
# plus strict epistemic classification, preparation steps, and fallback paths.
EXTENDED_DOC_GUIDANCE: Dict[str, Dict[str, Any]] = {
    "land_possession": {
        "title": {
            "en": "Homestead Land Title / Land Possession Certificate",
            "hi": "आवासीय भूमि स्वामित्व / भूमि कब्ज़ा प्रमाण पत्र",
            "mr": "निवासी जागा मालकी / जमीन ताबा प्रमाणपत्र",
        },
        "why": {
            "en": "Establishes homestead land title or Gram Panchayat plot allotment required to construct a house under rural housing rules.",
            "hi": "ग्रामीण आवास निर्माण के लिए वैध आवासीय भूमि स्वामित्व अथवा ग्राम पंचायत पट्टा आवंटन सिद्ध करने हेतु आवश्यक।",
            "mr": "ग्रामीण घरकुल बांधकामासाठी निवासी जागेची मालकी किंवा ग्रामपंचायत भूखंड वाटप सिद्ध करण्यासाठी आवश्यक.",
        },
        "where": {
            "en": "Local Tehsil / Taluka Revenue Office, Talathi / Patwari Office, Gram Panchayat Allotment Register, or State e-District / Land Records portal.",
            "hi": "स्थानीय तहसील राजस्व कार्यालय, लेखपाल/पटवारी कार्यालय, ग्राम पंचायत आवंटन रजिस्टर या राज्य ई-डिस्ट्रिक्ट / भूलेख पोर्टल।",
            "mr": "स्थानिक तहसील कार्यालय, तलाठी / ग्रामपंचायत कार्यालय किंवा राज्य भूमी अभिलेख / आपले सरकार पोर्टल.",
        },
        "authority": {
            "en": "State Revenue Department (Tahsildar / Patwari / Talathi) or Gram Panchayat",
            "hi": "राज्य राजस्व विभाग (तहसीलदार / लेखपाल) अथवा ग्राम पंचायत",
            "mr": "राज्य महसूल विभाग (तहसीलदार / तलाठी) किंवा ग्रामपंचायत",
        },
        "portals": [
            {"label": "PMAY-G Official Portal", "url": "https://pmayg.nic.in"},
            {"label": "DILRMP National Land Records Portal", "url": "https://dilrmp.gov.in"},
        ],
        "fee_verified": {
            "en": "Viewing computerized land records online is free; Gram Panchayat homestead allotment for eligible landless families carries no application fee.",
            "hi": "कंप्यूटरीकृत भूमि रिकॉर्ड ऑनलाइन देखना निःशुल्क है; पात्र भूमिहीन परिवारों हेतु ग्राम पंचायत आवास पट्टा आवंटन निःशुल्क होता है।",
            "mr": "संगणकीकृत जमीन उतारा ऑनलाइन पाहणे विनामूल्य आहे; पात्र भूमिहीन कुटुंबांसाठी ग्रामपंचायत जागा वाटप विनामूल्य असते.",
        },
        "fee_estimated": {
            "en": "Typically ₹15–₹30 for a digitally signed revenue extract (7/12, Khasra/Khatauni, or Patta) via CSC / State e-District (varies by state schedule).",
            "hi": "सीएससी / राज्य ई-डिस्ट्रिक्ट के माध्यम से हस्ताक्षरित राजस्व नकल (खतौनी/पट्टा) हेतु सामान्यतः ₹15–₹30 शुल्क (राज्यानुसार भिन्न)।",
            "mr": "सीएससी / आपले सरकार केंद्राद्वारे डिजिटल स्वाक्षरीकृत ७/१२ किंवा पट्टा प्रतीसाठी साधारणतः ₹१५–₹३० शुल्क (राज्यानुसार बदलते).",
        },
        "time_estimated": {
            "en": "Instant digital download where land records are digitized; typically 7–15 working days for certified copies or Gram Panchayat possession/allotment certificates.",
            "hi": "डिजिटल पोर्टल पर तुरंत डाउनलोड; प्रमाणित प्रति या ग्राम पंचायत आवंटन प्रमाण पत्र हेतु सामान्यतः 7–15 कार्य दिवस।",
            "mr": "संगणकीकृत असल्यास त्वरित डाउनलोड; प्रमाणित प्रत किंवा ग्रामपंचायत वाटप प्रमाणपत्रासाठी साधारणतः ७–१५ कामाचे दिवस.",
        },
        "unavailable": {
            "en": [
                "Exact local office street address, counter number, and village officer schedule.",
                "Exact state-specific stamp/court fee if your district requires a fresh revenue survey.",
            ],
            "hi": [
                "आपके गाँव/ब्लॉक के स्थानीय कार्यालय का सटीक सड़क पता, कमरा संख्या और अधिकारी संपर्क विवरण।",
                "यदि नए राजस्व सर्वेक्षण की आवश्यकता हो तो जिले का सटीक स्थानीय शुल्क।",
            ],
            "mr": [
                "तुमच्या गाव/तालुक्यातील स्थानिक कार्यालयाचा नेमका पत्ता, खिडकी क्रमांक आणि अधिकाऱ्यांचा संपर्क.",
                "नवीन मोजणी किंवा अर्जासाठीचे जिल्हास्तरीय नेमके स्थानिक शुल्क.",
            ],
        },
        "steps": {
            "en": [
                "Gather prerequisites: Aadhaar Card, family Ration Card/Voter ID, plot survey/khasra number or old allotment resolution.",
                "Check online first on your State Land Records portal (e.g., UP Bhulekh or Maharashtra Mahabhumi) via https://dilrmp.gov.in.",
                "If not digitized or if requesting Gram Panchayat homestead allotment, visit your Gram Panchayat or Tehsil/Talathi office with a written application.",
                "Collect the signed extract/allotment certificate with official seal or digital barcode.",
                "Upload the document in Scheme Saathi's Document Vault, review extracted fields, and complete verification before final submission.",
            ],
            "hi": [
                "आवश्यक सामग्री जुटाएं: आधार कार्ड, राशन कार्ड/पहचान पत्र, भूमि गाटा/खसरा संख्या या पुराना आवंटन प्रस्ताव।",
                "पहले अपने राज्य के भूलेख पोर्टल (जैसे यूपी भूलेख या महाभूमि) को https://dilrmp.gov.in से जांचें।",
                "यदि ऑनलाइन न हो या नया आवास पट्टा चाहिए, तो लिखित आवेदन लेकर ग्राम पंचायत या तहसील/लेखपाल कार्यालय जाएं।",
                "सरकारी मुहर या डिजिटल बारकोड वाला प्रमाणित आवंटन/कब्ज़ा प्रमाण पत्र प्राप्त करें।",
                "दस्तावेज़ को योजना साथी के डॉक्यूमेंट वॉल्ट में अपलोड करें, विवरण की समीक्षा करें और सत्यापन पूर्ण करें।",
            ],
            "mr": [
                "पूर्वतयारीची कागदपत्रे गोळा करा: आधार कार्ड, रेशन कार्ड/ओळखपत्र, जागेचा सर्व्हे/गट क्रमांक किंवा जुना ग्रामपंचायत ठराव.",
                "प्रथम https://dilrmp.gov.in द्वारे तुमच्या राज्याच्या भूमी अभिलेख पोर्टलवर (उदा. महाभूमी) नोंद ऑनलाइन तपासा.",
                "नोंद ऑनलाइन नसल्यास किंवा नवीन निवासी जागा वाटप हवे असल्यास ग्रामपंचायत किंवा तहसील/तलाठी कार्यालयात लेखी अर्ज करा.",
                "अधिकृत शिक्का किंवा डिजिटल स्वाक्षरीसह प्रमाणित ताबा/वाटप प्रमाणपत्र घ्या.",
                "मिळालेले कागदपत्र योजना साथीच्या डॉक्युमेंट व्हॉल्टमध्ये अपलोड करा, तपशील तपासा आणि पडताळणी पूर्ण करा.",
            ],
        },
        "fallback": {
            "en": [
                "Accepted alternatives under PMAY-G guidelines include a Gram Panchayat Allotment Certificate or state Revenue Patta.",
                "If you are a landless rural household under PMAY-G, inform your Gram Sabha/Block office — PMAY-G provides for state homestead land allotment or financial assistance to purchase a plot before house sanction.",
                "For unresolved revenue title disputes or missing entries, visit your nearest CSC / Tehsil e-District grievance counter to request an official Record of Rights (RoR) search.",
            ],
            "hi": [
                "PMAY-G दिशानिर्देशों के अनुसार ग्राम पंचायत आवंटन प्रमाण पत्र अथवा राज्य राजस्व पट्टा मान्य विकल्प हैं।",
                "यदि आप भूमिहीन ग्रामीण परिवार हैं, तो ग्राम सभा / ब्लॉक कार्यालय को सूचित करें — आवास स्वीकृति से पहले राज्य सरकार द्वारा आवासीय भूमि पट्टा या भूमि क्रय सहायता प्रदान की जाती है।",
                "रिकॉर्ड त्रुटि या देरी होने पर नजदीकी सीएससी या तहसील जन-सुनवाई/ई-डिस्ट्रिक्ट काउंटर पर रिकॉर्ड सुधार आवेदन दर्ज करें।",
            ],
            "mr": [
                "PMAY-G मार्गदर्शक तत्त्वांनुसार ग्रामपंचायत जागा वाटप प्रमाणपत्र किंवा महसूल पट्टा हे अधिकृत पर्याय म्हणून स्वीकारले जातात.",
                "तुम्ही भूमिहीन ग्रामीण कुटुंब असल्यास ग्रामसभा / गटविकास कार्यालयात नोंद करा — घरकुल मंजुरीपूर्वी राज्य शासनाकडून मोफत निवासी जागा किंवा जागा खरेदी सहाय्य मिळू शकते.",
                "जुनी नोंद सापडत नसल्यास नजीकच्या सीएससी किंवा तहसील तक्रार निवारण कक्षात अधिकृत नोंद शोध (RoR search) अर्ज करा.",
            ],
        },
    },
    "land_records": {
        "title": {
            "en": "Land Ownership Records (7/12 Extract / Khasra-Khatauni / RoR)",
            "hi": "भूमि स्वामित्व रिकॉर्ड (खसरा-खतौनी / 7/12 / अधिकार अभिलेख)",
            "mr": "जमीन मालकी नोंद (७/१२ व ८-अ उतारा / RoR)",
        },
        "why": {
            "en": "Establishes legal cultivable land ownership, survey number, and landholding family eligibility.",
            "hi": "कृषि भूमि के वैध स्वामित्व, गाटा/खसरा संख्या और किसान परिवार की पात्रता सिद्ध करने हेतु आवश्यक।",
            "mr": "शेतजमिनीची कायदेशीर मालकी, गट क्रमांक आणि शेतकरी कुटुंब पात्रता सिद्ध करण्यासाठी आवश्यक.",
        },
        "where": {
            "en": "State Land Records Portal (e.g., UP Bhulekh, Maharashtra Mahabhumi), local Talathi / Patwari / Lekhpal office, Tehsil Office, or authorized CSC / Aaple Sarkar center.",
            "hi": "राज्य भूलेख पोर्टल (जैसे यूपी भूलेख, महाराष्ट्र महाभूमि), स्थानीय लेखपाल/पटवारी, तहसील कार्यालय या अधिकृत सीएससी (CSC)।",
            "mr": "राज्य भूमी अभिलेख पोर्टल (उदा. महाभूमी), स्थानिक तलाठी कार्यालय, तहसील कार्यालय किंवा आपले सरकार / सीएससी केंद्र.",
        },
        "authority": {
            "en": "State Revenue Department / Directorate of Land Records (Tahsildar / Talathi / Patwari)",
            "hi": "राज्य राजस्व विभाग / भू-अभिलेख निदेशालय (तहसीलदार / लेखपाल / पटवारी)",
            "mr": "राज्य महसूल विभाग / भूमी अभिलेख संचालनालय (तहसीलदार / तलाठी)",
        },
        "portals": [
            {"label": "DILRMP National Land Records Portal", "url": "https://dilrmp.gov.in"},
            {"label": "DigiLocker (Signed Land/Revenue Records)", "url": "https://digilocker.gov.in"},
        ],
        "fee_verified": {
            "en": "Online informational viewing on official state land portals is free.",
            "hi": "आधिकारिक राज्य भूलेख पोर्टल पर जानकारी हेतु रिकॉर्ड ऑनलाइन देखना निःशुल्क है।",
            "mr": "अधिकृत राज्य भूमी अभिलेख पोर्टलवर उतारा माहितीसाठी ऑनलाइन पाहणे विनामूल्य आहे.",
        },
        "fee_estimated": {
            "en": "Typically ₹15–₹30 for a digitally signed certified copy via CSC / Aaple Sarkar / Tehsil kiosk (exact fee varies by state revenue rules).",
            "hi": "सीएससी / तहसील केंद्र से डिजिटल हस्ताक्षरित प्रमाणित नकल हेतु सामान्यतः ₹15–₹30 शुल्क (राज्यानुसार भिन्न)।",
            "mr": "सीएससी / आपले सरकार / तहसील केंद्रातून डिजिटल स्वाक्षरीकृत प्रमाणित ७/१२ प्रतीसाठी साधारणतः ₹१५–₹३० शुल्क (राज्यानुसार बदलते).",
        },
        "time_estimated": {
            "en": "Instant digital download on computerized state portals; typically 3–5 working days at Talathi/Patwari office, or 15–30 days if name mutation (Ferfar) is pending.",
            "hi": "डिजिटल पोर्टल पर तुरंत डाउनलोड; पटवारी/तहसील से नकल हेतु 3–5 कार्य दिवस (यदि नामांतरण/दाखिल-खारिज लंबित हो तो 15–30 दिन)।",
            "mr": "संगणकीकृत पोर्टलवरून त्वरित डाउनलोड; तलाठी/तहसील कार्यालयातून ३–५ कामाचे दिवस (जर वारसा/फेरफार प्रलंबित असेल तर १५–३० दिवस).",
        },
        "unavailable": {
            "en": [
                "Exact local Talathi/Lekhpal office street address and village duty hours.",
                "Exact state-specific certified extract or land mutation stamp fee.",
            ],
            "hi": [
                "स्थानीय लेखपाल/पटवारी या तहसील कार्यालय का सटीक सड़क पता और समय सारणी।",
                "राज्यानुसार प्रमाणित नकल या नामांतरण का सटीक स्थानीय शुल्क।",
            ],
            "mr": [
                "तुमच्या गाव/तालुक्यातील तलाठी किंवा तहसील कार्यालयाचा नेमका पत्ता व कामकाजाची वेळ.",
                "प्रमाणित प्रत किंवा फेरफार नोंदीचे राज्यानुसार नेमके स्थानिक शुल्क.",
            ],
        },
        "steps": {
            "en": [
                "Note your District, Taluka/Tehsil, Village, and Survey/Khasra/Khata number (along with Aadhaar).",
                "Check your state revenue portal via https://dilrmp.gov.in or fetch via https://digilocker.gov.in for an instant digital record.",
                "If your name is missing or undivided family partition is needed, apply for land mutation (Ferfar / Dakhil-Kharij) at your Talathi/Patwari or Tehsil e-District CSC.",
                "Obtain the digitally signed 7/12, Khasra-Khatauni, or Record of Rights (RoR) extract.",
                "Upload the extract to Scheme Saathi's Document Vault, review extracted fields, and confirm verification before applying.",
            ],
            "hi": [
                "अपना जिला, तहसील, ग्राम और खसरा/गाटा/खाता संख्या (एवं आधार कार्ड) तैयार रखें।",
                "https://dilrmp.gov.in के माध्यम से राज्य भूलेख पोर्टल या https://digilocker.gov.in पर डिजिटल रिकॉर्ड डाउनलोड करें।",
                "यदि खतौनी में आपका नाम दर्ज नहीं है या बंटवारा लंबित है, तो लेखपाल/तहसील या सीएससी पर नामांतरण (दाखिल-खारिज) हेतु आवेदन करें।",
                "डिजिटल हस्ताक्षरित खसरा-खतौनी या अधिकार अभिलेख (RoR) प्राप्त करें।",
                "दस्तावेज़ को डॉक्यूमेंट वॉल्ट में अपलोड कर समीक्षा और सत्यापन पूरा करें।",
            ],
            "mr": [
                "तुमचा जिल्हा, तालुका, गाव आणि सर्व्हे/गट/खाते क्रमांक (आधार कार्डसह) तयार ठेवा.",
                "https://dilrmp.gov.in द्वारे राज्य भूमी अभिलेख पोर्टल किंवा https://digilocker.gov.in वरून डिजिटल प्रत तपासा.",
                "उताऱ्यावर तुमचे नाव नसल्यास किंवा हिस्सेवाटप प्रलंबित असल्यास तलाठी/तहसील किंवा सीएससीद्वारे फेरफार (नामांतरण) अर्ज करा.",
                "डिजिटल स्वाक्षरी असलेला ७/१२ व ८-अ किंवा RoR उतारा प्राप्त करा.",
                "हा उतारा डॉक्युमेंट व्हॉल्टमध्ये अपलोड करून तपशील तपासा आणि पडताळणी पूर्ण करा.",
            ],
        },
        "fallback": {
            "en": [
                "Accepted equivalents depend on the active scheme: PM-KISAN accepts Record of Rights (RoR), Khasra-Khatauni, 7/12+8-A, Patta, or Mutation Extract; KCC and PMFBY also accept a registered Lease Deed or Tenancy Agreement for tenant farmers.",
                "Under PM-KISAN guidelines, cultivable land ownership in the applicant family's name is mandatory — if your family cultivates leased land without ownership, ask about KCC (tenant farmer route), PMFBY, or MGNREGA instead.",
                "If records are lost due to old family partition, apply at Tehsil / CSC for inheritance/partition mutation (Ferfar) first.",
            ],
            "hi": [
                "स्वीकार्य विकल्प योजना पर निर्भर करते हैं: PM-KISAN में अधिकार अभिलेख (RoR), खसरा-खतौनी, पट्टा या नामांतरण नकल मान्य है; जबकि KCC और PMFBY में बटाईदार/काश्तकार किसानों के लिए पंजीकृत पट्टा/किरायानामा (Lease/Tenancy Agreement) भी स्वीकार किया जाता है।",
                "PM-KISAN दिशानिर्देशों के अनुसार आवेदक परिवार के नाम कृषि भूमि स्वामित्व अनिवार्य है — यदि आप केवल किराये/बटाई की भूमि पर खेती करते हैं, तो आप KCC, PMFBY या मनरेगा जैसी योजनाओं की जांच कर सकते हैं।",
                "यदि पारिवारिक बंटवारे या विरासत के कारण नाम नहीं जुड़ा है, तो तहसील या सीएससी से नामांतरण हेतु आवेदन करें।",
            ],
            "mr": [
                "स्वीकारले जाणारे पर्याय योजनेनुसार बदलतात: PM-KISAN साठी ७/१२ व ८-अ, खसरा-खतौनी, पट्टा किंवा फेरफार उतारा मान्य असतो; तर KCC आणि PMFBY मध्ये भाडेपट्टा कराराद्वारे (Lease/Tenancy Agreement) शेती करणाऱ्यांनाही लाभ मिळू शकतो.",
                "PM-KISAN नियमांनुसार अर्जदार कुटुंबाच्या नावावर शेतजमीन मालकी अनिवार्य आहे — स्वतःची जमीन नसल्यास तुम्ही KCC (करार शेतकरी), PMFBY किंवा मनरेगा या योजना तपासू शकता.",
                "वारसा किंवा वाटणीमुळे नाव नसल्यास तलाठी/तहसील किंवा सीएससीद्वारे फेरफार नोंदीसाठी अर्ज करा.",
            ],
        },
    },
    "aadhaar_card": {
        "title": {"en": "Aadhaar Card", "hi": "आधार कार्ड", "mr": "आधार कार्ड"},
        "why": {
            "en": "Mandatory statutory identity and DBT authentication document under Section 7 of the Aadhaar Act.",
            "hi": "आधार अधिनियम की धारा 7 के अंतर्गत वैधानिक पहचान और प्रत्यक्ष लाभ अंतरण (DBT) सत्यापन हेतु आवश्यक।",
            "mr": "आधार कायद्याच्या कलम ७ अन्वये वैधानिक ओळख व थेट लाभ हस्तांतरण (DBT) पडताळणीसाठी आवश्यक.",
        },
        "where": {
            "en": "Authorized Aadhaar Seva Kendra, Post Office, Bank Aadhaar Enrolment Centre, or online e-Aadhaar via myAadhaar.",
            "hi": "अधिकृत आधार सेवा केंद्र, डाकघर, बैंक नामांकन केंद्र अथवा myAadhaar ऑनलाइन पोर्टल।",
            "mr": "अधिकृत आधार सेवा केंद्र, पोस्ट ऑफिस, बँक नोंदणी केंद्र किंवा myAadhaar ऑनलाइन पोर्टल.",
        },
        "authority": {
            "en": "Unique Identification Authority of India (UIDAI), Ministry of Electronics & IT",
            "hi": "भारतीय विशिष्ट पहचान प्राधिकरण (UIDAI), इलेक्ट्रॉनिक्स एवं सूचना प्रौद्योगिकी मंत्रालय",
            "mr": "भारतीय विशिष्ट ओळख प्राधिकरण (UIDAI), इलेक्ट्रॉनिक्स आणि माहिती तंत्रज्ञान मंत्रालय",
        },
        "portals": [{"label": "UIDAI myAadhaar Portal", "url": "https://myaadhaar.uidai.gov.in"}],
        "fee_verified": {
            "en": "New enrolment and mandatory child biometric updates are Free; ₹50 for demographic update; ₹100 for biometric update; ₹50 for PVC Aadhaar order.",
            "hi": "नया आधार नामांकन और बच्चों का अनिवार्य बायोमेट्रिक अपडेट निःशुल्क है; जनसांख्यिकीय संशोधन ₹50, बायोमेट्रिक संशोधन ₹100 तथा पीवीसी कार्ड शुल्क ₹50 है।",
            "mr": "नवीन आधार नोंदणी आणि मुलांचे अनिवार्य बायोमेट्रिक अद्यतन मोफत आहे; लोकसंख्याशास्त्रीय सुधारणा ₹५०, बायोमेट्रिक सुधारणा ₹१०० आणि PVC कार्ड ₹५० शुल्क आहे.",
        },
        "time_estimated": {
            "en": "Instant e-Aadhaar download once generated; typically 7–30 days for new generation or updates (90 days statutory outer limit).",
            "hi": "बनने के बाद ई-आधार तुरंत डाउनलोड; नए नामांकन या सुधार हेतु सामान्यतः 7–30 दिन।",
            "mr": "तयार झाल्यावर ई-आधार त्वरित डाउनलोड; नवीन नोंदणी किंवा सुधारणेसाठी साधारणतः ७–३० दिवस.",
        },
        "unavailable": {
            "en": ["Exact nearest Aadhaar Seva Kendra street address and daily appointment slot availability (check on myaadhaar.uidai.gov.in)."],
            "hi": ["आपके नजदीकी आधार सेवा केंद्र का सटीक सड़क पता और आज की स्लॉट उपलब्धता (myaadhaar.uidai.gov.in पर जांचें)।"],
            "mr": ["तुमच्या जवळच्या आधार सेवा केंद्राचा नेमका पत्ता आणि अपॉइंटमेंट स्लॉट उपलब्धता (myaadhaar.uidai.gov.in वर पहा)."],
        },
        "steps": {
            "en": [
                "Collect an approved Proof of Identity (PoI) and Proof of Address (PoA) such as Ration Card, Voter ID, or Birth Certificate.",
                "Book an appointment at an Aadhaar Seva Kendra via https://myaadhaar.uidai.gov.in or visit an enrolled Bank/Post Office.",
                "Complete biometric & demographic capture and keep your Enrolment ID (EID) receipt safe.",
                "Download digital e-Aadhaar from myAadhaar/DigiLocker once SMS confirmation arrives and upload it to Document Vault.",
            ],
            "hi": [
                "पहचान और पते का मान्य प्रमाण (जैसे राशन कार्ड, मतदाता पहचान पत्र या जन्म प्रमाण पत्र) तैयार रखें।",
                "https://myaadhaar.uidai.gov.in पर अपॉइंटमेंट बुक करें या बैंक/डाकघर आधार केंद्र पर जाएं।",
                "बायोमेट्रिक एवं विवरण दर्ज कराकर नामांकन रसीद (EID) सुरक्षित रखें।",
                "बनने पर myAadhaar या DigiLocker से ई-आधार डाउनलोड कर डॉक्यूमेंट वॉल्ट में अपलोड करें।",
            ],
            "mr": [
                "ओळखीचा व पत्त्याचा वैध पुरावा (उदा. रेशन कार्ड, मतदान ओळखपत्र किंवा जन्म दाखला) सोबत ठेवा.",
                "https://myaadhaar.uidai.gov.in वर अपॉइंटमेंट घ्या किंवा बँक/पोस्ट ऑफिस आधार केंद्रात जा.",
                "बायोमेट्रिक व माहिती नोंदवून पावती (EID) जपून ठेवा.",
                "तयार झाल्यावर myAadhaar किंवा DigiLocker वरून ई-आधार डाउनलोड करून डॉक्युमेंट व्हॉल्टमध्ये अपलोड करा.",
            ],
        },
        "fallback": {
            "en": [
                "If lost, retrieve Aadhaar/EID online using registered mobile number on myaadhaar.uidai.gov.in or toll-free UIDAI helpline 1947.",
                "Under Section 7 of the Aadhaar Act, beneficiaries who have applied for Aadhaar (holding EID) or face biometric mismatch can seek alternate authentication support at the CSC/Block office.",
            ],
            "hi": [
                "यदि खो गया है, तो पंजीकृत मोबाइल से myaadhaar.uidai.gov.in पर पुनः डाउनलोड करें या हेल्पलाइन 1947 पर संपर्क करें।",
                "आधार अधिनियम की धारा 7 के तहत जब तक आधार जारी न हो, नामांकन रसीद (EID) दिखाकर सीएससी/ब्लॉक कार्यालय से वैकल्पिक सहायता मांगी जा सकती है।",
            ],
            "mr": [
                "हरवले असल्यास नोंदणीकृत मोबाइलवरून myaadhaar.uidai.gov.in वरून पुन्हा डाउनलोड करा किंवा १९४७ हेल्पलाइनवर संपर्क साधा.",
                "आधार कायद्याच्या कलम ७ नुसार आधार मिळेपर्यंत नोंदणी पावतीसह (EID) सीएससी/गट कार्यालयात पर्यायी मदतीची विनंती करता येते.",
            ],
        },
    },
    "income_certificate": {
        "title": {"en": "Income Certificate", "hi": "आय प्रमाण पत्र", "mr": "उत्पन्न प्रमाणपत्र"},
        "why": {
            "en": "Certifies annual household income falls within the statutory ceiling required for means-tested schemes.",
            "hi": "योजना की पात्रता हेतु निर्धारित अधिकतम सीमा के अंतर्गत वार्षिक पारिवारिक आय प्रमाणित करने के लिए आवश्यक।",
            "mr": "योजनेच्या विहित मर्यादेखालील वार्षिक कौटुंबिक उत्पन्न सिद्ध करण्यासाठी आवश्यक.",
        },
        "where": {
            "en": "Tehsil / Taluka Revenue Office, Common Service Center (CSC / Aaple Sarkar / Jan Seva Kendra), or State e-District portal.",
            "hi": "तहसील/ब्लॉक राजस्व कार्यालय, सीएससी (CSC / जन सेवा केंद्र) या राज्य ई-डिस्ट्रिक्ट पोर्टल।",
            "mr": "तहसील महसूल कार्यालय, आपले सरकार / सेतू सेवा केंद्र किंवा राज्य ई-डिस्ट्रिक्ट पोर्टल.",
        },
        "authority": {
            "en": "State Revenue Department (Tahsildar / Sub-Divisional Officer / SDM)",
            "hi": "राज्य राजस्व विभाग (तहसीलदार / उप-विभागीय अधिकारी / एसडीएम)",
            "mr": "राज्य महसूल विभाग (तहसीलदार / उपविभागीय अधिकारी)",
        },
        "portals": [{"label": "National Government Services Portal", "url": "https://services.india.gov.in"}],
        "fee_verified": None,
        "fee_estimated": {
            "en": "Typically ₹15 to ₹30 at authorized CSC / state e-District portals (exact fee depends on state service schedule).",
            "hi": "सीएससी / राज्य ई-डिस्ट्रिक्ट पोर्टल पर सामान्यतः ₹15 से ₹30 शुल्क (सटीक शुल्क राज्य नियमानुसार भिन्न)।",
            "mr": "सीएससी / आपले सरकार पोर्टलवर साधारणतः ₹१५ ते ₹३० शुल्क (नेमके शुल्क राज्य नियमांनुसार बदलते).",
        },
        "time_estimated": {
            "en": "Typically 7–15 working days depending on state citizen service charter verification by Patwari/Talathi.",
            "hi": "लेखपाल/तलाठी जांच के पश्चात सामान्यतः 7–15 कार्य दिवस (राज्यानुसार भिन्न)।",
            "mr": "तलाठी/मंडळ अधिकारी पडताळणीनंतर साधारणतः ७–१५ कामाचे दिवस (राज्यानुसार बदलते).",
        },
        "unavailable": {
            "en": [
                "Exact local CSC/Tehsil street address.",
                "Exact state-specific portal fee for your district.",
            ],
            "hi": [
                "आपके स्थानीय तहसील/सीएससी केंद्र का सटीक पता।",
                "आपके जिले का सटीक राज्य सेवा शुल्क।",
            ],
            "mr": [
                "तुमच्या स्थानिक तहसील/सेतू केंद्राचा नेमका पत्ता.",
                "तुमच्या जिल्ह्याचे नेमके स्थानिक सेवा शुल्क.",
            ],
        },
        "steps": {
            "en": [
                "Collect Aadhaar Card, Ration Card / Address Proof, passport photo, and salary slip or self-declaration of family income.",
                "Apply online via your state e-District / Aaple Sarkar portal (listed on https://services.india.gov.in) or through an authorized CSC.",
                "Complete local Talathi/Patwari verification and track application via acknowledgement number.",
                "Download the digitally signed Income Certificate and upload it to Scheme Saathi's Document Vault for review & verification.",
            ],
            "hi": [
                "आधार कार्ड, राशन कार्ड / निवास प्रमाण, फोटो और आय स्व-घोषणा या वेतन पर्ची एकत्र करें।",
                "अपने राज्य ई-डिस्ट्रिक्ट पोर्टल (https://services.india.gov.in पर लिंक उपलब्ध) या नजदीकी सीएससी केंद्र से आवेदन करें।",
                "लेखपाल/तलाठी सत्यापन पूरा कर रसीद संख्या से स्थिति ट्रैक करें।",
                "डिजिटल हस्ताक्षरित आय प्रमाण पत्र डाउनलोड करें और डॉक्यूमेंट वॉल्ट में अपलोड व सत्यापित करें।",
            ],
            "mr": [
                "आधार कार्ड, रेशन कार्ड / पत्त्याचा पुरावा, फोटो आणि उत्पन्नाचे स्वयंघोषणापत्र किंवा पगार स्लिप गोळा करा.",
                "राज्य ई-डिस्ट्रिक्ट / आपले सरकार पोर्टलवरून (https://services.india.gov.in वर उपलब्ध) किंवा सीएससीद्वारे अर्ज करा.",
                "तलाठी पडताळणी पूर्ण करून पावती क्रमांकाद्वारे स्थिती तपासा.",
                "डिजिटल स्वाक्षरीकृत उत्पन्न प्रमाणपत्र डाउनलोड करून डॉक्युमेंट व्हॉल्टमध्ये अपलोड व पडताळणी करा.",
            ],
        },
        "fallback": {
            "en": [
                "Under Maharashtra Ladki Bahin Yojana (MLBY-MH), a valid Yellow or Orange Ration Card is accepted as a direct alternative to an Income Certificate.",
                "For other income-capped schemes (such as NSP-CSSS or Widow Pension), an Income Certificate from the competent revenue authority is required before sanction — use CSC expedited service or State Right to Services grievance tracking if delayed.",
            ],
            "hi": [
                "महाराष्ट्र लाडकी बहीण योजना (MLBY-MH) में आय प्रमाण पत्र के स्थान पर वैध पीला या नारंगी राशन कार्ड विकल्प के रूप में मान्य है।",
                "अन्य आय-आधारित योजनाओं (जैसे NSP-CSSS या विधवा पेंशन) में सक्षम राजस्व अधिकारी का आय प्रमाण पत्र आवश्यक होता है — देरी होने पर राज्य लोक सेवा गारंटी पोर्टल पर शिकायत दर्ज की जा सकती है।",
            ],
            "mr": [
                "मुख्यमंत्री माझी लाडकी बहीण योजनेअंतर्गत (MLBY-MH) उत्पन्नाच्या दाखल्याऐवजी पिवळे किंवा केशरी रेशन कार्ड पर्याय म्हणून स्वीकारले जाते.",
                "इतर उत्पन्न मर्यादेच्या योजनांसाठी (जसे NSP-CSSS किंवा विधवा निवृत्तीवेतन) तहसीलदारांचा दाखला आवश्यक असतो — विलंब झाल्यास सेवा हक्क कायद्यांतर्गत (RTS) अपील करता येते.",
            ],
        },
    },
    "death_certificate": {
        "title": {"en": "Death Certificate", "hi": "मृत्यु प्रमाण पत्र", "mr": "मृत्यू प्रमाणपत्र"},
        "why": {
            "en": "Mandatory statutory proof of spouse's demise under civil registration rules for survivor/widow pension benefits.",
            "hi": "विधवा/परिवार पेंशन योजनाओं हेतु पति के निधन का अनिवार्य वैधानिक प्रमाण।",
            "mr": "विधवा निवृत्तीवेतन योजनेसाठी पतीच्या निधनाचा अनिवार्य वैधानिक पुरावा.",
        },
        "where": {
            "en": "Urban: Municipal Corporation / Municipality Registrar. Rural: Gram Panchayat Registrar or State Civil Registration System (CRS).",
            "hi": "शहरी: नगर निगम/नगर पालिका रजिस्ट्रार। ग्रामीण: ग्राम पंचायत / जन्म-मृत्यु पंजीकरण प्रणाली (CRS)।",
            "mr": "शहरी: महानगरपालिका / नगरपालिका निबंधक. ग्रामीण: ग्रामपंचायत किंवा नागरी नोंदणी प्रणाली (CRS).",
        },
        "authority": {
            "en": "Registrar of Births and Deaths (Registration of Births and Deaths Act, 1969)",
            "hi": "जन्म एवं मृत्यु रजिस्ट्रार (जन्म और मृत्यु पंजीकरण अधिनियम, 1969)",
            "mr": "जन्म आणि मृत्यू निबंधक (जन्म व मृत्यू नोंदणी अधिनियम, १९६९)",
        },
        "portals": [{"label": "Civil Registration System (CRS)", "url": "https://crsorgi.gov.in"}],
        "fee_verified": {
            "en": "Registration within 21 days of demise is free under the Registration of Births and Deaths Act.",
            "hi": "निधन के 21 दिनों के भीतर पंजीकरण निःशुल्क है।",
            "mr": "निधनानंतर २१ दिवसांच्या आत नोंदणी मोफत असते.",
        },
        "fee_estimated": {
            "en": "Delayed registration or duplicate certified copies typically attract nominal late/search fees (₹10–₹50, varying by state/ULB).",
            "hi": "विलंबित पंजीकरण या अतिरिक्त नकल पर राज्यों/निकायों के अनुसार नाममात्र शुल्क (सामान्यतः ₹10–₹50) लागू हो सकता है।",
            "mr": "उशिरा नोंदणी किंवा दुय्यम प्रतीसाठी स्थानिक स्वराज्य संस्थेनुसार नाममात्र शुल्क (साधारणतः ₹१०–₹५०) लागू शकते.",
        },
        "time_estimated": {
            "en": "Typically 7–15 working days from application/verification (instant download on CRS if already digitized).",
            "hi": "आवेदन से सामान्यतः 7–15 कार्य दिवस (यदि डिजिटल रिकॉर्ड मौजूद हो तो तुरंत डाउनलोड)।",
            "mr": "अर्जापासून साधारणतः ७–१५ कामाचे दिवस (डिजिटल नोंद असल्यास त्वरित डाउनलोड).",
        },
        "unavailable": {
            "en": [
                "Exact municipal ward/Gram Panchayat office street address.",
                "Exact late-registration magistrate fee if demise occurred over 1 year ago without prior registration.",
            ],
            "hi": [
                "स्थानीय नगर पालिका वार्ड / ग्राम पंचायत कार्यालय का सटीक सड़क पता।",
                "1 वर्ष से अधिक विलंबित पंजीकरण में मजिस्ट्रेट/तहसीलदार आदेश का सटीक स्थानीय शुल्क।",
            ],
            "mr": [
                "स्थानिक प्रभाग कार्यालय / ग्रामपंचायत कार्यालयाचा नेमका पत्ता.",
                "१ वर्षापेक्षा जास्त विलंबित नोंदणीसाठी दंडाधिकारी आदेशाचे नेमके स्थानिक शुल्क.",
            ],
        },
        "steps": {
            "en": [
                "Gather hospital demise summary / cremation slip, deceased spouse's ID, and applicant's Aadhaar.",
                "Search https://crsorgi.gov.in or visit the Municipal/Gram Panchayat Registrar where demise occurred.",
                "If demise was not registered within 1 year, submit delayed registration request with affidavit to Sub-Divisional Magistrate / Tahsildar.",
                "Collect the digitally signed certificate and upload it to Document Vault for review & verification.",
            ],
            "hi": [
                "अस्पताल मृत्यु विवरण / श्मशान पर्ची, दिवंगत का पहचान पत्र एवं आवेदक का आधार एकत्र करें।",
                "https://crsorgi.gov.in पोर्टल जांचें या संबंधित नगर पालिका/ग्राम पंचायत रजिस्ट्रार कार्यालय जाएं।",
                "यदि 1 वर्ष से अधिक समय बाद पंजीकरण नहीं हुआ है, तो एसडीएम/तहसीलदार के समक्ष विलंबित पंजीकरण आवेदन दें।",
                "डिजिटल प्रमाण पत्र लेकर डॉक्यूमेंट वॉल्ट में अपलोड व सत्यापित करें।",
            ],
            "mr": [
                "रुग्णालय निधनाचा दाखला / स्मशान पावती, दिवंगत व्यक्तीचे ओळखपत्र आणि अर्जदाराचा आधार सोबत ठेवा.",
                "https://crsorgi.gov.in वर नोंद तपासा किंवा संबंधित मनपा/ग्रामपंचायत निबंधकाकडे अर्ज करा.",
                "१ वर्षापेक्षा जास्त कालावधी उलटला असल्यास उपविभागीय अधिकारी/तहसीलदारांकडे विलंबित नोंदणी अर्ज द्या.",
                "डिजिटल प्रमाणपत्र मिळवून डॉक्युमेंट व्हॉल्टमध्ये अपलोड आणि पडताळणी करा.",
            ],
        },
        "fallback": {
            "en": [
                "Widow pension schemes require an official Death Certificate from the Civil Registrar; hospital slips alone cannot replace it permanently.",
                "For older unregistered deaths, file a delayed-registration application under Section 13(3) of the RBD Act through Tehsil/SDM/CSC using two witness affidavits and cremation/hospital records.",
            ],
            "hi": [
                "विधवा पेंशन के लिए सिविल रजिस्ट्रार द्वारा जारी आधिकारिक मृत्यु प्रमाण पत्र अनिवार्य है; केवल अस्पताल की पर्ची पर्याप्त नहीं होती।",
                "यदि पुरानी मृत्यु दर्ज नहीं है, तो RBD अधिनियम की धारा 13(3) के तहत दो गवाह शपथपत्र व स्थानीय प्रमाण के साथ सीएससी/एसडीएम के माध्यम से विलंबित पंजीकरण कराएं।",
            ],
            "mr": [
                "विधवा निवृत्तीवेतन योजनेसाठी नागरी निबंधकाचे अधिकृत मृत्यू प्रमाणपत्र अनिवार्य असते; केवळ रुग्णालयाची चिठ्ठी पुरेशी नसते.",
                "जुनी नोंद नसल्यास RBD कायद्याच्या कलम १३(३) नुसार दोन साक्षीदारांचे प्रतिज्ञापत्र आणि स्थानिक पुराव्यांसह तहसीलदार/उपविभागीय अधिकाऱ्यांकडे विलंबित नोंदणी करा.",
            ],
        },
    },
    "bank_passbook": {
        "title": {"en": "Aadhaar-Seeded Bank Passbook / Account Proof", "hi": "आधार-सीडेड बैंक पासबुक / खाता विवरण", "mr": "आधार-संलग्न बँक पासबुक / खाते पुरावा"},
        "why": {
            "en": "Verifies active IFSC/account number and NPCI Aadhaar DBT seeding for direct electronic benefit transfers.",
            "hi": "प्रत्यक्ष डीबीटी भुगतान हेतु सक्रिय बैंक खाता संख्या, आईएफएससी कोड और आधार सीडिंग सत्यापित करने के लिए आवश्यक।",
            "mr": "थेट लाभ हस्तांतरणासाठी (DBT) सक्रिय बँक खाते क्रमांक, IFSC कोड आणि आधार संलग्नता तपासण्यासाठी आवश्यक.",
        },
        "where": {
            "en": "Your home branch of a Scheduled Commercial Bank, Regional Rural Bank, Cooperative Bank, or India Post Payments Bank.",
            "hi": "आपकी बैंक शाखा (राष्ट्रीयकृत, ग्रामीण, सहकारी बैंक अथवा इंडिया पोस्ट पेमेंट्स बैंक)।",
            "mr": "तुमचे खाते असलेल्या राष्ट्रीयीकृत, ग्रामीण, सहकारी बँक किंवा इंडिया पोस्ट पेमेंट्स बँकेची शाखा.",
        },
        "authority": {
            "en": "Account-holding Banking Institution (RBI regulated) / NPCI DBT Mapper",
            "hi": "संबंधित बैंक संस्थान (आरबीआई विनियमित) / एनपीसीआई डीबीटी मैपर",
            "mr": "संबंधित बँक संस्था (RBI नियंत्रित) / NPCI DBT मॅपर",
        },
        "portals": [{"label": "Department of Financial Services", "url": "https://financialservices.gov.in"}],
        "fee_verified": {
            "en": "Initial passbook issuance for savings / PMJDY zero-balance accounts is free.",
            "hi": "बचत / जन धन खाते पर प्रारंभिक पासबुक जारी करना निःशुल्क है।",
            "mr": "बचत / जन धन खात्यासाठी पहिले पासबुक मिळणे मोफत असते.",
        },
        "fee_estimated": None,
        "time_estimated": {
            "en": "Passbook print/update is usually same-day at bank counter; NPCI Aadhaar seeding typically activates in 2–5 working days.",
            "hi": "बैंक शाखा में पासबुक मुद्रण सामान्यतः उसी दिन; आधार डीबीटी सीडिंग सक्रिय होने में 2–5 कार्य दिवस।",
            "mr": "बँकेत पासबुक छपाई साधारणतः त्याच दिवशी; आधार DBT सीडिंग सक्रिय होण्यास २–५ कामाचे दिवस.",
        },
        "unavailable": {
            "en": [
                "Exact local bank branch address and duplicate passbook charges (depends on bank tariff).",
            ],
            "hi": [
                "आपकी स्थानीय बैंक शाखा का सटीक पता एवं बैंक के अनुसार डुप्लीकेट पासबुक शुल्क।",
            ],
            "mr": [
                "तुमच्या स्थानिक बँक शाखेचा नेमका पत्ता व बँकेनुसार दुय्यम पासबुकचे शुल्क.",
            ],
        },
        "steps": {
            "en": [
                "Take your Aadhaar Card and active ATM/account details to your bank branch (or open a zero-balance PMJDY account if you lack one).",
                "Ask the branch desk to print an updated front-page passbook or bank statement clearly showing Name, Account Number, and IFSC.",
                "Submit the Aadhaar-DBT seeding consent form so NPCI mapping is active.",
                "Upload the passbook page to Scheme Saathi's Document Vault and confirm extracted account details.",
            ],
            "hi": [
                "अपना आधार कार्ड लेकर बैंक शाखा जाएं (या खाता न होने पर शून्य-शेष जन धन खाता खुलवाएं)।",
                "नाम, खाता संख्या और आईएफएससी कोड दर्शाती हुई पासबुक प्रिंट या बैंक स्टेटमेंट लें।",
                "डीबीटी प्राप्त करने हेतु शाखा में आधार सीडिंग (NPCI मैपिंग) फॉर्म जमा करें।",
                "पासबुक के प्रथम पृष्ठ को डॉक्यूमेंट वॉल्ट में अपलोड कर समीक्षा व सत्यापन करें।",
            ],
            "mr": [
                "तुमचे आधार कार्ड घेऊन बँक शाखेत जा (खाते नसल्यास झिरो-बॅलन्स जन धन खाते उघडा).",
                "नाव, खाते क्रमांक आणि IFSC कोड स्पष्ट दिसणारे पासबुक प्रिंट किंवा बँक स्टेटमेंट घ्या.",
                "शाखेत आधार DBT सीडिंग (NPCI मॅपिंग) संमती अर्ज जमा करा.",
                "पासबुकचे पहिले पान डॉक्युमेंट व्हॉल्टमध्ये अपलोड करून तपासणी व पडताळणी पूर्ण करा.",
            ],
        },
        "fallback": {
            "en": [
                "Accepted bank account proofs across most schemes include a Cancelled Cheque or official Bank Account Statement showing IFSC and account holder name.",
                "If your commercial bank branch is far away, open an Aadhaar-seeded India Post Payments Bank (IPPB) account via your local Post Office.",
            ],
            "hi": [
                "अधिकांश योजनाओं में पासबुक के स्थान पर आईएफएससी और नाम वाला आधिकारिक बैंक स्टेटमेंट या रद्द चेक (Cancelled Cheque) भी मान्य होता है।",
                "यदि बैंक शाखा दूर है, तो नजदीकी डाकघर से इंडिया पोस्ट पेमेंट्स बैंक (IPPB) खाता तुरंत खुलवाया जा सकता है।",
            ],
            "mr": [
                "बहुतांश योजनांमध्ये पासबुकऐवजी खातेदाराचे नाव व IFSC असलेले अधिकृत बँक स्टेटमेंट किंवा रद्द केलेला धनादेश (Cancelled Cheque) देखील स्वीकारला जातो.",
                "बँक शाखा दूर असल्यास नजीकच्या पोस्ट ऑफिसमधून इंडिया पोस्ट पेमेंट्स बँकेत (IPPB) खाते उघडता येते.",
            ],
        },
    },
    "vending_certificate": {
        "title": {"en": "Certificate of Vending / Letter of Recommendation (LoR)", "hi": "वेंडिंग प्रमाण पत्र / सिफारिश पत्र (LoR)", "mr": "विक्री प्रमाणपत्र / शिफारस पत्र (LoR)"},
        "why": {
            "en": "Identifies eligible urban street vendors under the Street Vendors Act, 2014 for collateral-free PM-SVANidhi working capital loans.",
            "hi": "पीएम स्वनिधि योजना के अंतर्गत बिना गारंटी कार्यशील पूंजी ऋण हेतु शहरी पथविक्रेता पहचान प्रमाणित करने के लिए आवश्यक।",
            "mr": "पीएम स्वनिधी योजनेअंतर्गत विनातारण भांडवली कर्जासाठी शहरी पथविक्रेता ओळख सिद्ध करण्यासाठी आवश्यक.",
        },
        "where": {
            "en": "Urban Local Body (ULB / Municipal Corporation / Nagar Panchayat), Town Vending Committee (TVC), or online via PM-SVANidhi portal.",
            "hi": "शहरी स्थानीय निकाय (नगर निगम/नगर पालिका), टाउन वेंडिंग कमेटी (TVC) अथवा पीएम स्वनिधि ऑनलाइन पोर्टल।",
            "mr": "स्थानिक नागरी स्वराज्य संस्था (महानगरपालिका/नगरपालिका), टाऊन वेंडिंग समिती (TVC) किंवा पीएम स्वनिधी पोर्टल.",
        },
        "authority": {
            "en": "Urban Local Body (ULB) / Town Vending Committee (TVC), Ministry of Housing & Urban Affairs",
            "hi": "शहरी स्थानीय निकाय (ULB) / टाउन वेंडिंग कमेटी (TVC), आवासन एवं शहरी कार्य मंत्रालय",
            "mr": "नागरी स्थानिक स्वराज्य संस्था (ULB) / टाऊन वेंडिंग समिती (TVC)",
        },
        "portals": [{"label": "PM-SVANidhi Official Portal", "url": "https://pmsvanidhi.mohua.gov.in"}],
        "fee_verified": {
            "en": "Application and LoR issuance on the PM-SVANidhi / ULB portal is free.",
            "hi": "पीएम स्वनिधि / शहरी निकाय पोर्टल पर आवेदन और सिफारिश पत्र (LoR) जारी करना निःशुल्क है।",
            "mr": "पीएम स्वनिधी / नागरी संस्था पोर्टलवर अर्ज आणि शिफारस पत्र (LoR) प्रक्रिया मोफत आहे.",
        },
        "fee_estimated": None,
        "time_estimated": {
            "en": "Typically 15–30 days depending on Town Vending Committee verification.",
            "hi": "टाउन वेंडिंग कमेटी की जांच के अनुसार सामान्यतः 15–30 दिन।",
            "mr": "टाऊन वेंडिंग समितीच्या पडताळणीनुसार साधारणतः १५–३० दिवस.",
        },
        "unavailable": {
            "en": ["Exact municipal ward/ULB vending cell desk address and local TVC meeting dates."],
            "hi": ["आपके नगर निगम/पालिका के वेंडिंग सेल का सटीक पता और आगामी बैठक तिथि।"],
            "mr": ["तुमच्या मनपा/नगरपालिकेच्या फेरीवाला कक्षाचा नेमका पत्ता व समिती बैठकीची तारीख."],
        },
        "steps": {
            "en": [
                "Keep Aadhaar linked mobile number and past vending activity evidence (municipal receipts, vendor association receipt, or local proof).",
                "Check https://pmsvanidhi.mohua.gov.in to verify if your name appears in the ULB Street Vendor Survey list.",
                "If missing from the survey, submit an online request on the portal for a Letter of Recommendation (LoR) to your ULB.",
                "Download the Certificate of Vending or ULB-issued LoR and upload it to Document Vault.",
            ],
            "hi": [
                "आधार-लिंक्ड मोबाइल नंबर और व्यवसाय संबंधी पुराना प्रमाण रखें।",
                "https://pmsvanidhi.mohua.gov.in पर नगर सर्वेक्षण सूची में अपना नाम जांचें।",
                "नाम न होने पर पोर्टल से शहरी स्थानीय निकाय को सिफारिश पत्र (LoR) का ऑनलाइन अनुरोध भेजें।",
                "जारी हुआ LoR या वेंडिंग प्रमाण पत्र डॉक्यूमेंट वॉल्ट में अपलोड व सत्यापित करें।",
            ],
            "mr": [
                "आधार-संलग्न मोबाइल क्रमांक व विक्री व्यवसायाचा पुरावा सोबत ठेवा.",
                "https://pmsvanidhi.mohua.gov.in वर नागरी सर्वेक्षण यादीत तुमचे नाव तपासा.",
                "नावे यादीत नसल्यास पोर्टलवरून स्थानिक नागरी संस्थेकडे शिफारस पत्रासाठी (LoR) ऑनलाइन विनंती करा.",
                "प्राप्त झालेले विक्री प्रमाणपत्र किंवा LoR डॉक्युमेंट व्हॉल्टमध्ये अपलोड करून पडताळा.",
            ],
        },
        "fallback": {
            "en": [
                "Vendors left out of the original ULB survey do NOT have to wait for a full new survey — PM-SVANidhi expressly supports applying online for a Letter of Recommendation (LoR) from your ULB.",
            ],
            "hi": [
                "मूल शहरी सर्वेक्षण से छूटे हुए विक्रेताओं को नए सर्वे का इंतजार नहीं करना पड़ता — पीएम स्वनिधि पोर्टल पर सीधे शहरी निकाय से सिफारिश पत्र (LoR) के लिए आवेदन किया जा सकता है।",
            ],
            "mr": [
                "मूळ सर्वेक्षणात नाव नसलेल्या विक्रेत्यांना नवीन सर्वेक्षणाची वाट पाहण्याची गरज नाही — पीएम स्वनिधी पोर्टलवरून थेट स्थानिक नागरी संस्थेकडून शिफारस पत्रासाठी (LoR) अर्ज करता येतो.",
            ],
        },
    },
    "mcp_card": {
        "title": {"en": "Mother and Child Protection (MCP) Card", "hi": "मातृ एवं बाल सुरक्षा (MCP) कार्ड", "mr": "माता आणि बाल संरक्षण (MCP) कार्ड"},
        "why": {
            "en": "Statutory clinical record of pregnancy registration and ANC check-ups required under PMMVY and JSY.",
            "hi": "PMMVY और जननी सुरक्षा योजना के अंतर्गत गर्भावस्था पंजीकरण व प्रसवपूर्व जांच (ANC) का वैधानिक स्वास्थ्य प्रमाण।",
            "mr": "PMMVY आणि जननी सुरक्षा योजनेसाठी गर्भधारणा नोंदणी व आरोग्य तपासणीचा (ANC) वैधानिक पुरावा.",
        },
        "where": {
            "en": "Nearest Anganwadi Centre (AWC), ASHA worker, Primary Health Centre (PHC), or Government Hospital.",
            "hi": "नजदीकी आंगनवाड़ी केंद्र, आशा कार्यकर्ता, प्राथमिक स्वास्थ्य केंद्र (PHC) या सरकारी अस्पताल।",
            "mr": "जवळचे अंगणवाडी केंद्र, आशा सेविका, प्राथमिक आरोग्य केंद्र (PHC) किंवा शासकीय रुग्णालय.",
        },
        "authority": {
            "en": "Ministry of Health & Family Welfare / Ministry of Women & Child Development",
            "hi": "स्वास्थ्य एवं परिवार कल्याण मंत्रालय / महिला एवं बाल विकास मंत्रालय",
            "mr": "सार्वजनिक आरोग्य विभाग / महिला व बाल विकास विभाग",
        },
        "portals": [{"label": "PMMVY Official Portal", "url": "https://pmmvy.wcd.gov.in"}],
        "fee_verified": {
            "en": "Completely Free at all Anganwadi Centres and public healthcare facilities.",
            "hi": "सभी आंगनवाड़ी केंद्रों और सरकारी स्वास्थ्य केंद्रों पर पूर्णतः निःशुल्क।",
            "mr": "सर्व अंगणवाडी केंद्रे व शासकीय आरोग्य केंद्रांवर पूर्णपणे मोफत.",
        },
        "fee_estimated": None,
        "time_estimated": None,
        "unavailable": {
            "en": ["Exact address and timing of your local ward Anganwadi / PHC."],
            "hi": ["आपके मोहल्ले के स्थानीय आंगनवाड़ी / पीएचसी केंद्र का सटीक पता व समय।"],
            "mr": ["तुमच्या भागातील अंगणवाडी किंवा प्राथमिक आरोग्य केंद्राचा नेमका पत्ता."],
        },
        "steps": {
            "en": [
                "Visit your local Anganwadi worker, ASHA worker, or Government PHC with mother's Aadhaar Card.",
                "Complete pregnancy registration and obtain your filled MCP Card containing RCH ID and LMP/ANC entries (issued immediately at registration).",
                "Keep ANC check-up signatures updated and upload the MCP Card to Scheme Saathi's Document Vault.",
            ],
            "hi": [
                "माता का आधार कार्ड लेकर स्थानीय आंगनवाड़ी कार्यकर्ता, आशा या सरकारी पीएचसी केंद्र जाएं।",
                "गर्भावस्था पंजीकरण करवाकर RCH आईडी एवं ANC विवरण युक्त MCP कार्ड तुरंत प्राप्त करें।",
                "जांच प्रविष्टियां अद्यतन रखकर MCP कार्ड डॉक्यूमेंट वॉल्ट में अपलोड व सत्यापित करें।",
            ],
            "mr": [
                "मातेचे आधार कार्ड घेऊन स्थानिक अंगणवाडी सेविका, आशा सेविका किंवा शासकीय PHC केंद्रात जा.",
                "गर्भधारणा नोंदणी पूर्ण करून RCH आयडी व ANC नोंदी असलेले MCP कार्ड त्वरित प्राप्त करा.",
                "तपासणी नोंदी अद्ययावत ठेवून MCP कार्ड डॉक्युमेंट व्हॉल्टमध्ये अपलोड व पडताळणी करा.",
            ],
        },
        "fallback": {
            "en": [
                "MCP Card registration is free and mandatory for PMMVY/JSY; if a card was misplaced, ask your ANM/ASHA worker to retrieve your RCH ID record at the PHC and issue a duplicate card.",
            ],
            "hi": [
                "PMMVY/JSY हेतु MCP कार्ड अनिवार्य और निःशुल्क है; कार्ड खो जाने पर अपने PHC की एएनएम/आशा से RCH आईडी के आधार पर प्रतिलिपि कार्ड प्राप्त करें।",
            ],
            "mr": [
                "PMMVY/JSY साठी MCP कार्ड अनिवार्य व मोफत आहे; कार्ड हरवले असल्यास PHC मधील ANM/आशा सेविकेकडून तुमच्या RCH आयडीद्वारे नवीन प्रत मिळू शकते.",
            ],
        },
    },
    "caste_certificate": {
        "title": {"en": "Caste / Category Certificate", "hi": "जाति प्रमाण पत्र", "mr": "जातीचे प्रमाणपत्र"},
        "why": {
            "en": "Establishes SC/ST/OBC category eligibility for targeted welfare and scholarship schemes.",
            "hi": "आरक्षित वर्ग (SC/ST/OBC) की योजनाओं व छात्रवृत्तियों हेतु श्रेणी पात्रता प्रमाणित करने के लिए आवश्यक।",
            "mr": "SC/ST/OBC प्रवर्गातील विशेष योजना व शिष्यवृत्ती पात्रता सिद्ध करण्यासाठी आवश्यक.",
        },
        "where": {
            "en": "Tehsil / Sub-Divisional Magistrate (SDM) / SDO Office, CSC, or State e-District portal.",
            "hi": "तहसील / एसडीएम कार्यालय, सीएससी (CSC) या राज्य ई-डिस्ट्रिक्ट पोर्टल।",
            "mr": "तहसील / उपविभागीय अधिकारी (SDO) कार्यालय, आपले सरकार केंद्र किंवा ई-डिस्ट्रिक्ट पोर्टल.",
        },
        "authority": {
            "en": "State Revenue Department (SDM / SDO / Tahsildar)",
            "hi": "राज्य राजस्व विभाग (एसडीएम / तहसीलदार)",
            "mr": "राज्य महसूल विभाग (उपविभागीय अधिकारी / तहसीलदार)",
        },
        "portals": [
            {"label": "National Government Services Portal", "url": "https://services.india.gov.in"},
            {"label": "DigiLocker", "url": "https://digilocker.gov.in"},
        ],
        "fee_verified": None,
        "fee_estimated": {
            "en": "Typically ₹15–₹50 at authorized CSC / state e-District portals (varies by state).",
            "hi": "सीएससी / राज्य ई-डिस्ट्रिक्ट पोर्टल पर सामान्यतः ₹15–₹50 शुल्क (राज्यानुसार भिन्न)।",
            "mr": "सीएससी / आपले सरकार पोर्टलवर साधारणतः ₹१५–₹५० शुल्क (राज्यानुसार बदलते).",
        },
        "time_estimated": {
            "en": "Typically 15–30 working days after revenue genealogy/family verification.",
            "hi": "राजस्व एवं वंशावली जांच के पश्चात सामान्यतः 15–30 कार्य दिवस।",
            "mr": "महसूल व वंशावळ तपासणीनंतर साधारणतः १५–३० कामाचे दिवस.",
        },
        "unavailable": {
            "en": [
                "Exact local SDM/SDO counter address.",
                "Exact state-specific application fee schedule.",
            ],
            "hi": [
                "स्थानीय तहसील/एसडीएम कार्यालय का सटीक पता।",
                "आपके राज्य का सटीक निर्धारित शुल्क।",
            ],
            "mr": [
                "स्थानिक तहसील/SDO कार्यालयाचा नेमका पत्ता.",
                "तुमच्या राज्याचे नेमके शासकीय शुल्क.",
            ],
        },
        "steps": {
            "en": [
                "Collect Aadhaar, School Leaving / Birth record, and parent's/relative's caste record or old revenue extract.",
                "Apply online through State e-District / Aaple Sarkar portal (https://services.india.gov.in) or nearest CSC.",
                "Download the digitally signed certificate (also fetchable via DigiLocker) and upload to Document Vault.",
            ],
            "hi": [
                "आधार कार्ड, जन्म/स्कूल प्रमाण एवं माता-पिता/परिवार का जाति संबंधी पुराना रिकॉर्ड जुटाएं।",
                "राज्य ई-डिस्ट्रिक्ट पोर्टल (https://services.india.gov.in) या सीएससी के माध्यम से आवेदन करें।",
                "डिजिटल प्रमाण पत्र डाउनलोड कर डॉक्यूमेंट वॉल्ट में अपलोड व सत्यापित करें।",
            ],
            "mr": [
                "आधार कार्ड, शाळा सोडल्याचा दाखला/जन्म दाखला आणि वडिलांचा किंवा नातेवाईकांचा जुना जातीचा पुरावा गोळा करा.",
                "राज्य ई-डिस्ट्रिक्ट / आपले सरकार पोर्टल (https://services.india.gov.in) किंवा सीएससीद्वारे अर्ज करा.",
                "डिजिटल प्रमाणपत्र डाउनलोड करून डॉक्युमेंट व्हॉल्टमध्ये अपलोड व पडताळणी करा.",
            ],
        },
        "fallback": {
            "en": [
                "In schemes like PM-KISAN, Caste Certificate is only required if applying under SC/ST preference/validation; General/OBC applicants may not need it.",
                "For mandatory SC/ST schemes (such as PMS-SC or Stand-Up India SC/ST), submit parent's caste record or old revenue entry at Tehsil to obtain your official certificate.",
            ],
            "hi": [
                "PM-KISAN जैसी योजनाओं में जाति प्रमाण पत्र केवल SC/ST श्रेणी के संदर्भ में वैकल्पिक होता है।",
                "अनिवार्य SC/ST योजनाओं (जैसे PMS-SC या स्टैंड-अप इंडिया) हेतु पिता/परिवार के पुराने रिकॉर्ड के आधार पर तहसील से प्रमाण पत्र बनवाएं।",
            ],
            "mr": [
                "PM-KISAN सारख्या योजनांमध्ये जातीचा दाखला केवळ SC/ST प्रवर्गासाठी ऐच्छिक असतो.",
                "अनिवार्य SC/ST योजनांसाठी (जसे PMS-SC किंवा स्टँड-अप इंडिया) वडिलोपार्जित नोंदीच्या आधारे तहसील/SDO कार्यालयातून दाखला मिळवावा.",
            ],
        },
    },
    "domicile_certificate": {
        "title": {"en": "Domicile / Residence Certificate", "hi": "निवास / अधिवास प्रमाण पत्र", "mr": "अधिवास / रहिवासी प्रमाणपत्र"},
        "why": {
            "en": "Proof of state residency duration required for state-specific welfare schemes.",
            "hi": "राज्य-स्तरीय कल्याणकारी योजनाओं हेतु स्थायी निवास अवधि प्रमाणित करने के लिए आवश्यक।",
            "mr": "राज्यस्तरीय योजनांसाठी राज्याचे कायमस्वरूपी रहिवासी असल्याचा पुरावा सिद्ध करण्यासाठी आवश्यक.",
        },
        "where": {
            "en": "Tehsil / SDM / SDO Office, CSC / Aaple Sarkar center, or State e-District portal.",
            "hi": "तहसील / एसडीएम कार्यालय, सीएससी या राज्य ई-डिस्ट्रिक्ट पोर्टल।",
            "mr": "तहसील / SDO कार्यालय, आपले सरकार केंद्र किंवा राज्य ई-डिस्ट्रिक्ट पोर्टल.",
        },
        "authority": {
            "en": "State Revenue Department (Tahsildar / SDM / SDO)",
            "hi": "राज्य राजस्व विभाग (तहसीलदार / एसडीएम)",
            "mr": "राज्य महसूल विभाग (तहसीलदार / उपविभागीय अधिकारी)",
        },
        "portals": [{"label": "National Government Services Portal", "url": "https://services.india.gov.in"}],
        "fee_verified": None,
        "fee_estimated": {
            "en": "Typically ₹15–₹50 via CSC / e-District portal (varies by state).",
            "hi": "सीएससी / ई-डिस्ट्रिक्ट के माध्यम से सामान्यतः ₹15–₹50 शुल्क (राज्यानुसार भिन्न)।",
            "mr": "सीएससी / आपले सरकार द्वारे साधारणतः ₹१५–₹५० शुल्क (राज्यानुसार बदलते).",
        },
        "time_estimated": {
            "en": "Typically 7–15 working days depending on state citizen charter.",
            "hi": "सामान्यतः 7–15 कार्य दिवस (राज्यानुसार भिन्न)।",
            "mr": "साधारणतः ७–१५ कामाचे दिवस (राज्यानुसार बदलते).",
        },
        "unavailable": {
            "en": ["Exact local Tehsil/CSC street address and state-specific fee table."],
            "hi": ["स्थानीय तहसील/सीएससी का सटीक पता व राज्य-वार सटीक शुल्क तालिका।"],
            "mr": ["स्थानिक तहसील/सीएससी केंद्राचा नेमका पत्ता व राज्यानुसार नेमके शुल्क."],
        },
        "steps": {
            "en": [
                "Gather Aadhaar Card, continuous residence proof (Ration Card, School Leaving Certificate, Electricity/Water bill or Birth Certificate), and self-declaration.",
                "Apply online on State e-District / Aaple Sarkar (https://services.india.gov.in) or via nearest CSC.",
                "Download the signed Domicile Certificate and upload it to Document Vault.",
            ],
            "hi": [
                "आधार कार्ड, निरंतर निवास प्रमाण (राशन कार्ड, स्कूल टीसी, बिजली बिल या जन्म प्रमाण) व स्व-घोषणा तैयार रखें।",
                "राज्य ई-डिस्ट्रिक्ट पोर्टल (https://services.india.gov.in) या सीएससी से आवेदन करें।",
                "प्राप्त निवास प्रमाण पत्र को डॉक्यूमेंट वॉल्ट में अपलोड व सत्यापित करें।",
            ],
            "mr": [
                "आधार कार्ड, दीर्घकालीन वास्तव्याचा पुरावा (रेशन कार्ड, शाळा सोडल्याचा दाखला, वीज बिल किंवा जन्म दाखला) व स्वयंघोषणापत्र तयार ठेवा.",
                "राज्य ई-डिस्ट्रिक्ट / आपले सरकार पोर्टल (https://services.india.gov.in) किंवा सीएससीद्वारे अर्ज करा.",
                "प्राप्त झालेला अधिवास दाखला डॉक्युमेंट व्हॉल्टमध्ये अपलोड व पडताळणी करा.",
            ],
        },
        "fallback": {
            "en": [
                "Under Maharashtra MLBY-MH guidelines, if you do not have a Domicile Certificate, a 15-year old Ration Card, 15-year old Voter ID, State Birth Certificate, or School Leaving Certificate is accepted as an official alternative.",
            ],
            "hi": [
                "महाराष्ट्र MLBY-MH दिशानिर्देशों के तहत अधिवास प्रमाण पत्र न होने पर 15 वर्ष पुराना राशन कार्ड, मतदाता पहचान पत्र, जन्म प्रमाण पत्र या स्कूल टीसी मान्य विकल्प हैं।",
            ],
            "mr": [
                "महाराष्ट्र लाडकी बहीण योजनेअंतर्गत (MLBY-MH) अधिवास प्रमाणपत्र नसल्यास १५ वर्षे जुने रेशन कार्ड, मतदान ओळखपत्र, जन्म दाखला किंवा शाळा सोडल्याचा दाखला अधिकृत पर्याय म्हणून चालतो.",
            ],
        },
    },
    "ration_card": {
        "title": {"en": "Ration Card (Family Identity / BPL / Antyodaya)", "hi": "राशन कार्ड (पारिवारिक पहचान / बीपीएल)", "mr": "रेशन कार्ड (कुटुंब ओळख / पिवळे / केशरी)"},
        "why": {
            "en": "Establishes household composition, family ID linkage, and socioeconomic status for food/health/welfare schemes.",
            "hi": "परिवार की संरचना, सदस्य पहचान और सामाजिक-आर्थिक श्रेणी सिद्ध करने हेतु आवश्यक।",
            "mr": "कुटुंबातील सदस्य संख्या आणि सामाजिक-आर्थिक प्रवर्ग सिद्ध करण्यासाठी आवश्यक.",
        },
        "where": {
            "en": "District Food & Civil Supplies Office, Tehsil Supply Officer, Authorized CSC, or State NFSA Food Portal.",
            "hi": "जिला खाद्य एवं रसद कार्यालय, तहसील आपूर्ति कार्यालय, सीएससी या राज्य खाद्य पोर्टल।",
            "mr": "जिल्हा/तहसील पुरवठा अधिकारी कार्यालय, सेतू केंद्र किंवा राज्य अन्न व नागरी पुरवठा पोर्टल.",
        },
        "authority": {
            "en": "State Department of Food, Civil Supplies & Consumer Protection (NFSA)",
            "hi": "राज्य खाद्य एवं नागरिक आपूर्ति विभाग (NFSA)",
            "mr": "राज्य अन्न, नागरी पुरवठा व ग्राहक संरक्षण विभाग (NFSA)",
        },
        "portals": [
            {"label": "NFSA National Food Security Portal", "url": "https://nfsa.gov.in"},
            {"label": "DigiLocker", "url": "https://digilocker.gov.in"},
        ],
        "fee_verified": None,
        "fee_estimated": {
            "en": "Typically ₹10–₹50 as per state Civil Supplies notification.",
            "hi": "राज्य खाद्य विभाग के नियमानुसार सामान्यतः ₹10–₹50 शुल्क।",
            "mr": "राज्य पुरवठा विभागाच्या नियमानुसार साधारणतः ₹१०–₹५० शुल्क.",
        },
        "time_estimated": {
            "en": "Typically 15–30 working days after field inspection by Food Inspector.",
            "hi": "खाद्य निरीक्षक की जांच के उपरांत सामान्यतः 15–30 कार्य दिवस।",
            "mr": "पुरवठा निरीक्षक तपासणीनंतर साधारणतः १५–३० कामाचे दिवस.",
        },
        "unavailable": {
            "en": ["Exact local Rationing / Tehsil Supply Office street address and exact state fee."],
            "hi": ["स्थानीय राशन/आपूर्ति कार्यालय का सटीक पता व सटीक स्थानीय शुल्क।"],
            "mr": ["स्थानिक शिधावाटप / पुरवठा कार्यालयाचा नेमका पत्ता व नेमके राज्य शुल्क."],
        },
        "steps": {
            "en": [
                "Collect Aadhaar cards of all family members, passport photo of head of family, and residence/income declaration.",
                "Apply through your State Food Portal (listed via https://nfsa.gov.in) or nearest Tehsil Supply / CSC center.",
                "Once approved, download digital Ration Card (e-Ration / DigiLocker) and upload to Document Vault.",
            ],
            "hi": [
                "सभी परिवार सदस्यों के आधार कार्ड, मुखिया का फोटो एवं निवास/आय विवरण एकत्र करें।",
                "राज्य खाद्य पोर्टल (https://nfsa.gov.in पर लिंक उपलब्ध) या नजदीकी सीएससी/आपूर्ति कार्यालय में आवेदन करें।",
                "जारी ई-राशन कार्ड डाउनलोड कर डॉक्यूमेंट वॉल्ट में अपलोड व सत्यापित करें।",
            ],
            "mr": [
                "कुटुंबातील सर्व सदस्यांचे आधार कार्ड, कुटुंब प्रमुखाचा फोटो व निवास/उत्पन्न माहिती गोळा करा.",
                "राज्य अन्न व पुरवठा पोर्टल (https://nfsa.gov.in वर उपलब्ध) किंवा तहसील पुरवठा/सीएससी केंद्राद्वारे अर्ज करा.",
                "मंजूर झालेले ई-रेशन कार्ड डाउनलोड करून डॉक्युमेंट व्हॉल्टमध्ये अपलोड व पडताळणी करा.",
            ],
        },
        "fallback": {
            "en": [
                "If misplaced, download digital e-Ration Card instantly via State Food Portal / DigiLocker using your Aadhaar or RC number.",
                "For AB-PMJAY, Ration Card is optional if family linkage is already verified in SECC/PMJAY database via Aadhaar e-KYC.",
            ],
            "hi": [
                "खो जाने पर आधार/कार्ड नंबर से DigiLocker या राज्य खाद्य पोर्टल से ई-राशन कार्ड तुरंत डाउनलोड करें।",
                "AB-PMJAY में यदि SECC/PMJAY डेटाबेस में आधार ई-केवाईसी से परिवार जुड़ा है, तो राशन कार्ड वैकल्पिक हो सकता है।",
            ],
            "mr": [
                "हरवले असल्यास DigiLocker किंवा राज्य अन्न पोर्टलवरून आधार क्रमांकाद्वारे ई-रेशन कार्ड त्वरित डाउनलोड करता येते.",
                "AB-PMJAY मध्ये SECC डेटाबेसमध्ये आधार e-KYC द्वारे कुटुंब नोंद असल्यास रेशन कार्ड ऐच्छिक ठरू शकते.",
            ],
        },
    },
    "job_card": {
        "title": {"en": "MGNREGA Job Card", "hi": "मनरेगा जॉब कार्ड", "mr": "मनरेगा जॉब कार्ड"},
        "why": {
            "en": "Establishes rural household registration under MGNREGA for guaranteed wage employment and PMAY-G 90/95-day labour convergence.",
            "hi": "मनरेगा के अंतर्गत रोजगार गारंटी एवं PMAY-G में 90/95 दिनों की मजदूरी सहायता जोड़ने हेतु आवश्यक।",
            "mr": "मनरेगा अंतर्गत रोजगार हमी तसेच PMAY-G घरकुल योजनेत ९०/९५ दिवसांच्या मजुरी संलग्नतेसाठी आवश्यक.",
        },
        "where": {
            "en": "Local Gram Panchayat Office (Rozgar Sevak / Sarpanch / Gram Sachiv) or Block Development Officer (BDO).",
            "hi": "स्थानीय ग्राम पंचायत कार्यालय (ग्राम रोजगार सेवक / सचिव) अथवा ब्लॉक विकास अधिकारी (BDO) कार्यालय।",
            "mr": "स्थानिक ग्रामपंचायत कार्यालय (ग्रामरोजगार सेवक / ग्रामसेवक) किंवा पंचायत समिती (गटविकास अधिकारी).",
        },
        "authority": {
            "en": "Gram Panchayat / Block Programme Officer (Mahatma Gandhi NREGA)",
            "hi": "ग्राम पंचायत / प्रखंड कार्यक्रम अधिकारी (मनरेगा)",
            "mr": "ग्रामपंचायत / गट कार्यक्रम अधिकारी (मनरेगा)",
        },
        "portals": [{"label": "MGNREGA Official Portal", "url": "https://nrega.nic.in"}],
        "fee_verified": {
            "en": "Completely Free under the Mahatma Gandhi National Rural Employment Guarantee Act.",
            "hi": "महात्मा गांधी राष्ट्रीय ग्रामीण रोजगार गारंटी अधिनियम के अंतर्गत पूर्णतः निःशुल्क।",
            "mr": "महात्मा गांधी राष्ट्रीय ग्रामीण रोजगार हमी कायद्यांतर्गत पूर्णपणे मोफत.",
        },
        "fee_estimated": None,
        "time_verified": {
            "en": "Must be issued within 15 days of written application to the Gram Panchayat (statutory MGNREGA entitlement).",
            "hi": "ग्राम पंचायत में आवेदन के 15 दिनों के भीतर जारी किया जाना वैधानिक रूप से अनिवार्य है।",
            "mr": "ग्रामपंचायतीकडे अर्ज केल्यापासून १५ दिवसांच्या आत जॉब कार्ड देणे कायदेशीररीत्या बंधनकारक आहे.",
        },
        "unavailable": {
            "en": ["Exact Gram Panchayat office location and daily Rozgar Sevak sitting hours."],
            "hi": ["आपके ग्राम पंचायत कार्यालय का सटीक पता और रोजगार सेवक के मिलने का समय।"],
            "mr": ["तुमच्या ग्रामपंचायत कार्यालयाचा नेमका पत्ता व ग्रामरोजगार सेवकाची उपलब्धता."],
        },
        "steps": {
            "en": [
                "Take Aadhaar, Bank Passbook, and photos of adult household members willing to do unskilled manual work.",
                "Submit an application (oral or written) at your local Gram Panchayat or Block office and get a dated receipt.",
                "Collect the Job Card within 15 days and upload it to Scheme Saathi's Document Vault.",
            ],
            "hi": [
                "इच्छुक वयस्क सदस्यों के आधार कार्ड, बैंक पासबुक और फोटो एकत्र करें।",
                "अपनी ग्राम पंचायत या ब्लॉक कार्यालय में आवेदन देकर दिनांकित पावती प्राप्त करें।",
                "15 दिनों के भीतर जॉब कार्ड प्राप्त कर डॉक्यूमेंट वॉल्ट में अपलोड व सत्यापित करें।",
            ],
            "mr": [
                "कुटुंबातील इच्छुक प्रौढ सदस्यांचे आधार कार्ड, बँक पासबुक आणि फोटो सोबत ठेवा.",
                "तुमच्या ग्रामपंचायत किंवा पंचायत समितीत अर्ज देऊन दिनांकित पोचपावती घ्या.",
                "१५ दिवसांत जॉब कार्ड प्राप्त करून डॉक्युमेंट व्हॉल्टमध्ये अपलोड व पडताळणी करा.",
            ],
        },
        "fallback": {
            "en": [
                "Under PMAY-G, MGNREGA Job Card is ONLY required if your household is already registered for MGNREGA 90/95-day unskilled wage convergence; otherwise you can proceed without it.",
                "For MGNREGA work itself, every rural household is legally entitled to apply free at the Gram Panchayat and receive a card within 15 days.",
            ],
            "hi": [
                "PMAY-G में मनरेगा जॉब कार्ड केवल तभी आवश्यक है जब आप 90/95 दिनों की मजदूरी सहायता लेना चाहते हैं; अन्यथा यह बाध्यकारी नहीं है।",
                "मनरेगा कार्य हेतु प्रत्येक ग्रामीण परिवार ग्राम पंचायत में निःशुल्क आवेदन कर 15 दिन में कार्ड प्राप्त करने का वैधानिक हकदार है।",
            ],
            "mr": [
                "PMAY-G मध्ये मनरेगा जॉब कार्ड फक्त तुम्ही ९०/९५ दिवसांच्या मजुरीचा लाभ घेत असाल तरच आवश्यक असते; अन्यथा ते बंधनकारक नाही.",
                "प्रत्येक ग्रामीण कुटुंब ग्रामपंचायतीकडे मोफत अर्ज करून १५ दिवसांत जॉब कार्ड मिळवण्यास कायदेशीर पात्र आहे.",
            ],
        },
    },
    "marksheet_12th": {
        "title": {"en": "Class 12 Passing Marksheet & Certificate", "hi": "12वीं कक्षा की अंकतालिका एवं प्रमाण पत्र", "mr": "१२वी उत्तीर्ण गुणपत्रिका व प्रमाणपत्र"},
        "why": {
            "en": "Verifies Class 12 academic merit (above 80th percentile) and roll number for National Scholarship Portal (NSP-CSSS).",
            "hi": "राष्ट्रीय छात्रवृत्ति (NSP-CSSS) हेतु कक्षा 12 की मेरिट (80वें पर्सेंटाइल से अधिक) और रोल नंबर सत्यापित करने के लिए आवश्यक।",
            "mr": "राष्ट्रीय शिष्यवृत्ती (NSP-CSSS) साठी इयत्ता १२वी ची गुणवत्ता (८० पर्सेंटाईलपेक्षा जास्त) व बैठक क्रमांक तपासण्यासाठी आवश्यक.",
        },
        "where": {
            "en": "Respective Higher Secondary School / Junior College, State/Central Education Board, or DigiLocker.",
            "hi": "संबंधित उच्च माध्यमिक विद्यालय / कॉलेज, शिक्षा बोर्ड या डिजिलॉकर (DigiLocker)।",
            "mr": "संबंधित कनिष्ठ महाविद्यालय / शाळा, शिक्षण मंडळ किंवा डिजीलॉकर (DigiLocker).",
        },
        "authority": {
            "en": "State Secondary & Higher Secondary Education Board, CBSE, or CISCE",
            "hi": "राज्य माध्यमिक एवं उच्च माध्यमिक शिक्षा बोर्ड, CBSE या CISCE",
            "mr": "राज्य माध्यमिक व उच्च माध्यमिक शिक्षण मंडळ, CBSE किंवा CISCE",
        },
        "portals": [{"label": "DigiLocker Portal", "url": "https://digilocker.gov.in"}],
        "fee_verified": {
            "en": "Digital verified fetch via DigiLocker and original distribution by school are free.",
            "hi": "डिजिलॉकर द्वारा डिजिटल अंकतालिका प्राप्त करना तथा विद्यालय से मूल प्रति मिलना निःशुल्क है।",
            "mr": "डिजीलॉकरवरून डिजिटल गुणपत्रिका मिळणे आणि शाळेतून मूळ प्रत मिळणे मोफत असते.",
        },
        "fee_estimated": None,
        "time_estimated": {
            "en": "Instant download on DigiLocker for recent board exams; duplicate board copies take longer per board rules.",
            "hi": "हाल की बोर्ड परीक्षाओं हेतु डिजिलॉकर पर तुरंत उपलब्ध; डुप्लीकेट प्रति हेतु बोर्ड नियमानुसार समय लगता है।",
            "mr": "नुकत्याच झालेल्या परीक्षांसाठी डिजीलॉकरवर त्वरित उपलब्ध; दुय्यम प्रतीसाठी मंडळाच्या नियमांनुसार कालावधी लागतो.",
        },
        "unavailable": {
            "en": ["Duplicate physical marksheet replacement fee (varies by State Education Board / CBSE)."],
            "hi": ["बोर्ड से डुप्लीकेट भौतिक अंकतालिका निकलवाने का सटीक शुल्क (संबंधित बोर्ड पर निर्भर)।"],
            "mr": ["शिक्षण मंडळाकडून दुय्यम छापील गुणपत्रिका मिळण्याचे नेमके शुल्क (मंडळानुसार बदलते)."],
        },
        "steps": {
            "en": [
                "Keep your Class 12 Board Roll Number, passing year, and Aadhaar-linked DigiLocker account ready.",
                "Sign in to https://digilocker.gov.in -> Search Issued Documents -> select your Education Board to fetch the digitally signed marksheet.",
                "If awaiting physical copy, collect an attested copy from your school Principal and upload to Document Vault.",
            ],
            "hi": [
                "अपना 12वीं बोर्ड रोल नंबर, उत्तीर्ण वर्ष और डिजिलॉकर खाता तैयार रखें।",
                "https://digilocker.gov.in पर लॉग इन करके अपने बोर्ड की डिजिटल हस्ताक्षरित अंकतालिका डाउनलोड करें।",
                "भौतिक प्रति न होने पर विद्यालय प्राचार्य से सत्यापित प्रति लें और डॉक्यूमेंट वॉल्ट में अपलोड करें।",
            ],
            "mr": [
                "तुमचा १२वीचा बैठक क्रमांक, उत्तीर्ण वर्ष आणि डिजीलॉकर खाते तयार ठेवा.",
                "https://digilocker.gov.in वर लॉग इन करून संबंधित मंडळाची डिजिटल स्वाक्षरीकृत गुणपत्रिका डाउनलोड करा.",
                "मूळ प्रत नसल्यास महाविद्यालय प्राचार्यांकडून प्रमाणित प्रत घेऊन डॉक्युमेंट व्हॉल्टमध्ये अपलोड करा.",
            ],
        },
        "fallback": {
            "en": [
                "A digitally signed DigiLocker marksheet is legally equivalent to the physical marksheet for NSP-CSSS verification.",
                "If lost and unavailable on DigiLocker, apply via your school Principal to the Education Board for a duplicate marksheet.",
            ],
            "hi": [
                "NSP-CSSS सत्यापन हेतु डिजिलॉकर की डिजिटल अंकतालिका मूल प्रति के समान ही वैध मानी जाती है।",
                "डिजिलॉकर में उपलब्ध न होने पर विद्यालय के माध्यम से बोर्ड से डुप्लीकेट प्रति हेतु आवेदन करें।",
            ],
            "mr": [
                "NSP-CSSS पडताळणीसाठी डिजीलॉकरवरील डिजिटल गुणपत्रिका मूळ प्रतीइतकीच कायदेशीर वैध मानली जाते.",
                "डिजीलॉकरवर उपलब्ध नसल्यास शाळेमार्फत मंडळाकडे दुय्यम गुणपत्रिकेसाठी अर्ज करा.",
            ],
        },
    },
    "pan_card": {
        "title": {"en": "PAN Card", "hi": "पैन (PAN) कार्ड", "mr": "पॅन (PAN) कार्ड"},
        "why": {
            "en": "Statutory tax and KYC identity proof required for MSME/Mudra credit, PMEGP, and Sukanya Samriddhi guardian accounts.",
            "hi": "मुद्रा, PMEGP और सूक्ष्म उद्यम ऋण / खाता केवाईसी सत्यापन हेतु वैधानिक पहचान प्रमाण।",
            "mr": "मुद्रा, PMEGP आणि सूक्ष्म उद्योग कर्ज / केवायसी पडताळणीसाठी वैधानिक ओळख पुरावा.",
        },
        "where": {
            "en": "Income Tax e-Filing portal (Instant e-PAN), authorized PAN service centers (Protean/UTIITSL), or CSC.",
            "hi": "आयकर ई-फाइलिंग पोर्टल (इंस्टेंट ई-पैन), अधिकृत पैन सेवा केंद्र या सीएससी।",
            "mr": "आयकर ई-फायलिंग पोर्टल (ई-पॅन), अधिकृत पैन सेवा केंद्र किंवा सीएससी.",
        },
        "authority": {
            "en": "Income Tax Department, Ministry of Finance",
            "hi": "आयकर विभाग, वित्त मंत्रालय",
            "mr": "आयकर विभाग, वित्त मंत्रालय",
        },
        "portals": [{"label": "Income Tax e-Filing Portal", "url": "https://www.incometax.gov.in"}],
        "fee_verified": {
            "en": "Instant e-PAN issued via Aadhaar OTP on the Income Tax e-Filing portal is Free.",
            "hi": "आयकर ई-फाइलिंग पोर्टल पर आधार ओटीपी द्वारा जारी इंस्टेंट ई-पैन निःशुल्क है।",
            "mr": "आयकर ई-फायलिंग पोर्टलवर आधार ओटीपीद्वारे त्वरित ई-पॅन काढणे मोफत आहे.",
        },
        "fee_estimated": None,
        "time_estimated": {
            "en": "Instant to 24 hours for Aadhaar-based digital e-PAN; physical card dispatch takes longer.",
            "hi": "आधार आधारित डिजिटल ई-पैन तुरंत से 24 घंटे में; भौतिक कार्ड डाक द्वारा आने में अधिक समय लगता है।",
            "mr": "आधार आधारित डिजिटल ई-पॅन त्वरित ते २४ तासांत मिळते; छापील कार्ड पोस्टाने येण्यास अधिक वेळ लागतो.",
        },
        "unavailable": {
            "en": [
                "Exact physical PAN reprint/dispatch fee via Protean/UTIITSL (verify directly on official portal).",
                "Nearest local PAN facilitation center street address.",
            ],
            "hi": [
                "भौतिक पैन कार्ड प्रिंट/डाक शुल्क (आधिकारिक पोर्टल पर जांचें)।",
                "नजदीकी पैन सेवा केंद्र का सटीक सड़क पता।",
            ],
            "mr": [
                "छापील पॅन कार्ड पोस्ट फी (अधिकृत पोर्टलवर तपासा).",
                "जवळच्या पॅन सेवा केंद्राचा नेमका पत्ता.",
            ],
        },
        "steps": {
            "en": [
                "Ensure your Aadhaar number has an active linked mobile number for OTP.",
                "Visit https://www.incometax.gov.in -> Instant e-PAN to generate a free PDF PAN using Aadhaar e-KYC.",
                "Download the e-PAN PDF and upload it to Scheme Saathi's Document Vault.",
            ],
            "hi": [
                "सुनिश्चित करें कि आपके आधार से सक्रिय मोबाइल नंबर जुड़ा है।",
                "https://www.incometax.gov.in पर 'Instant e-PAN' चुनें और आधार ओटीपी से निःशुल्क ई-पैन बनाएं।",
                "ई-पैन पीडीएफ डाउनलोड कर डॉक्यूमेंट वॉल्ट में अपलोड व सत्यापित करें।",
            ],
            "mr": [
                "तुमच्या आधार कार्डशी सक्रिय मोबाइल क्रमांक जोडलेला असल्याची खात्री करा.",
                "https://www.incometax.gov.in वरील 'Instant e-PAN' सुविधेद्वारे आधार ओटीपीने मोफत ई-पॅन मिळवा.",
                "ई-पॅन पीडीएफ डाउनलोड करून डॉक्युमेंट व्हॉल्टमध्ये अपलोड व पडताळणी करा.",
            ],
        },
        "fallback": {
            "en": [
                "A free digital e-PAN PDF (generated via Income Tax Instant e-PAN or DigiLocker) is legally valid across banks and MSME portals.",
            ],
            "hi": [
                "आयकर पोर्टल या डिजिलॉकर से प्राप्त डिजिटल ई-पैन पीडीएफ सभी बैंकों और सरकारी योजनाओं में कानूनी रूप से मान्य है।",
            ],
            "mr": [
                "आयकर पोर्टल किंवा डिजीलॉकरवरून घेतलेले डिजिटल ई-पॅन सर्व बँका व योजनांसाठी कायदेशीररीत्या वैध मानले जाते.",
            ],
        },
    },
    "birth_certificate": {
        "title": {"en": "Birth Certificate", "hi": "जन्म प्रमाण पत्र", "mr": "जन्म प्रमाणपत्र"},
        "why": {
            "en": "Establishes minor age eligibility (under 10 years) for Sukanya Samriddhi Yojana account opening.",
            "hi": "सुकन्या समृद्धि योजना हेतु बालिका की आयु (10 वर्ष से कम) सिद्ध करने का वैधानिक प्रमाण।",
            "mr": "सुकन्या समृद्धी योजनेसाठी मुलीच्या वयाची (१० वर्षांखालील) खात्री करण्यासाठी वैधानिक पुरावा.",
        },
        "where": {
            "en": "Municipal Corporation / Municipality Registrar (urban) or Gram Panchayat / CRS portal (rural).",
            "hi": "नगर निगम / नगर पालिका रजिस्ट्रार या ग्राम पंचायत / सीआरएस पोर्टल।",
            "mr": "महानगरपालिका / नगरपालिका निबंधक किंवा ग्रामपंचायत / CRS पोर्टल.",
        },
        "authority": {
            "en": "Registrar of Births and Deaths (RBD Act, 1969)",
            "hi": "जन्म एवं मृत्यु रजिस्ट्रार",
            "mr": "जन्म आणि मृत्यू निबंधक",
        },
        "portals": [{"label": "Civil Registration System (CRS)", "url": "https://crsorgi.gov.in"}],
        "fee_verified": {
            "en": "Registration within 21 days of birth is free.",
            "hi": "जन्म के 21 दिनों के भीतर पंजीकरण निःशुल्क है।",
            "mr": "जन्मानंतर २१ दिवसांच्या आत नोंदणी मोफत असते.",
        },
        "fee_estimated": None,
        "time_estimated": {
            "en": "Typically 7–15 working days from application (instant download if already on CRS).",
            "hi": "आवेदन से सामान्यतः 7–15 कार्य दिवस।",
            "mr": "अर्जापासून साधारणतः ७–१५ कामाचे दिवस.",
        },
        "unavailable": {
            "en": [
                "Exact municipal ward/Gram Panchayat address and state-specific delayed-copy fee.",
            ],
            "hi": [
                "स्थानीय नगर पालिका / ग्राम पंचायत कार्यालय का सटीक पता व विलंबित नकल शुल्क।",
            ],
            "mr": [
                "स्थानिक प्रभाग / ग्रामपंचायत कार्यालयाचा नेमका पत्ता व विलंबित प्रतीचे शुल्क.",
            ],
        },
        "steps": {
            "en": [
                "Collect hospital discharge/birth report and parents' Aadhaar cards.",
                "Check https://crsorgi.gov.in or apply at the local Municipal/Gram Panchayat Registrar.",
                "Download the signed Birth Certificate and upload to Document Vault.",
            ],
            "hi": [
                "अस्पताल जन्म प्रमाण व माता-पिता के आधार कार्ड एकत्र करें।",
                "https://crsorgi.gov.in पर जांचें या स्थानीय नगर निगम/ग्राम पंचायत रजिस्ट्रार कार्यालय में आवेदन करें।",
                "प्रमाण पत्र डाउनलोड कर डॉक्यूमेंट वॉल्ट में अपलोड व सत्यापित करें।",
            ],
            "mr": [
                "रुग्णालयाचा जन्म दाखला आणि पालकांचे आधार कार्ड गोळा करा.",
                "https://crsorgi.gov.in वर नोंद तपासा किंवा मनपा/ग्रामपंचायत निबंधकाकडे अर्ज करा.",
                "प्रमाणपत्र डाउनलोड करून डॉक्युमेंट व्हॉल्टमध्ये अपलोड व पडताळणी करा.",
            ],
        },
        "fallback": {
            "en": [
                "If birth was not registered within 1 year, submit hospital/school birth evidence and parents' affidavit to SDM/Tahsildar for a delayed Birth Certificate.",
            ],
            "hi": [
                "यदि 1 वर्ष के भीतर पंजीकरण नहीं हुआ है, तो अस्पताल/स्कूल प्रमाण एवं शपथपत्र के साथ एसडीएम/तहसीलदार के पास विलंबित पंजीकरण आवेदन दें।",
            ],
            "mr": [
                "१ वर्षाच्या आत नोंदणी झाली नसल्यास रुग्णालय/शाळेचा दाखला व प्रतिज्ञापत्रासह उपविभागीय अधिकारी/तहसीलदारांकडे विलंबित नोंदणी करा.",
            ],
        },
    },
    "bonafide_certificate": {
        "title": {"en": "Institution / Bonafide Student Certificate", "hi": "शैक्षणिक संस्थान / बोनाफाइड प्रमाण पत्र", "mr": "शाळा / महाविद्यालय बोनाफाईड प्रमाणपत्र"},
        "why": {
            "en": "Confirms active regular enrolment in a recognized school/college for scholarship verification.",
            "hi": "छात्रवृत्ति सत्यापन हेतु मान्यता प्राप्त विद्यालय/महाविद्यालय में नियमित अध्ययन प्रमाणित करने के लिए आवश्यक।",
            "mr": "शिष्यवृत्ती पडताळणीसाठी मान्यताप्राप्त शाळा/महाविद्यालयात नियमित प्रवेश असल्याचे सिद्ध करण्यासाठी आवश्यक.",
        },
        "where": {
            "en": "Academic / Administrative Office of your currently enrolled School, College, or University.",
            "hi": "आपके वर्तमान विद्यालय, महाविद्यालय या विश्वविद्यालय का प्रशासनिक/छात्रवृत्ति कार्यालय।",
            "mr": "तुमच्या सध्याच्या शाळा, महाविद्यालय किंवा विद्यापीठाचे कार्यालय.",
        },
        "authority": {
            "en": "Principal / Headmaster / Registrar of Enrolled Educational Institution",
            "hi": "संबंधित शैक्षणिक संस्थान के प्राचार्य / प्रधानाचार्य",
            "mr": "संबंधित शैक्षणिक संस्थेचे प्राचार्य / मुख्याध्यापक",
        },
        "portals": [{"label": "National Scholarship Portal (NSP)", "url": "https://scholarships.gov.in"}],
        "fee_verified": None,
        "fee_estimated": None,
        "time_estimated": None,
        "unavailable": {
            "en": [
                "Exact institutional administrative fee (many public institutions issue it free; private colleges vary).",
                "Exact processing days (depends on your school/college administration).",
                "Your college counter address and hours.",
            ],
            "hi": [
                "संस्थान का सटीक प्रशासनिक शुल्क (अधिकांश सरकारी संस्थान निःशुल्क देते हैं)।",
                "प्रसंस्करण समय (संबंधित कॉलेज/स्कूल प्रशासन पर निर्भर)।",
                "संस्थान कार्यालय का कक्ष विवरण।",
            ],
            "mr": [
                "शैक्षणिक संस्थेचे नेमके प्रशासकीय शुल्क व प्रमाणपत्र मिळण्याचा नेमका कालावधी (महाविद्यालयानुसार बदलतो).",
                "तुमच्या महाविद्यालय कार्यालयाचा नेमका कक्ष क्रमांक व वेळ.",
            ],
        },
        "steps": {
            "en": [
                "Carry your College/School ID card and current academic fee receipt.",
                "Request an official Bonafide Certificate (or NSP verification form stamp) from your institution's office.",
                "Ensure Principal signature, seal, and AISHE/UDISE code are visible, then upload to Document Vault.",
            ],
            "hi": [
                "अपना कॉलेज/स्कूल पहचान पत्र एवं चालू सत्र की शुल्क रसीद लेकर संस्थान कार्यालय जाएं।",
                "प्राचार्य के हस्ताक्षर, मुहर और संस्था कोड युक्त बोनाफाइड प्रमाण पत्र प्राप्त करें।",
                "दस्तावेज़ को डॉक्यूमेंट वॉल्ट में अपलोड व सत्यापित करें।",
            ],
            "mr": [
                "तुमचे शाळा/महाविद्यालय ओळखपत्र आणि चालू शैक्षणिक शुल्क पावती सोबत ठेवा.",
                "प्राचार्यांची स्वाक्षरी, शिक्का व संस्थेचा कोड असलेले बोनाफाईड प्रमाणपत्र कार्यालयातून घ्या.",
                "हे प्रमाणपत्र डॉक्युमेंट व्हॉल्टमध्ये अपलोड करून पडताळणी करा.",
            ],
        },
        "fallback": {
            "en": [
                "A Bonafide Certificate (verified by your Institution Nodal Officer on NSP) cannot be replaced by fee receipts alone; contact your Institution Scholarship Nodal Officer immediately if delayed.",
            ],
            "hi": [
                "NSP सत्यापन में बोनाफाइड प्रमाण पत्र के स्थान पर केवल शुल्क रसीद पर्याप्त नहीं होती; देरी होने पर अपने कॉलेज के छात्रवृत्ति नोडल अधिकारी से संपर्क करें।",
            ],
            "mr": [
                "NSP पडताळणीमध्ये बोनाफाईड प्रमाणपत्राऐवजी केवळ शुल्क पावती पुरेशी ठरत नाही; विलंब झाल्यास महाविद्यालयाच्या शिष्यवृत्ती नोडल अधिकाऱ्यांशी संपर्क साधा.",
            ],
        },
    },
    "marksheet_7th": {
        "title": {"en": "Class VII Examination Marksheet", "hi": "कक्षा 7वीं की अंकतालिका", "mr": "इयत्ता ७वी गुणपत्रिका"},
        "why": {
            "en": "Confirms minimum qualifying marks in Class VII required to sit for the NMMS scholarship examination.",
            "hi": "NMMS छात्रवृत्ति परीक्षा में बैठने हेतु कक्षा 7 में न्यूनतम अंक योग्यता सिद्ध करने के लिए आवश्यक।",
            "mr": "NMMS शिष्यवृत्ती परीक्षेसाठी इयत्ता ७वी मधील किमान गुण पात्रता सिद्ध करण्यासाठी आवश्यक.",
        },
        "where": {"en": "Headmaster / Principal of your Government or Government-aided School.", "hi": "आपके सरकारी / सहायता प्राप्त विद्यालय के प्रधानाचार्य कार्यालय।", "mr": "तुमच्या शासकीय / अनुदानित शाळेचे मुख्याध्यापक कार्यालय."},
        "authority": {"en": "Headmaster / School Examination Authority", "hi": "विद्यालय प्रधानाचार्य / परीक्षा प्राधिकरण", "mr": "शाळा मुख्याध्यापक / परीक्षा विभाग"},
        "portals": [{"label": "National Scholarship Portal (NSP)", "url": "https://scholarships.gov.in"}],
        "fee_verified": None,
        "fee_estimated": None,
        "time_estimated": None,
        "unavailable": {
            "en": ["Whether a duplicate school-record fee applies and exact school office counter timing."],
            "hi": ["विद्यालय में डुप्लीकेट अंकतालिका शुल्क एवं कार्यालय समय की जानकारी।"],
            "mr": ["शाळेतील दुय्यम गुणपत्रिका शुल्क व कार्यालयीन वेळेची नेमकी माहिती."],
        },
        "steps": {
            "en": [
                "Visit your Class VII school office with student Aadhaar / enrolment number.",
                "Request an attested duplicate or certified marks summary signed by the Headmaster.",
                "Upload the signed marksheet to Document Vault.",
            ],
            "hi": [
                "अपना छात्र नामांकन/आधार विवरण लेकर विद्यालय प्रधानाचार्य से मिलें।",
                "प्रधानाचार्य द्वारा प्रमाणित कक्षा 7 अंकतालिका की प्रति प्राप्त कर डॉक्यूमेंट वॉल्ट में अपलोड करें।",
            ],
            "mr": [
                "विद्यार्थी नोंदणी क्रमांक / आधार घेऊन शाळेच्या मुख्याध्यापकांकडे अर्ज करा.",
                "मुख्याध्यापकांच्या स्वाक्षरीसह प्रमाणित ७वी गुणपत्रिका मिळवून डॉक्युमेंट व्हॉल्टमध्ये अपलोड करा.",
            ],
        },
        "fallback": {
            "en": ["Request an attested register extract signed by the School Headmaster / Block Education Officer if the original marksheet is lost."],
            "hi": ["मूल प्रति खो जाने पर प्रधानाचार्य या खंड शिक्षा अधिकारी से प्रमाणित परीक्षा पंजिका नकल प्राप्त करें।"],
            "mr": ["मूळ प्रत हरवल्यास मुख्याध्यापक किंवा गटशिक्षणाधिकाऱ्यांकडून प्रमाणित निकाल नोंदवही उतारा घ्या."],
        },
    },
    "delivery_certificate": {
        "title": {"en": "Institutional Delivery Discharge Slip", "hi": "संस्थागत प्रसव डिस्चार्ज पर्ची", "mr": "संस्थात्मक प्रसूती डिस्चार्ज कार्ड"},
        "why": {
            "en": "Verifies delivery at a government or accredited private health institution for Janani Suraksha Yojana (JSY) assistance.",
            "hi": "जननी सुरक्षा योजना (JSY) सहायता हेतु सरकारी या मान्यता प्राप्त अस्पताल में प्रसव प्रमाणित करने के लिए आवश्यक।",
            "mr": "जननी सुरक्षा योजनेच्या (JSY) लाभासाठी शासकीय किंवा मान्यताप्राप्त रुग्णालयात प्रसूती झाल्याचा पुरावा.",
        },
        "where": {"en": "Medical Records Section / Maternity Ward of the Government Hospital or Accredited PHC/CHC where delivery occurred.", "hi": "संबंधित सरकारी अस्पताल / पीएचसी के प्रसूति विभाग एवं मेडिकल रिकॉर्ड कार्यालय।", "mr": "प्रसूती झालेल्या शासकीय रुग्णालयाचा प्रसूती कक्ष / वैद्यकीय अभिलेख विभाग."},
        "authority": {"en": "Hospital Medical Superintendent / Medical Officer", "hi": "अस्पताल चिकित्सा अधीक्षक / चिकित्सा अधिकारी", "mr": "रुग्णालय वैद्यकीय अधीक्षक / वैद्यकीय अधिकारी"},
        "portals": [{"label": "National Health Mission (NHM)", "url": "https://nhm.gov.in"}],
        "fee_verified": {"en": "Original discharge slip issued free at public hospitals.", "hi": "सरकारी अस्पतालों में मूल डिस्चार्ज पर्ची निःशुल्क जारी की जाती है।", "mr": "शासकीय रुग्णालयांत मूळ डिस्चार्ज कार्ड मोफत दिले जाते."},
        "fee_estimated": None,
        "time_estimated": None,
        "unavailable": {
            "en": ["Hospital medical-records duplicate request turnaround time and exact ward counter address."],
            "hi": ["अस्पताल से डुप्लीकेट प्रति मिलने का सटीक समय और वार्ड का पता।"],
            "mr": ["रुग्णालयातून दुय्यम प्रत मिळण्याचा नेमका कालावधी व कक्षाचा पत्ता."],
        },
        "steps": {
            "en": [
                "Visit the hospital maternity/records counter with mother's Aadhaar, admission date, and MCP Card.",
                "Obtain a stamped discharge summary signed by the Medical Officer and upload it to Document Vault.",
            ],
            "hi": [
                "माता का आधार, भर्ती तिथि व MCP कार्ड लेकर अस्पताल के रिकॉर्ड काउंटर पर जाएं।",
                "चिकित्सा अधिकारी द्वारा प्रमाणित डिस्चार्ज पर्ची लेकर डॉक्यूमेंट वॉल्ट में अपलोड करें।",
            ],
            "mr": [
                "मातेचे आधार कार्ड, दाखल दिनांक व MCP कार्ड घेऊन रुग्णालयाच्या अभिलेख विभागात जा.",
                "वैद्यकीय अधिकाऱ्यांची स्वाक्षरी व शिक्का असलेली डिस्चार्ज प्रत घेऊन डॉक्युमेंट व्हॉल्टमध्ये अपलोड करा.",
            ],
        },
        "fallback": {
            "en": ["Ask your ASHA / ANM worker to help retrieve the hospital RCH delivery register extract if the original slip was lost."],
            "hi": ["पर्ची खो जाने पर आशा/एएनएम कार्यकर्ता के माध्यम से अस्पताल के RCH प्रसव रजिस्टर की प्रमाणित प्रति निकलवाएं।"],
            "mr": ["कार्ड हरवले असल्यास आशा/ANM सेविकेच्या मदतीने रुग्णालयाच्या RCH प्रसूती नोंदवहीतील प्रमाणित उतारा मिळवा."],
        },
    },
    "sowing_certificate": {
        "title": {"en": "Crop Sowing Certificate / Self-Declaration", "hi": "बुवाई प्रमाण पत्र / स्व-घोषणा", "mr": "पीक पेरणी प्रमाणपत्र / स्वयंघोषणापत्र"},
        "why": {
            "en": "Confirms actual seasonal crop sown on the insured agricultural plot under PMFBY guidelines.",
            "hi": "PMFBY फसल बीमा के अंतर्गत बीमित खेत में बोई गई फसल की पुष्टि हेतु आवश्यक।",
            "mr": "PMFBY पीक विमा योजनेअंतर्गत विमा उतरवलेल्या क्षेत्रावर प्रत्यक्ष घेतलेल्या पिकाची खात्री करण्यासाठी आवश्यक.",
        },
        "where": {"en": "Local Patwari / Talathi / Village Agriculture Officer, CSC, or Self-Declaration format on PMFBY portal.", "hi": "स्थानीय पटवारी/तलाठी/कृषि सहायक, सीएससी या PMFBY पोर्टल का स्व-घोषणा प्रारूप।", "mr": "स्थानिक तलाठी / कृषी सहायक, सीएससी किंवा PMFBY पोर्टलवरील स्वयंघोषणा नमुना."},
        "authority": {"en": "State Revenue / Agriculture Officer (Patwari / Talathi) or Farmer Self-Declaration", "hi": "राजस्व / कृषि अधिकारी अथवा किसान स्व-घोषणा", "mr": "महसूल / कृषी अधिकारी किंवा शेतकरी स्वयंघोषणा"},
        "portals": [{"label": "PMFBY Official Portal", "url": "https://pmfby.gov.in"}],
        "fee_verified": {"en": "Self-declaration format and crop survey entry carry no government fee.", "hi": "स्व-घोषणा पत्र एवं ई-फसल सर्वेक्षण हेतु कोई सरकारी शुल्क नहीं है।", "mr": "स्वयंघोषणापत्र आणि ई-पीक पाहणी नोंदीसाठी कोणतेही शासकीय शुल्क नाही."},
        "fee_estimated": None,
        "time_estimated": None,
        "unavailable": {
            "en": ["Exact CSC scanning fee (if assisted by private VLE) and local Talathi visit schedule."],
            "hi": ["सीएससी ऑपरेटर का स्थानीय सेवा शुल्क और पटवारी के गांव दौरे का समय।"],
            "mr": ["सीएससी केंद्राचे स्थानिक शुल्क व तलाठी भेटीचे वेळापत्रक."],
        },
        "steps": {
            "en": [
                "Complete your state digital crop survey (e.g., e-Pik Pahani / Digital Girdawari) or fill out the PMFBY Sowing Certificate self-declaration.",
                "Get Talathi/Patwari/Agriculture Assistant verification if required in your state and upload to Document Vault.",
            ],
            "hi": [
                "अपने राज्य का ई-खसरा/डिजिटल फसल सर्वेक्षण दर्ज करें या PMFBY बुवाई स्व-घोषणा भरें।",
                "नियमानुसार पटवारी/तलाठी हस्ताक्षर कराकर डॉक्यूमेंट वॉल्ट में अपलोड करें।",
            ],
            "mr": [
                "ई-पीक पाहणी नोंद पूर्ण करा किंवा PMFBY पीक पेरणी स्वयंघोषणापत्र भरा.",
                "आवश्यकतेनुसार तलाठी/कृषी सहायकांची स्वाक्षरी घेऊन डॉक्युमेंट व्हॉल्टमध्ये अपलोड करा.",
            ],
        },
        "fallback": {
            "en": ["If your local Talathi crop entry (Pik Pahani) is delayed near the PMFBY cut-off date, PMFBY guidelines allow submitting a signed Farmer Sowing Self-Declaration via CSC/Bank until revenue Girdawari updates."],
            "hi": ["यदि अंतिम तिथि तक पटवारी खसरा अद्यतन न हो सके, तो PMFBY दिशानिर्देशों के तहत बैंक/सीएससी में हस्ताक्षरित स्व-घोषणा पत्र जमा किया जा सकता है।"],
            "mr": ["अंतिम मुदतीपूर्वी तलाठी पीक पाहणी अद्ययावत नसल्यास बँक किंवा सीएससीकडे शेतकऱ्याचे स्वाक्षरीकृत स्वयंघोषणापत्र सादर करता येते."],
        },
    },
    "trade_declaration": {
        "title": {"en": "Traditional Artisan / Trade Self-Declaration", "hi": "पारंपरिक कारीगर / व्यवसाय स्व-घोषणा", "mr": "पारंपरिक कारागीर / व्यवसाय स्वयंघोषणा"},
        "why": {
            "en": "Confirms active family-based traditional craft engagement across eligible PM Vishwakarma trades.",
            "hi": "पीएम विश्वकर्मा के अंतर्गत चिह्नित पारंपरिक हस्तशिल्प/कारीगरी व्यवसाय में संलग्नता प्रमाणित करने हेतु आवश्यक।",
            "mr": "पीएम विश्वकर्मा योजनेतील पारंपरिक कारागिरी व्यवसायात कार्यरत असल्याची खात्री करण्यासाठी आवश्यक.",
        },
        "where": {"en": "Authorized CSC / PM Vishwakarma portal with Gram Panchayat / ULB stage-1 verification.", "hi": "अधिकृत सीएससी / पीएम विश्वकर्मा पोर्टल एवं ग्राम पंचायत/निकाय स्तर सत्यापन।", "mr": "अधिकृत सीएससी / पीएम विश्वकर्मा पोर्टल आणि ग्रामपंचायत/मनपा स्तर तपासणी."},
        "authority": {"en": "Applicant Self-Declaration verified by Gram Panchayat / Urban Local Body", "hi": "ग्राम पंचायत / शहरी स्थानीय निकाय द्वारा सत्यापित आवेदक स्व-घोषणा", "mr": "ग्रामपंचायत / नागरी संस्थेद्वारे तपासलेले स्वयंघोषणापत्र"},
        "portals": [{"label": "PM Vishwakarma Official Portal", "url": "https://pmvishwakarma.gov.in"}],
        "fee_verified": {"en": "Registration and trade self-declaration on PM Vishwakarma via CSC is free for beneficiaries.", "hi": "पीएम विश्वकर्मा पंजीकरण एवं स्व-घोषणा लाभार्थियों के लिए निःशुल्क है।", "mr": "पीएम विश्वकर्मा नोंदणी व स्वयंघोषणा लाभार्थ्यांसाठी मोफत आहे."},
        "fee_estimated": None,
        "time_estimated": None,
        "unavailable": {
            "en": ["Exact Gram Panchayat / District Implementation Committee meeting turnaround time."],
            "hi": ["ग्राम पंचायत / जिला समिति अनुमोदन में लगने वाला सटीक समय।"],
            "mr": ["ग्रामपंचायत / जिल्हा समितीच्या मंजुरीसाठी लागणारा नेमका कालावधी."],
        },
        "steps": {
            "en": [
                "Visit a CSC with Aadhaar, mobile number, and Bank Passbook to submit biometric registration on https://pmvishwakarma.gov.in.",
                "Sign the trade self-declaration and complete Gram Panchayat/ULB verification, then upload acknowledgement to Document Vault.",
            ],
            "hi": [
                "आधार व बैंक पासबुक लेकर सीएससी केंद्र पर https://pmvishwakarma.gov.in पंजीकरण व व्यवसाय स्व-घोषणा पूरा करें।",
                "ग्राम पंचायत/शहरी निकाय सत्यापन कराएं और पावती डॉक्यूमेंट वॉल्ट में अपलोड करें।",
            ],
            "mr": [
                "आधार व बँक पासबुक घेऊन सीएससीवर https://pmvishwakarma.gov.in नोंदणी व व्यवसाय स्वयंघोषणा पूर्ण करा.",
                "ग्रामपंचायत/नागरी संस्थेची पडताळणी पूर्ण करून पावती डॉक्युमेंट व्हॉल्टमध्ये अपलोड करा.",
            ],
        },
        "fallback": {
            "en": ["No third-party trade certificate is needed upfront — your self-declaration plus local Gram Panchayat / ULB verification serves as official trade proof under PM Vishwakarma."],
            "hi": ["पहले से किसी बाहरी लाइसेंस की आवश्यकता नहीं है — आपकी स्व-घोषणा और ग्राम पंचायत सत्यापन ही मुख्य प्रमाण है।"],
            "mr": ["आधीपासून वेगळ्या परवान्याची गरज नाही — तुमचे स्वयंघोषणापत्र व ग्रामपंचायत पडताळणी हाच अधिकृत पुरावा मानला जातो."],
        },
    },
    "shg_passbook": {
        "title": {"en": "SHG Membership Passbook / Resolution Copy", "hi": "स्वयं सहायता समूह (SHG) सदस्यता पासबुक / प्रस्ताव प्रति", "mr": "बचत गट (SHG) सदस्यत्व पासबुक / ठराव प्रत"},
        "why": {
            "en": "Establishes active membership in a State Rural Livelihood Mission (SRLM) registered Self-Help Group.",
            "hi": "DAY-NRLM के तहत पंजीकृत महिला स्वयं सहायता समूह में सक्रिय सदस्यता सिद्ध करने हेतु आवश्यक।",
            "mr": "DAY-NRLM अंतर्गत नोंदणीकृत महिला बचत गटातील सक्रिय सदस्यत्व सिद्ध करण्यासाठी आवश्यक.",
        },
        "where": {"en": "Your Self-Help Group President/Secretary, Village Organization (VO), or Block SRLM / Mission Coordinator.", "hi": "आपके समूह की अध्यक्ष/सचिव, ग्राम संगठन (VO) या ब्लॉक आजीविका मिशन कार्यालय।", "mr": "तुमच्या बचत गटाच्या अध्यक्ष/सचिव, ग्रामसंघ किंवा पंचायत समिती उमेद/SRLM कक्ष."},
        "authority": {"en": "Self-Help Group / Village Organization / State Rural Livelihoods Mission", "hi": "स्वयं सहायता समूह / ग्राम संगठन / राज्य ग्रामीण आजीविका मिशन", "mr": "बचत गट / ग्रामसंघ / राज्य ग्रामीण जीवनोन्नती अभियान"},
        "portals": [{"label": "Ministry of Rural Development / DAY-NRLM", "url": "https://rural.nic.in"}],
        "fee_verified": None,
        "fee_estimated": None,
        "time_estimated": None,
        "unavailable": {
            "en": ["Local Block SRLM office address, meeting schedule, and exact turnaround days."],
            "hi": ["ब्लॉक आजीविका मिशन कार्यालय का सटीक पता व समय।"],
            "mr": ["तालुका अभियान कार्यालयाचा नेमका पत्ता व बैठकीचा कालावधी."],
        },
        "steps": {
            "en": [
                "Ask your SHG President/Bookkeeper for your group savings passbook or a signed SHG Resolution Copy with LokOS/NRLM code.",
                "If not yet in an SHG, contact your Village Organization (VO) / Block Mission Manager to join or form a 10-member SHG, then upload proof to Document Vault.",
            ],
            "hi": [
                "अपने समूह अध्यक्ष/सचिव से समूह बचत पासबुक अथवा हस्ताक्षरित प्रस्ताव प्रति लें।",
                "समूह में न होने पर ब्लॉक आजीविका मिशन/ग्राम संगठन से जुड़कर प्रमाण पत्र डॉक्यूमेंट वॉल्ट में अपलोड करें।",
            ],
            "mr": [
                "बचत गटाच्या अध्यक्ष/सचिवांकडून गटाचे पासबुक किंवा स्वाक्षरीकृत ठराव प्रत घ्या.",
                "गटात नसल्यास ग्रामसंघ/तालुका अभियानाशी संपर्क साधून नोंदणी करा व पुरावा डॉक्युमेंट व्हॉल्टमध्ये अपलोड करा.",
            ],
        },
        "fallback": {
            "en": ["If your personal SHG booklet is misplaced, ask the Village Organization / Block Mission Coordinator for a signed NRLM/LokOS portal membership extract."],
            "hi": ["पासबुक खो जाने पर ग्राम संगठन या ब्लॉक समन्वयक से LokOS/NRLM पोर्टल सदस्यता विवरण प्राप्त करें।"],
            "mr": ["पासबुक हरवले असल्यास ग्रामसंघ किंवा तालुका समन्वयकाकडून LokOS/NRLM पोर्टलवरील सदस्यत्वाचा उतारा घ्या."],
        },
    },
    "fisheries_license": {
        "title": {"en": "Fisheries Identity / Vessel Registration / Land Document", "hi": "मत्स्य पहचान पत्र / नौका पंजीकरण / भूमि दस्तावेज़", "mr": "मत्स्य व्यवसाय ओळखपत्र / नौका नोंदणी / जागा कागदपत्र"},
        "why": {
            "en": "Establishes active fisher / fish-farmer identity or pond/vessel entitlement under PMMSY.",
            "hi": "प्रधानमंत्री मत्स्य संपदा योजना (PMMSY) हेतु सक्रिय मत्स्यपालक/मछुआरा पहचान व कार्यस्थल प्रमाणित करने के लिए आवश्यक।",
            "mr": "प्रधानमंत्री मत्स्य संपदा योजनेसाठी (PMMSY) सक्रिय मच्छीमार ओळख किंवा तलाव/नौका हक्क सिद्ध करण्यासाठी आवश्यक.",
        },
        "where": {"en": "District Fisheries Development Office or National Fisheries Digital Platform (NFDP) / CSC.", "hi": "जिला मत्स्य विकास कार्यालय या राष्ट्रीय मत्स्य डिजिटल प्लेटफॉर्म (NFDP) / सीएससी।", "mr": "जिल्हा मत्स्यव्यवसाय विकास कार्यालय किंवा राष्ट्रीय मत्स्य डिजिटल प्लॅटफॉर्म / सीएससी."},
        "authority": {"en": "State Fisheries Department / Department of Fisheries, Government of India", "hi": "राज्य मत्स्य विभाग / मत्स्यपालन विभाग, भारत सरकार", "mr": "राज्य मत्स्यव्यवसाय विभाग / मत्स्यव्यवसाय विभाग, भारत सरकार"},
        "portals": [{"label": "Department of Fisheries", "url": "https://dof.gov.in"}],
        "fee_verified": None,
        "fee_estimated": None,
        "time_estimated": None,
        "unavailable": {
            "en": [
                "Exact state licensing/registration fee schedule.",
                "Exact local District Fisheries Officer address and processing days.",
            ],
            "hi": [
                "राज्य-वार लाइसेंस/पंजीकरण शुल्क और स्थानीय कार्यालय का सटीक पता व समय।",
            ],
            "mr": [
                "राज्यानुसार परवाना शुल्क, नेमका कालावधी व जिल्हा मत्स्य कार्यालयाचा पत्ता.",
            ],
        },
        "steps": {
            "en": [
                "Carry Aadhaar, Bank Passbook, boat/pond lease/ownership details, and Fishermen Cooperative membership (if applicable).",
                "Visit your District Fisheries Office or register via https://dof.gov.in / CSC to obtain Fisher ID or vessel registration.",
                "Upload the issued ID/registration certificate to Document Vault.",
            ],
            "hi": [
                "आधार, बैंक पासबुक एवं नाव/तालाब पट्टा विवरण लेकर जिला मत्स्य कार्यालय या सीएससी पर पंजीकरण कराएं।",
                "मत्स्य पहचान पत्र या पंजीकरण प्रमाण पत्र प्राप्त कर डॉक्यूमेंट वॉल्ट में अपलोड करें।",
            ],
            "mr": [
                "आधार, बँक पासबुक व नौका/तलाव करार तपशील घेऊन जिल्हा मत्स्य कार्यालयात किंवा सीएससीद्वारे नोंदणी करा.",
                "मिळालेले ओळखपत्र किंवा नोंदणी प्रमाणपत्र डॉक्युमेंट व्हॉल्टमध्ये अपलोड करा.",
            ],
        },
        "fallback": {
            "en": ["Either a Fisher ID Card, Registered Fishing Vessel Certificate, Cooperative Society Certificate, or Agricultural/Aquaculture Land Record/Lease meets PMMSY initial project criteria depending on the sub-component."],
            "hi": ["PMMSY के अंतर्गत मत्स्य पहचान पत्र, पंजीकृत नौका प्रमाण पत्र, सहकारी समिति प्रमाण या भूमि/तालाब पट्टा दस्तावेज़ घटकों के अनुसार विकल्प रूप में मान्य हैं।"],
            "mr": ["PMMSY अंतर्गत उपघटकानुसार मच्छीमार ओळखपत्र, नौका नोंदणी, सहकारी संस्था प्रमाणपत्र किंवा तलाव/जमीन करार पर्याय म्हणून चालतो."],
        },
    },
    "project_report": {
        "title": {"en": "Detailed Project Report (DPR) / Business Plan", "hi": "विस्तृत परियोजना रिपोर्ट (DPR) / व्यवसाय योजना", "mr": "सविस्तर प्रकल्प अहवाल (DPR) / व्यवसाय आराखडा"},
        "why": {
            "en": "Details capital expenditure, working capital, revenue projections, and viability required for bank credit sanction under PMEGP / Stand-Up India.",
            "hi": "PMEGP / स्टैंड-अप इंडिया के अंतर्गत बैंक ऋण एवं सब्सिडी मूल्यांकन हेतु लागत, कार्यशील पूंजी और आय विवरण प्रस्तुत करने के लिए आवश्यक।",
            "mr": "PMEGP / स्टँड-अप इंडिया योजनेअंतर्गत बँक कर्ज व अनुदान मंजुरीसाठी प्रकल्प खर्च आणि उत्पन्न तपशील सादर करण्यासाठी आवश्यक.",
        },
        "where": {"en": "Self-prepared using KVIC / Udyamimitra model DPR templates, District Industries Centre (DIC), MSME-DI, or Chartered Accountant.", "hi": "KVIC / उद्यमिमित्र मॉडल टेम्पलेट से स्वयं निर्मित, जिला उद्योग केंद्र (DIC), MSME-DI या चार्टर्ड अकाउंटेंट।", "mr": "KVIC / उद्यमीमित्र नमुना आराखड्याद्वारे स्वतः, जिल्हा उद्योग केंद्र (DIC) किंवा चार्टर्ड अकाउंटंट."},
        "authority": {"en": "Applicant / District Industries Centre (DIC) / MSME Development Institute / CA", "hi": "आवेदक / जिला उद्योग केंद्र / एमएसएमई संस्थान", "mr": "अर्जदार / जिल्हा उद्योग केंद्र / MSME संस्थान"},
        "portals": [
            {"label": "KVIC PMEGP e-Portal", "url": "https://kviconline.gov.in"},
            {"label": "Department of Financial Services", "url": "https://financialservices.gov.in"},
        ],
        "fee_verified": {"en": "Free model project profiles are available on KVIC PMEGP / Udyamimitra portals.", "hi": "KVIC PMEGP पोर्टल पर मॉडल प्रोजेक्ट प्रोफाइल निःशुल्क उपलब्ध हैं।", "mr": "KVIC PMEGP पोर्टलवर नमुना प्रकल्प अहवाल मोफत उपलब्ध आहेत."},
        "fee_estimated": None,
        "time_estimated": None,
        "unavailable": {
            "en": [
                "Private Chartered Accountant / consultant drafting fees (if you hire external preparation).",
                "Exact DIC / RSETI counseling center address.",
            ],
            "hi": [
                "निजी सलाहकार या चार्टर्ड अकाउंटेंट की फीस (यदि आप बाहर से बनवाते हैं) तथा स्थानीय DIC केंद्र का पता।",
            ],
            "mr": [
                "खाजगी सल्लागार/सीए शुल्क (बाहेरून करून घेतल्यास) व स्थानिक जिल्हा उद्योग केंद्राचा पत्ता.",
            ],
        },
        "steps": {
            "en": [
                "Download free model DPR templates for your industry directly from https://kviconline.gov.in (over 1,000 free sample profiles).",
                "Customize machinery quotations, working capital, and projected cash flow, or seek free handholding at your District Industries Centre (DIC) / RSETI.",
                "Upload the finalized DPR PDF to Document Vault.",
            ],
            "hi": [
                "https://kviconline.gov.in से अपने व्यवसाय हेतु निःशुल्क मॉडल प्रोजेक्ट प्रोफाइल डाउनलोड करें।",
                "मशीनरी कोटेशन और पूंजी विवरण भरें या जिला उद्योग केंद्र (DIC) से निःशुल्क मार्गदर्शन लें।",
                "तैयार DPR डॉक्यूमेंट वॉल्ट में अपलोड करें।",
            ],
            "mr": [
                "https://kviconline.gov.in वरून तुमच्या व्यवसायासाठी मोफत नमुना प्रकल्प अहवाल डाउनलोड करा.",
                "यंत्रसामग्री कोटेशन व भांडवली तपशील भरा किंवा जिल्हा उद्योग केंद्राचे (DIC) मोफत मार्गदर्शन घ्या.",
                "तयार DPR डॉक्युमेंट व्हॉल्टमध्ये अपलोड करा.",
            ],
        },
        "fallback": {
            "en": ["Use free KVIC/DIC sample project reports and Rural Self Employment Training Institutes (RSETI) handholding rather than paying high agent fees."],
            "hi": ["एजेंटों को भारी शुल्क देने के बजाय KVIC के निःशुल्क मॉडल DPR और जिला उद्योग केंद्र / RSETI की निःशुल्क सहायता का उपयोग करें।"],
            "mr": ["एजंटना मोठी फी देण्याऐवजी KVIC चे मोफत नमुना प्रकल्प अहवाल आणि DIC / RSETI केंद्रांची मोफत मदत घ्या."],
        },
    },
    "business_proof": {
        "title": {"en": "Proof of Business Address & Enterprise Registration", "hi": "व्यवसाय पता और उद्यम पंजीकरण प्रमाण", "mr": "व्यवसाय पत्ता आणि उद्योग नोंदणी पुरावा"},
        "why": {
            "en": "Confirms existence and location of micro/small non-farm enterprise for MUDRA loan appraisal.",
            "hi": "मुद्रा ऋण मूल्यांकन हेतु सूक्ष्म/लघु व्यवसाय के अस्तित्व और पते की पुष्टि करने के लिए आवश्यक।",
            "mr": "मुद्रा कर्ज मंजुरीसाठी सूक्ष्म/लघु व्यवसायाचे अस्तित्व व पत्ता सिद्ध करण्यासाठी आवश्यक.",
        },
        "where": {"en": "Udyam Registration Portal (MSME), Municipal Shop & Establishment Portal, or CSC.", "hi": "उद्यम पंजीकरण पोर्टल (MSME), नगर शॉप एक्ट लाइसेंस पोर्टल या सीएससी।", "mr": "उद्यम नोंदणी पोर्टल (MSME), शॉप अ‍ॅक्ट परवाना पोर्टल किंवा सीएससी."},
        "authority": {"en": "Ministry of MSME / Municipal Authority", "hi": "सूक्ष्म, लघु और मध्यम उद्यम मंत्रालय / नगर निकाय", "mr": "सूक्ष्म, लघु आणि मध्यम उद्योग मंत्रालय / स्थानिक स्वराज्य संस्था"},
        "portals": [{"label": "Udyam MSME Registration / DFS", "url": "https://financialservices.gov.in"}],
        "fee_verified": {"en": "Official MSME Udyam Registration is completely Free on government portals.", "hi": "आधिकारिक सरकारी पोर्टल पर MSME उद्यम पंजीकरण पूर्णतः निःशुल्क है।", "mr": "अधिकृत शासकीय पोर्टलवर MSME उद्यम नोंदणी पूर्णपणे मोफत आहे."},
        "fee_estimated": None,
        "time_estimated": None,
        "unavailable": {
            "en": ["State/municipal Shop & Establishment Act registration fee and local municipal ward address."],
            "hi": ["राज्य/नगर शॉप एक्ट लाइसेंस का स्थानीय शुल्क एवं कार्यालय पता।"],
            "mr": ["स्थानिक शॉप अ‍ॅक्ट परवाना शुल्क व मनपा कार्यालयाचा नेमका पत्ता."],
        },
        "steps": {
            "en": [
                "Use your Aadhaar & PAN to register free for an MSME Udyam Certificate or municipal Shop & Establishment registration.",
                "Gather rent agreement/utility bill of your shop/workshop and upload proofs to Document Vault.",
            ],
            "hi": [
                "आधार व पैन से निःशुल्क MSME उद्यम पंजीकरण अथवा शॉप एक्ट लाइसेंस प्राप्त करें।",
                "दुकान किरायानामा/बिजली बिल सहित प्रमाण डॉक्यूमेंट वॉल्ट में अपलोड करें।",
            ],
            "mr": [
                "आधार व पॅनद्वारे मोफत MSME उद्यम नोंदणी किंवा शॉप अ‍ॅक्ट परवाना काढा.",
                "दुकानाचा भाडेकरार/वीज बिल यासह पुरावा डॉक्युमेंट व्हॉल्टमध्ये अपलोड करा.",
            ],
        },
        "fallback": {
            "en": ["Acceptable alternatives under MUDRA guidelines include Udyam Registration Certificate, Shop & Establishment License, GST/Trade certificate, or local business rent agreement + equipment quotation."],
            "hi": ["मुद्रा योजना के अंतर्गत उद्यम पंजीकरण प्रमाण पत्र, शॉप एक्ट लाइसेंस, ट्रेड लाइसेंस या दुकान किरायानामा मान्य विकल्प हैं।"],
            "mr": ["मुद्रा योजनेअंतर्गत उद्यम नोंदणी प्रमाणपत्र, शॉप अ‍ॅक्ट परवाना, व्यापार परवाना किंवा दुकान भाडेकरार पर्याय म्हणून स्वीकारले जातात."],
        },
    },
    "education_certificate": {
        "title": {"en": "Educational Qualification Certificate / Marksheet", "hi": "शैक्षणिक योग्यता प्रमाण पत्र / अंकतालिका", "mr": "शैक्षणिक पात्रता प्रमाणपत्र / गुणपत्रिका"},
        "why": {
            "en": "Confirms minimum educational threshold (e.g., Class 8 pass for higher-ticket PMEGP manufacturing projects or technical PMKVY courses).",
            "hi": "बड़े PMEGP परियोजनाओं (कक्षा 8 उत्तीर्ण) या PMKVY तकनीकी पाठ्यक्रमों हेतु न्यूनतम शैक्षणिक योग्यता सिद्ध करने के लिए आवश्यक।",
            "mr": "मोठ्या PMEGP प्रकल्पांसाठी (८वी उत्तीर्ण) किंवा PMKVY तांत्रिक अभ्यासक्रमांसाठी किमान शैक्षणिक पात्रता सिद्ध करण्यासाठी आवश्यक.",
        },
        "where": {"en": "Your last attended School / Board Office or DigiLocker.", "hi": "आपके अंतिम विद्यालय / शिक्षा बोर्ड कार्यालय या डिजिलॉकर।", "mr": "तुमची मागील शाळा / शिक्षण मंडळ कार्यालय किंवा डिजीलॉकर."},
        "authority": {"en": "Recognized School / Educational Board", "hi": "मान्यता प्राप्त विद्यालय / शिक्षा बोर्ड", "mr": "मान्यताप्राप्त शाळा / शिक्षण मंडळ"},
        "portals": [
            {"label": "DigiLocker Portal", "url": "https://digilocker.gov.in"},
            {"label": "MSDE PMKVY Information", "url": "https://www.msde.gov.in"},
        ],
        "fee_verified": {"en": "Fetching existing marksheets/leaving records on DigiLocker is free.", "hi": "डिजिलॉकर पर उपलब्ध शैक्षणिक प्रमाण पत्र प्राप्त करना निःशुल्क है।", "mr": "डिजीलॉकरवर उपलब्ध शैक्षणिक कागदपत्रे मिळवणे मोफत आहे."},
        "fee_estimated": None,
        "time_estimated": None,
        "unavailable": {
            "en": ["Duplicate physical school-leaving / board marksheet fees and school processing timelines."],
            "hi": ["डुप्लीकेट स्कूल टीसी/अंकतालिका निकलवाने का स्थानीय शुल्क और समय।"],
            "mr": ["शाळेतून दुय्यम दाखला/गुणपत्रिका मिळण्याचे नेमके शुल्क व कालावधी."],
        },
        "steps": {
            "en": [
                "Check https://digilocker.gov.in first for board certificates or visit your last school with Aadhaar to get an attested School Leaving / Transfer Certificate.",
                "Upload the certificate to Document Vault for review & verification.",
            ],
            "hi": [
                "पहले https://digilocker.gov.in जांचें या अपने अंतिम विद्यालय से प्रमाणित टीसी/अंकतालिका प्राप्त करें।",
                "दस्तावेज़ को डॉक्यूमेंट वॉल्ट में अपलोड व सत्यापित करें।",
            ],
            "mr": [
                "प्रथम https://digilocker.gov.in तपासा किंवा तुमच्या मागील शाळेतून प्रमाणित दाखला/गुणपत्रिका मिळवा.",
                "हे प्रमाणपत्र डॉक्युमेंट व्हॉल्टमध्ये अपलोड व पडताळणी करा.",
            ],
        },
        "fallback": {
            "en": [
                "Under PMKVY Recognition of Prior Learning (RPL), a self-declaration of basic literacy/skill experience can substitute formal certificates for eligible informal-sector workers.",
                "Under PMEGP, educational qualification (8th pass) is mandatory only for manufacturing projects above ₹10 lakh or service projects above ₹5 lakh.",
            ],
            "hi": [
                "PMKVY (RPL) के अंतर्गत पूर्व कार्य अनुभव वाले कामगारों के लिए बुनियादी साक्षरता स्व-घोषणा मान्य है।",
                "PMEGP में कक्षा 8 उत्तीर्ण प्रमाण पत्र केवल ₹10 लाख (विनिर्माण) या ₹5 लाख (सेवा) से अधिक की परियोजनाओं के लिए अनिवार्य है।",
            ],
            "mr": [
                "PMKVY (RPL) अंतर्गत अनुभवी कामगारांसाठी साक्षरतेचे स्वयंघोषणापत्र पर्याय म्हणून स्वीकारले जाते.",
                "PMEGP मध्ये ८वी उत्तीर्ण प्रमाणपत्र फक्त ₹१० लाख (उत्पादन) किंवा ₹५ लाख (सेवा) पेक्षा मोठ्या प्रकल्पांसाठी अनिवार्य आहे.",
            ],
        },
    },
    "passport_photo": {
        "title": {"en": "Passport Size Photographs", "hi": "पासपोर्ट आकार के फ़ोटो", "mr": "पासपोर्ट आकाराचे छायाचित्र"},
        "why": {
            "en": "Required for applicant identity verification on physical/digital KYC forms (KCC / PMJDY).",
            "hi": "KCC / PMJDY आवेदन केवाईसी पहचान सत्यापन हेतु आवश्यक।",
            "mr": "KCC / PMJDY अर्जावरील KYC ओळख पडताळणीसाठी आवश्यक.",
        },
        "where": {"en": "Any local photo studio or recent clear digital self-portrait meeting standard passport dimensions.", "hi": "कोई भी स्थानीय फोटो स्टूडियो या स्पष्ट डिजिटल फोटो।", "mr": "कोणताही स्थानिक फोटो स्टुडिओ किंवा स्पष्ट डिजिटल फोटो."},
        "authority": {"en": "Applicant-supplied recent photograph", "hi": "आवेदक द्वारा प्रदत्त हाल का फ़ोटो", "mr": "अर्जदाराने दिलेले अलीकडील छायाचित्र"},
        "portals": [],
        "fee_verified": None,
        "fee_estimated": None,
        "time_estimated": None,
        "unavailable": {
            "en": ["Local photo studio printing price (not fixed by government)."],
            "hi": ["स्थानीय फोटो स्टूडियो का निजी प्रिंटिंग मूल्य।"],
            "mr": ["स्थानिक फोटो स्टुडिओचे खाजगी छपाई दर."],
        },
        "steps": {
            "en": [
                "Capture a clear front-facing photo against a light background (no sunglasses/cap).",
                "Upload a clean JPG/PNG photo directly in Document Vault.",
            ],
            "hi": [
                "हल्की पृष्ठभूमि में स्पष्ट सामने का पासपोर्ट फोटो तैयार करें।",
                "साफ JPG/PNG फोटो डॉक्यूमेंट वॉल्ट में अपलोड करें।",
            ],
            "mr": [
                "फिकट पार्श्वभूमीवर स्पष्ट पासपोर्ट आकाराचे छायाचित्र तयार करा.",
                "सुस्पष्ट JPG/PNG फोटो डॉक्युमेंट व्हॉल्टमध्ये अपलोड करा.",
            ],
        },
        "fallback": {
            "en": ["Many bank/CSC branches capture a live webcam KYC photograph if you do not carry physical prints."],
            "hi": ["भौतिक फोटो न होने पर कई बैंक/सीएससी केंद्र लाइव वेबकैम केवाईसी फोटो भी ले सकते हैं।"],
            "mr": ["छापील फोटो नसल्यास अनेक बँक/सीएससी केंद्रे थेट वेबकॅमद्वारे KYC फोटो घेऊ शकतात."],
        },
    },
}

# Alias canonical pointers inside extended registry
EXTENDED_DOC_GUIDANCE["aadhaar"] = EXTENDED_DOC_GUIDANCE["aadhaar_card"]
EXTENDED_DOC_GUIDANCE["aadhaar_guardian"] = EXTENDED_DOC_GUIDANCE["aadhaar_card"]
EXTENDED_DOC_GUIDANCE["pan_guardian"] = EXTENDED_DOC_GUIDANCE["pan_card"]
EXTENDED_DOC_GUIDANCE["bank_account"] = EXTENDED_DOC_GUIDANCE["bank_passbook"]
EXTENDED_DOC_GUIDANCE["bank_statement"] = EXTENDED_DOC_GUIDANCE["bank_passbook"]
EXTENDED_DOC_GUIDANCE["marksheet_12"] = EXTENDED_DOC_GUIDANCE["marksheet_12th"]
EXTENDED_DOC_GUIDANCE["marksheet_7"] = EXTENDED_DOC_GUIDANCE["marksheet_7th"]
EXTENDED_DOC_GUIDANCE["educational_certificate"] = EXTENDED_DOC_GUIDANCE["education_certificate"]


# Ordered cue matcher: keeps "land possession" distinct from "land records" when no scheme forces otherwise
DOC_PHRASE_CUES: List[Tuple[str, Tuple[str, ...]]] = [
    ("land_possession", ("land possession", "possession certificate", "homestead land", "allotment certificate", "आवासीय भूमि", "ताबा प्रमाणपत्र", "कब्ज़ा प्रमाण")),
    ("land_records", ("land record", "land records", "land ownership", "7/12", "khatauni", "khasra", "patta", "ror", "उतारा", "जमीन मालकी", "भूमि स्वामित्व")),
    ("death_certificate", ("death certificate", "husband's death", "मृत्यू प्रमाणपत्र", "मृत्यु प्रमाण")),
    ("income_certificate", ("income certificate", "aay praman", "utpann", "उत्पन्न प्रमाणपत्र", "आय प्रमाण")),
    ("aadhaar_guardian", ("aadhaar card of parent", "guardian aadhaar", "parent aadhaar")),
    ("aadhaar_card", ("aadhaar", "aadhar", "uidai", "आधार")),
    ("bank_passbook", ("bank passbook", "passbook", "cancelled cheque", "bank statement", "bank account", "पासबुक", "बँक", "बैंक खाता")),
    ("vending_certificate", ("vending", "certificate of vending", "letter of recommendation", "lor", "फेरीवाला", "वेंडिंग")),
    ("mcp_card", ("mcp card", "mother and child", "pregnancy card", "माता बाल", "मातृ एवं बाल")),
    ("marksheet_12th", ("12th marksheet", "class 12", "class xii", "12th passing", "१२वी गुणपत्रिका", "12वीं")),
    ("marksheet_7th", ("7th marksheet", "class 7", "class vii", "७वी गुणपत्रिका", "7वीं")),
    ("caste_certificate", ("caste certificate", "jati praman", "जाति प्रमाण", "जातीचे प्रमाणपत्र")),
    ("domicile_certificate", ("domicile", "residence certificate", "niwas", "अधिवास", "रहिवासी")),
    ("ration_card", ("ration card", "bpl", "antyodaya", "राशन कार्ड", "रेशन कार्ड")),
    ("job_card", ("job card", "mgnrega", "मनरेगा", "जॉब कार्ड")),
    ("pan_guardian", ("pan card of parent", "guardian pan")),
    ("pan_card", ("pan card", "e-pan", "पैन", "पॅन")),
    ("birth_certificate", ("birth certificate", "जन्म प्रमाणपत्र", "जन्म प्रमाण")),
    ("bonafide_certificate", ("bonafide", "बोनाफाईड", "बोनाफाइड")),
    ("delivery_certificate", ("delivery", "discharge slip", "प्रसव", "प्रसूती")),
    ("shg_passbook", ("shg", "self help group", "बचत गट", "स्वयं सहायता समूह")),
    ("sowing_certificate", ("sowing", "पेरणी", "बुवाई")),
    ("trade_declaration", ("trade self", "trade declaration", "artisan declaration", "कारीगर", "कारागीर")),
    ("fisheries_license", ("fisheries", "vessel registration", "मत्स्य")),
    ("project_report", ("project report", "dpr", "business plan", "प्रकल्प अहवाल", "परियोजना रिपोर्ट")),
    ("business_proof", ("business proof", "udyam", "shop and establishment", "व्यवसाय")),
    ("education_certificate", ("education certificate", "educational qualification", "शैक्षणिक")),
    ("passport_photo", ("passport photo", "passport size", "photograph", "छायाचित्र", "फोटो")),
]


def identify_document_key(raw_query: str) -> Optional[str]:
    """Identifies a canonical document key from a free-text query without defaulting unknown docs."""
    text = (raw_query or "").strip()
    if not text:
        return None
    lower = text.lower()
    norm = re.sub(r"[\s\-/]+", "_", lower).strip("_")

    if norm in EXTENDED_DOC_GUIDANCE:
        return norm
    if norm in DOCUMENT_SOURCING_REGISTRY:
        return norm

    for doc_key, cues in DOC_PHRASE_CUES:
        if any(cue in lower for cue in cues):
            return doc_key

    return None


def find_schemes_requiring_document(
    *,
    doc_key: str,
    all_schemes: Optional[List[Scheme]] = None,
    db: Optional[Session] = None,
    lang: str = "en",
) -> List[Dict[str, Any]]:
    """
    Finds active schemes in DB / seed catalog that require `doc_key` (or an equivalent family key).
    Prioritizes exact document_type match first, then equivalence-group match.
    """
    exact_matches: List[Dict[str, Any]] = []
    equiv_matches: List[Dict[str, Any]] = []
    seen_codes: set[str] = set()

    scheme_candidates: List[Tuple[str, str, Optional[str], List[Dict[str, Any]]]] = []
    if all_schemes:
        for s in all_schemes:
            raw_docs = []
            for d in getattr(s, "documents", None) or []:
                raw_docs.append({
                    "document_type": d.document_type,
                    "title": d.title,
                    "is_mandatory": d.is_mandatory,
                    "alternatives": getattr(d, "alternatives", None) or [],
                    "issuing_authority": getattr(d, "issuing_authority", None),
                    "guidance": getattr(d, "guidance", None),
                    "source_url": getattr(d, "source_url", None),
                })
            if not raw_docs:
                raw_docs = get_authoritative_scheme_documents(s.scheme_code, getattr(s, "id", None), db)
            scheme_candidates.append((s.scheme_code, s.name, s.official_url or s.source_url, raw_docs))
    else:
        # Check seeded JSON schemes via readiness_service helper for core codes
        for code in ("PMAY-G", "PM-KISAN", "KCC", "PMFBY", "PM-KMY", "NSMSNY-MH", "MLBY-MH", "NSP-CSSS", "PM-SVANIDHI", "PMMVY", "AB-PMJAY", "MGNREGA", "PMMY", "PMEGP", "SSY", "DAY-NRLM", "JSY"):
            raw_docs = get_authoritative_scheme_documents(code, None, db)
            meta = get_localized_scheme_metadata(code, lang) or {}
            scheme_candidates.append((code, meta.get("name") or code, None, raw_docs))

    for scode, sname, portal, raw_docs in scheme_candidates:
        if scode in seen_codes:
            continue
        for rd in raw_docs:
            rd_type = (rd.get("document_type") or "").lower()
            meta = get_localized_scheme_metadata(scode, lang)
            loc_name = (meta.get("name") if meta else None) or sname
            entry = {
                "scheme_code": scode,
                "scheme_name": loc_name,
                "document_type": rd_type,
                "document_title": rd.get("title") or rd_type,
                "is_mandatory": bool(rd.get("is_mandatory", True)),
                "alternatives": list(rd.get("alternatives") or []),
                "guidance": rd.get("guidance"),
                "issuing_authority": rd.get("issuing_authority"),
                "source_url": rd.get("source_url") or portal,
            }
            if rd_type == doc_key:
                exact_matches.append(entry)
                seen_codes.add(scode)
                break
            if doc_types_match(rd_type, doc_key) or doc_types_match(doc_key, rd_type):
                equiv_matches.append(entry)
                seen_codes.add(scode)
                break

    return (exact_matches + equiv_matches)[:6]


def build_missing_document_guidance(
    *,
    query_or_doc_key: str,
    scheme: Optional[Scheme] = None,
    checklist_items: Optional[List[Dict[str, Any]]] = None,
    profile: Optional[UserProfile] = None,
    user: Optional[User] = None,
    db: Optional[Session] = None,
    all_schemes: Optional[List[Scheme]] = None,
    lang: str = "en",
) -> Dict[str, Any]:
    """
    Constructs a complete, epistemically honest 10-element missing-document guidance payload
    grounded in active scheme rules, SchemeDocument metadata, and Citizen Document Vault state.
    """
    lang_code = lang if lang in ("en", "hi", "mr") else "en"
    items = checklist_items or []

    # 1. Resolve document against active scheme checklist first (handling scheme-specific mapping,
    #    e.g., 'land possession certificate' -> PM-KISAN's `land_records` OR PMAY-G's `land_possession`).
    matched_item: Optional[Dict[str, Any]] = None
    doc_key: Optional[str] = None
    if items:
        from app.agents.tool_registry import _resolve_doc_key_for_scheme
        matched_item = _resolve_doc_key_for_scheme(query_or_doc_key, items)
        if matched_item:
            doc_key = matched_item.get("document_type")

    if not doc_key and scheme is not None and not items:
        # Resolve directly from authoritative scheme docs
        auth_docs = get_authoritative_scheme_documents(scheme.scheme_code, getattr(scheme, "id", None), db)
        pseudo_items = [{"document_type": d["document_type"], "title": d.get("title") or d["document_type"], "is_mandatory": d.get("is_mandatory", True), "status": "missing"} for d in auth_docs]
        from app.agents.tool_registry import _resolve_doc_key_for_scheme
        matched_item = _resolve_doc_key_for_scheme(query_or_doc_key, pseudo_items)
        if matched_item:
            doc_key = matched_item.get("document_type")

    inferred_key = identify_document_key(query_or_doc_key)
    resolved_key = doc_key or inferred_key or query_or_doc_key.strip().lower().replace(" ", "_")
    spec = EXTENDED_DOC_GUIDANCE.get(resolved_key)
    base_sourcing = get_document_sourcing_info(resolved_key, lang=lang_code)
    known_document = bool(spec or (base_sourcing and not base_sourcing.get("info_unavailable")))

    # 2. Gather DB / JSON SchemeDocument context for the active scheme (or catalog matches)
    db_doc_meta: Optional[Dict[str, Any]] = None
    active_scheme_info: Optional[Dict[str, Any]] = None
    requiring_schemes: List[Dict[str, Any]] = []

    if scheme is not None:
        raw_docs = get_authoritative_scheme_documents(scheme.scheme_code, getattr(scheme, "id", None), db)
        for rd in raw_docs:
            rd_t = (rd.get("document_type") or "").lower()
            if rd_t == resolved_key or doc_types_match(rd_t, resolved_key) or doc_types_match(resolved_key, rd_t):
                db_doc_meta = rd
                break
        meta = get_localized_scheme_metadata(scheme.scheme_code, lang_code)
        scheme_title = (meta.get("name") if meta else None) or scheme.name
        is_mand = bool((matched_item or db_doc_meta or {}).get("is_mandatory", True))
        applicable, waiver_reason = _evaluate_doc_applicability(
            scheme_code=scheme.scheme_code,
            doc_type=resolved_key,
            is_mandatory=is_mand,
            profile=profile,
            form_data={},
            lang=lang_code,
        )
        active_scheme_info = {
            "scheme_code": scheme.scheme_code,
            "scheme_name": scheme_title,
            "is_mandatory": is_mand,
            "applicable": applicable,
            "waiver_reason": waiver_reason,
            "document_required_by_scheme": bool(matched_item or db_doc_meta),
            "official_portal": scheme.official_url or scheme.source_url,
            "scheme_document_title": (db_doc_meta or matched_item or {}).get("title"),
            "scheme_guidance": (db_doc_meta or {}).get("guidance"),
            "scheme_alternatives": list((db_doc_meta or {}).get("alternatives") or []),
            "scheme_source_url": (db_doc_meta or {}).get("source_url"),
        }
    elif known_document:
        requiring_schemes = find_schemes_requiring_document(
            doc_key=resolved_key,
            all_schemes=all_schemes,
            db=db,
            lang=lang_code,
        )

    # 3. Inspect real Document Vault state (read-only; NEVER assumes or promotes unverified uploads)
    vault_status = (matched_item or {}).get("status")
    vault_doc_id = (matched_item or {}).get("vault_document_id")
    if not vault_status:
        raw_vault = (
            (profile.profile_data or {}).get("documents", [])
            if profile and isinstance(getattr(profile, "profile_data", None), dict)
            else []
        )
        norm_vault = [normalize_vault_document(d) for d in raw_vault]
        rank = {"verified": 5, "reviewed": 4, "extracted": 3, "awaiting_citizen_review": 3, "uploaded": 2, "rejected": 1}
        matches = [
            d for d in norm_vault
            if doc_types_match(resolved_key, d.get("document_type", ""))
            or doc_types_match(d.get("document_type", ""), resolved_key)
        ]
        matches.sort(key=lambda d: rank.get(d.get("lifecycle_status", ""), 0), reverse=True)
        if matches:
            vault_status = matches[0].get("lifecycle_status", "awaiting_citizen_review")
            vault_doc_id = matches[0].get("id")
        else:
            vault_status = "missing"
    vault_status_label = get_localized_status_label(vault_status, lang_code)

    # 4. Build honest, unrecognized-document fallback if not in verified registry or DB
    if not known_document and not db_doc_meta:
        pretty_name = re.sub(r"[_-]+", " ", query_or_doc_key).strip().title() or _t(lang_code, "Requested Document", "वांछित दस्तावेज़", "संबंधित कागदपत्र")
        verified_info = [
            _t(lang_code, f"Document requested: {pretty_name}", f"अनुरोधित दस्तावेज़: {pretty_name}", f"विचारलेले कागदपत्र: {pretty_name}"),
            _t(lang_code, f"Document Vault status: {vault_status_label}", f"डॉक्यूमेंट वॉल्ट स्थिति: {vault_status_label}", f"डॉक्युमेंट व्हॉल्ट स्थिती: {vault_status_label}"),
        ]
        if active_scheme_info:
            verified_info.append(
                _t(
                    lang_code,
                    f"Active scheme in context: {active_scheme_info['scheme_name']} ({active_scheme_info['scheme_code']}) — this document is not listed in its verified checklist.",
                    f"सक्रिय योजना: {active_scheme_info['scheme_name']} ({active_scheme_info['scheme_code']}) — यह दस्तावेज़ इसकी सत्यापित सूची में दर्ज नहीं है।",
                    f"सक्रिय योजना: {active_scheme_info['scheme_name']} ({active_scheme_info['scheme_code']}) — हे कागदपत्र या योजनेच्या पडताळलेल्या यादीत नोंदलेले नाही.",
                )
            )
        unavailable_info = [
            _t(lang_code, "Issuing government authority and official portal URL are unavailable in our verified database.", "जारीकर्ता प्राधिकरण और आधिकारिक पोर्टल की जानकारी हमारे सत्यापित डेटाबेस में उपलब्ध नहीं है।", "जारी करणारे प्राधिकरण आणि अधिकृत पोर्टलची माहिती आमच्या पडताळलेल्या डेटाबेसमध्ये उपलब्ध नाही."),
            _t(lang_code, "Official fees, preparation process, and processing timelines are unavailable.", "आधिकारिक शुल्क, आवेदन प्रक्रिया और प्रसंस्करण समय उपलब्ध नहीं है।", "अधिकृत शुल्क, अर्ज प्रक्रिया आणि कालावधी उपलब्ध नाही."),
            _t(lang_code, "Exact local office address is unavailable.", "स्थानीय कार्यालय का सटीक पता उपलब्ध नहीं है।", "स्थानिक कार्यालयाचा नेमका पत्ता उपलब्ध नाही."),
        ]
        return {
            "found": True,
            "known_document": False,
            "document_type": resolved_key,
            "title": pretty_name,
            "active_scheme": active_scheme_info,
            "requiring_active_schemes": requiring_schemes,
            "why_required": _t(lang_code, "Information unavailable — this document is not present in our verified scheme guidelines.", "जानकारी उपलब्ध नहीं — यह दस्तावेज़ हमारे सत्यापित योजना दिशानिर्देशों में दर्ज नहीं है।", "माहिती उपलब्ध नाही — हे कागदपत्र आमच्या पडताळलेल्या योजना मार्गदर्शक तत्त्वांमध्ये नाही."),
            "where_to_obtain": None,
            "issuing_authority": None,
            "official_portals": [],
            "preparation_steps": [],
            "processing_time": {"value": None, "status": "unavailable"},
            "fees": {"value": None, "status": "unavailable"},
            "fallback_options": {
                "alternatives_from_scheme": [],
                "action_steps": [
                    _t(lang_code, "Check the active scheme's official portal or contact your nearest Common Service Center (CSC) / District Collectorate to confirm whether this document is required.", "यह दस्तावेज़ आवश्यक है या नहीं इसकी पुष्टि हेतु सक्रिय योजना के आधिकारिक पोर्टल या नजदीकी सीएससी (CSC) / जिला कार्यालय से संपर्क करें।", "हे कागदपत्र आवश्यक आहे का याची खात्री करण्यासाठी अधिकृत पोर्टल पहा किंवा जवळच्या सीएससी (CSC) / जिल्हा कार्यालयात चौकशी करा.")
                ],
            },
            "vault_status": vault_status,
            "vault_status_label": vault_status_label,
            "vault_document_id": vault_doc_id,
            "verified_info": verified_info,
            "estimated_info": [],
            "unavailable_info": unavailable_info,
        }

    # 5. Populate Verified / Estimated / Unavailable strictly for known or DB-backed documents
    title = (
        (spec["title"].get(lang_code) if spec else None)
        or (base_sourcing.get("title") if base_sourcing else None)
        or (db_doc_meta or {}).get("title")
        or resolved_key.replace("_", " ").title()
    )
    why_required = (
        (spec["why"].get(lang_code) if spec else None)
        or (base_sourcing.get("why_needed") if base_sourcing else None)
        or _t(lang_code, "Required under official scheme guidelines for eligibility verification.", "योजना के आधिकारिक दिशानिर्देशों के तहत पात्रता सत्यापन हेतु आवश्यक।", "योजनेच्या अधिकृत मार्गदर्शक तत्त्वांनुसार पात्रता तपासणीसाठी आवश्यक.")
    )
    authority = (
        (spec["authority"].get(lang_code) if spec else None)
        or (db_doc_meta or {}).get("issuing_authority")
        or (base_sourcing.get("issuing_authority") if base_sourcing else None)
    )
    where_to_obtain = (
        (spec["where"].get(lang_code) if spec else None)
        or (db_doc_meta or {}).get("guidance")
        or (base_sourcing.get("where_to_obtain") if base_sourcing else None)
    )

    portals: List[Dict[str, str]] = list(spec.get("portals", []) if spec else [])
    scheme_guideline_url = (db_doc_meta or {}).get("source_url")
    if scheme_guideline_url and all(p["url"] != scheme_guideline_url for p in portals):
        portals.insert(0, {
            "label": _t(lang_code, f"{scheme.scheme_code} Official Guidelines", f"{scheme.scheme_code} आधिकारिक दिशानिर्देश", f"{scheme.scheme_code} अधिकृत मार्गदर्शक तत्त्वे") if scheme else "Official Guidelines",
            "url": scheme_guideline_url,
        })
    elif not portals and base_sourcing and base_sourcing.get("official_url"):
        portals.append({"label": _t(lang_code, "Official Government Portal", "आधिकारिक सरकारी पोर्टल", "अधिकृत शासकीय पोर्टल"), "url": base_sourcing["official_url"]})

    # Fees classification
    fee_ver = (spec.get("fee_verified") or {}).get(lang_code) if spec else None
    fee_est = (spec.get("fee_estimated") or {}).get(lang_code) if spec else None
    if fee_ver:
        fees_obj = {"value": fee_ver, "estimated": fee_est, "status": "verified"}
    elif fee_est:
        fees_obj = {"value": fee_est, "estimated": fee_est, "status": "estimated"}
    else:
        fees_obj = {"value": None, "estimated": None, "status": "unavailable"}

    # Processing time classification
    time_ver = (spec.get("time_verified") or {}).get(lang_code) if spec else None
    time_est = (spec.get("time_estimated") or {}).get(lang_code) if spec else None
    if time_ver:
        time_obj = {"value": time_ver, "estimated": time_est, "status": "verified"}
    elif time_est:
        time_obj = {"value": time_est, "estimated": time_est, "status": "estimated"}
    else:
        time_obj = {"value": None, "estimated": None, "status": "unavailable"}

    steps = list((spec.get("steps") or {}).get(lang_code) or []) if spec else []
    fallback_actions = list((spec.get("fallback") or {}).get(lang_code) or []) if spec else []
    scheme_alts = list((db_doc_meta or {}).get("alternatives") or [])
    if not scheme_alts and requiring_schemes:
        for rs in requiring_schemes:
            for a in rs.get("alternatives") or []:
                if a not in scheme_alts:
                    scheme_alts.append(a)

    # Assemble clean epistemic buckets
    verified_info: List[str] = [
        _t(lang_code, f"Document Identified: {title} (`{resolved_key}`)", f"पहचाना गया दस्तावेज़: {title} (`{resolved_key}`)", f"ओळखलेले कागदपत्र: {title} (`{resolved_key}`)"),
    ]
    if active_scheme_info:
        mand_str = (
            _t(lang_code, "Mandatory", "अनिवार्य", "अनिवार्य")
            if active_scheme_info["is_mandatory"]
            else _t(lang_code, "Optional / Conditional", "वैकल्पिक / शर्त आधारित", "पर्यायी / अटींवर आधारित")
        )
        verified_info.append(
            _t(
                lang_code,
                f"Required By Active Scheme: {active_scheme_info['scheme_name']} ({active_scheme_info['scheme_code']}) — {mand_str}" + (f" [Listed in scheme as: {active_scheme_info['scheme_document_title']}]" if active_scheme_info.get("scheme_document_title") else ""),
                f"सक्रिय योजना द्वारा आवश्यक: {active_scheme_info['scheme_name']} ({active_scheme_info['scheme_code']}) — {mand_str}" + (f" [योजना सूची नाम: {active_scheme_info['scheme_document_title']}]" if active_scheme_info.get("scheme_document_title") else ""),
                f"सक्रिय योजनेसाठी आवश्यक: {active_scheme_info['scheme_name']} ({active_scheme_info['scheme_code']}) — {mand_str}" + (f" [योजनेतील नाव: {active_scheme_info['scheme_document_title']}]" if active_scheme_info.get("scheme_document_title") else ""),
            )
        )
        if active_scheme_info.get("waiver_reason"):
            verified_info.append(active_scheme_info["waiver_reason"])
    elif requiring_schemes:
        scheme_names = ", ".join(f"{r['scheme_name']} ({r['scheme_code']})" for r in requiring_schemes[:4])
        verified_info.append(
            _t(
                lang_code,
                f"Active Schemes Requiring This / Equivalent Document: {scheme_names}",
                f"इस दस्तावेज़ की आवश्यकता वाली सक्रिय योजनाएं: {scheme_names}",
                f"हे कागदपत्र लागणाऱ्या सक्रिय योजना: {scheme_names}",
            )
        )

    verified_info.append(_t(lang_code, f"Why Required: {why_required}", f"आवश्यक क्यों है: {why_required}", f"का आवश्यक आहे: {why_required}"))
    if authority:
        verified_info.append(_t(lang_code, f"Responsible Authority: {authority}", f"जिम्मेदार प्राधिकरण: {authority}", f"जबाबदार प्राधिकरण: {authority}"))
    if where_to_obtain:
        verified_info.append(_t(lang_code, f"Where to Obtain: {where_to_obtain}", f"कहाँ से प्राप्त करें: {where_to_obtain}", f"कुठून मिळवावे: {where_to_obtain}"))
    if fee_ver:
        verified_info.append(_t(lang_code, f"Statutory Fee: {fee_ver}", f"वैधानिक शुल्क: {fee_ver}", f"अधिकृत शुल्क: {fee_ver}"))
    if time_ver:
        verified_info.append(_t(lang_code, f"Statutory Processing SLA: {time_ver}", f"वैधानिक समय सीमा: {time_ver}", f"अधिकृत कालावधी: {time_ver}"))
    if scheme_alts:
        verified_info.append(
            _t(
                lang_code,
                f"Verified Accepted Alternatives in Scheme Guidelines: {', '.join(scheme_alts)}",
                f"योजना दिशानिर्देशों में मान्य विकल्प: {', '.join(scheme_alts)}",
                f"योजनेच्या नियमांतर्गत स्वीकारले जाणारे पर्याय: {', '.join(scheme_alts)}",
            )
        )
    verified_info.append(_t(lang_code, f"Your Document Vault Status: {vault_status_label}", f"आपके डॉक्यूमेंट वॉल्ट की स्थिति: {vault_status_label}", f"तुमची डॉक्युमेंट व्हॉल्ट स्थिती: {vault_status_label}"))

    estimated_info: List[str] = []
    if fee_est:
        estimated_info.append(_t(lang_code, f"Fee Estimate (State/CSC dependent): {fee_est}", f"अनुमानित शुल्क (राज्य/सीएससी अनुसार): {fee_est}", f"अंदाजे शुल्क (राज्य/सीएससीनुसार): {fee_est}"))
    if time_est:
        estimated_info.append(_t(lang_code, f"Estimated Processing Time: {time_est}", f"अनुमानित प्रसंस्करण समय: {time_est}", f"अंदाजे कालावधी: {time_est}"))

    unavailable_info: List[str] = list((spec.get("unavailable") or {}).get(lang_code) or []) if spec else []
    if fees_obj["status"] == "unavailable":
        unavailable_info.append(_t(lang_code, "Official application/issuance fee is unavailable in our verified database (varies by state/authority).", "आधिकारिक शुल्क हमारे सत्यापित डेटाबेस में उपलब्ध नहीं है (राज्य/प्राधिकरण के अनुसार भिन्न)।", "अधिकृत शुल्क आमच्या पडताळलेल्या डेटाबेसमध्ये उपलब्ध नाही (राज्य/प्राधिकरणानुसार बदलते)."))
    if time_obj["status"] == "unavailable":
        unavailable_info.append(_t(lang_code, "Verified processing duration is unavailable for this document.", "इस दस्तावेज़ की निश्चित प्रसंस्करण अवधि हमारे डेटाबेस में उपलब्ध नहीं है।", "या कागदपत्रासाठी निश्चित कालावधी आमच्या डेटाबेसमध्ये उपलब्ध नाही."))
    if not authority or not portals:
        unavailable_info.append(_t(lang_code, "Complete local portal/authority directory is unavailable for this entry.", "इस दस्तावेज़ का पूर्ण स्थानीय पोर्टल विवरण डेटाबेस में उपलब्ध नहीं है।", "या कागदपत्राचे संपूर्ण स्थानिक पोर्टल तपशील उपलब्ध नाहीत."))

    # Always note Document Vault requirement honestly
    vault_note = _t(
        lang_code,
        "Important: Uploading a file in Document Vault extracts text for your review (`awaiting_citizen_review`) and does NOT auto-verify it. Confirm your review in Document Vault so deterministic verification updates your readiness.",
        "महत्वपूर्ण: डॉक्यूमेंट वॉल्ट में फ़ाइल अपलोड करने पर वह स्वतः सत्यापित नहीं होती — पहले समीक्षा की पुष्टि करें ताकि सत्यापन के बाद आपकी तत्परता अद्यतन हो।",
        "महत्त्वाचे: डॉक्युमेंट व्हॉल्टमध्ये फाईल अपलोड केल्यावर ती आपोआप पडताळलेली होत नाही — तपासणीची पुष्टी करा म्हणजे पडताळणीनंतर तुमची अर्ज सज्जता अद्ययावत होईल.",
    )

    return {
        "found": True,
        "known_document": True,
        "document_type": resolved_key,
        "title": title,
        "active_scheme": active_scheme_info,
        "requiring_active_schemes": requiring_schemes,
        "why_required": why_required,
        "where_to_obtain": where_to_obtain,
        "issuing_authority": authority,
        "official_portals": portals,
        "preparation_steps": steps,
        "processing_time": time_obj,
        "fees": fees_obj,
        "fallback_options": {
            "alternatives_from_scheme": scheme_alts,
            "action_steps": fallback_actions,
        },
        "vault_status": vault_status,
        "vault_status_label": vault_status_label,
        "vault_document_id": vault_doc_id,
        "vault_upload_note": vault_note,
        "verified_info": verified_info,
        "estimated_info": estimated_info,
        "unavailable_info": unavailable_info,
        # Keep backward-compatible sourcing dict shape for UI/tests
        "sourcing": {
            "title": title,
            "why_needed": why_required,
            "where_to_obtain": where_to_obtain,
            "issuing_authority": authority,
            "official_url": portals[0]["url"] if portals else None,
            "verified_fee": fee_ver or fee_est or _t(lang_code, "Information unavailable", "जानकारी उपलब्ध नहीं", "माहिती उपलब्ध नाही"),
            "expected_processing_days": time_ver or time_est or _t(lang_code, "Information unavailable", "जानकारी उपलब्ध नहीं", "माहिती उपलब्ध नाही"),
            "is_verified": bool(spec or base_sourcing.get("is_verified")),
            "fee_status": fees_obj["status"],
            "processing_time_status": time_obj["status"],
        },
    }


def _format_bullets(items: List[str]) -> str:
    return "\n".join(f"• {item}" for item in items if item)


def _format_numbered(items: List[str]) -> str:
    return "\n".join(f"{idx}. {item}" for idx, item in enumerate(items, start=1) if item)


def format_document_guidance_response(
    guidance: Dict[str, Any],
    *,
    lang: str = "en",
    focus: str = "all",
    is_missing_disclosure: bool = False,
) -> str:
    """
    Formats missing-document assistance into pure single-language markdown (`en`, `hi`, `mr`),
    clearly distinguishing Verified, Estimated, and Unavailable information across all focus modes.
    """
    lang_code = lang if lang in ("en", "hi", "mr") else "en"
    focus_mode = focus if focus in SUPPORTED_FOCUS_MODES else "all"

    title = guidance.get("title") or _t(lang_code, "Document", "दस्तावेज़", "कागदपत्र")
    active_scheme = guidance.get("active_scheme")
    requiring = guidance.get("requiring_active_schemes") or []
    portals = guidance.get("official_portals") or []
    fees = guidance.get("fees") or {}
    proc_time = guidance.get("processing_time") or {}
    steps = guidance.get("preparation_steps") or []
    fallback_obj = guidance.get("fallback_options") or {}
    fallback_steps = fallback_obj.get("action_steps") or []
    scheme_alts = fallback_obj.get("alternatives_from_scheme") or []

    # Header identifying document + active scheme
    if active_scheme:
        scheme_tag = f"{active_scheme['scheme_name']} ({active_scheme['scheme_code']})"
        mand_text = (
            _t(lang_code, "Mandatory", "अनिवार्य", "अनिवार्य")
            if active_scheme.get("is_mandatory")
            else _t(lang_code, "Optional / Conditional", "वैकल्पिक / शर्त आधारित", "पर्यायी / अटींवर आधारित")
        )
        scheme_ctx_line = _t(
            lang_code,
            f"Active Scheme: **{scheme_tag}** ({mand_text})",
            f"सक्रिय योजना: **{scheme_tag}** ({mand_text})",
            f"सक्रिय योजना: **{scheme_tag}** ({mand_text})",
        )
    elif requiring:
        names = ", ".join(f"{r['scheme_name']} ({r['scheme_code']})" for r in requiring[:3])
        scheme_ctx_line = _t(
            lang_code,
            f"Relevant Active Schemes Requiring This Document: **{names}**",
            f"इस दस्तावेज़ की आवश्यकता वाली सक्रिय योजनाएं: **{names}**",
            f"हे कागदपत्र लागणाऱ्या सक्रिय योजना: **{names}**",
        )
    else:
        scheme_ctx_line = _t(
            lang_code,
            "Active Scheme: None selected yet (share which scheme you are applying for to check scheme-specific rules).",
            "सक्रिय योजना: अभी चयनित नहीं (योजना-विशिष्ट नियम जांचने हेतु योजना का नाम बताएं)।",
            "सक्रिय योजना: अद्याप निवडलेली नाही (योजनेनुसार नियम तपासण्यासाठी योजनेचे नाव सांगा).",
        )

    portal_md = (
        "\n".join(f"• {p['label']}: [{p['url']}]({p['url']})" for p in portals if p.get("url"))
        if portals
        else _t(lang_code, "Information unavailable in our verified catalog.", "हमारे सत्यापित कैटलॉग में आधिकारिक पोर्टल जानकारी उपलब्ध नहीं है।", "आमच्या पडताळलेल्या यादीत अधिकृत पोर्टल माहिती उपलब्ध नाही.")
    )

    if focus_mode == "cost":
        v_cost: List[str] = []
        e_cost: List[str] = []
        u_cost: List[str] = []
        if fees.get("status") == "verified" and fees.get("value"):
            v_cost.append(fees["value"])
            if fees.get("estimated"):
                e_cost.append(fees["estimated"])
        elif fees.get("status") == "estimated" and fees.get("value"):
            e_cost.append(fees["value"])
        else:
            u_cost.append(_t(lang_code, "Official issuance/application fee is unavailable in our verified database (varies by state/institution).", "आधिकारिक शुल्क हमारे सत्यापित डेटाबेस में उपलब्ध नहीं है (राज्य/संस्थान के अनुसार भिन्न)।", "अधिकृत शुल्क आमच्या पडताळलेल्या डेटाबेसमध्ये उपलब्ध नाही (राज्य/संस्थेनुसार बदलते)."))
        u_cost.append(_t(lang_code, "Local third-party printing/photocopy/travel expenses are not fixed by government.", "स्थानीय फोटोकॉपी या आने-जाने का निजी खर्च सरकारी स्तर पर निर्धारित नहीं है।", "स्थानिक झेरॉक्स किंवा प्रवासाचा खाजगी खर्च शासकीय नियमांत निश्चित नसतो."))

        parts = [
            _t(lang_code, f"💰 **Cost & Fee Breakdown for {title}**\n{scheme_ctx_line}", f"💰 **{title} के लिए शुल्क विवरण**\n{scheme_ctx_line}", f"💰 **{title} साठी शुल्क व खर्च तपशील**\n{scheme_ctx_line}"),
        ]
        if v_cost:
            parts.append(_t(lang_code, "**Verified Information:**\n", "**सत्यापित जानकारी:**\n", "**पडताळलेली माहिती:**\n") + _format_bullets(v_cost))
        if e_cost:
            parts.append(_t(lang_code, "**Estimated Information:**\n", "**अनुमानित जानकारी:**\n", "**अंदाजे माहिती:**\n") + _format_bullets(e_cost))
        parts.append(_t(lang_code, "**Information Unavailable:**\n", "**उपलब्ध न होने वाली जानकारी:**\n", "**उपलब्ध नसलेली माहिती:**\n") + _format_bullets(u_cost))
        return "\n\n".join(parts)

    if focus_mode == "where_to_apply":
        v_where = []
        if guidance.get("issuing_authority"):
            v_where.append(_t(lang_code, f"Responsible Government Authority: {guidance['issuing_authority']}", f"जिम्मेदार सरकारी प्राधिकरण: {guidance['issuing_authority']}", f"जबाबदार शासकीय प्राधिकरण: {guidance['issuing_authority']}"))
        if guidance.get("where_to_obtain"):
            v_where.append(_t(lang_code, f"Application Offices & Portals: {guidance['where_to_obtain']}", f"आवेदन कार्यालय और पोर्टल: {guidance['where_to_obtain']}", f"अर्ज करण्याची कार्यालये व पोर्टल: {guidance['where_to_obtain']}"))
        u_where = list(guidance.get("unavailable_info") or []) or [_t(lang_code, "Exact local office street address and counter room number are unavailable.", "स्थानीय कार्यालय का सटीक सड़क पता उपलब्ध नहीं है।", "स्थानिक कार्यालयाचा नेमका पत्ता उपलब्ध नाही.")]
        parts = [
            _t(lang_code, f"🏛️ **Where to Apply for {title}**\n{scheme_ctx_line}", f"🏛️ **{title} के लिए कहाँ आवेदन करें**\n{scheme_ctx_line}", f"🏛️ **{title} साठी कुठे अर्ज करावा**\n{scheme_ctx_line}"),
            _t(lang_code, "**Verified Information:**\n", "**सत्यापित जानकारी:**\n", "**पडताळलेली माहिती:**\n") + (_format_bullets(v_where) if v_where else _t(lang_code, "Information unavailable.", "जानकारी उपलब्ध नहीं।", "माहिती उपलब्ध नाही.")),
            _t(lang_code, "**Official Portals:**\n", "**आधिकारिक पोर्टल:**\n", "**अधिकृत पोर्टल:**\n") + portal_md,
            _t(lang_code, "**Information Unavailable:**\n", "**उपलब्ध न होने वाली जानकारी:**\n", "**उपलब्ध नसलेली माहिती:**\n") + _format_bullets(u_where),
        ]
        return "\n\n".join(parts)

    if focus_mode == "process":
        parts = [
            _t(lang_code, f"🛠️ **Step-by-Step Preparation Process for {title}**\n{scheme_ctx_line}", f"🛠️ **{title} प्राप्त करने की चरण-दर-चरण प्रक्रिया**\n{scheme_ctx_line}", f"🛠️ **{title} मिळवण्याची टप्प्याटप्प्याने प्रक्रिया**\n{scheme_ctx_line}"),
        ]
        if steps:
            parts.append(_t(lang_code, "**Preparation & Application Steps (Verified Workflow):**\n", "**तैयारी और आवेदन चरण:**\n", "**तयारी आणि अर्ज करण्याचे टप्पे:**\n") + _format_numbered(steps))
        else:
            parts.append(_t(lang_code, "**Verified Process Information:** Detailed procedure steps are currently unavailable for this document in our database.", "**सत्यापित प्रक्रिया:** इस दस्तावेज़ के विस्तृत चरण डेटाबेस में उपलब्ध नहीं हैं।", "**पडताळलेली प्रक्रिया:** या कागदपत्रासाठी सविस्तर टप्पे डेटाबेसमध्ये उपलब्ध नाहीत."))

        est_lines = []
        if proc_time.get("value"):
            est_lines.append(_t(lang_code, f"Processing Time ({proc_time.get('status', 'estimated')}): {proc_time['value']}", f"अनुमानित समय: {proc_time['value']}", f"कालावधी: {proc_time['value']}"))
        if fees.get("value"):
            est_lines.append(_t(lang_code, f"Fee ({fees.get('status', 'estimated')}): {fees['value']}", f"शुल्क: {fees['value']}", f"शुल्क: {fees['value']}"))
        if est_lines:
            parts.append(_t(lang_code, "**Estimated Information:**\n", "**अनुमानित जानकारी:**\n", "**अंदाजे माहिती:**\n") + _format_bullets(est_lines))
        parts.append(_t(lang_code, "**Official Portals:**\n", "**आधिकारिक पोर्टल:**\n", "**अधिकृत पोर्टल:**\n") + portal_md)
        if guidance.get("unavailable_info"):
            parts.append(_t(lang_code, "**Information Unavailable:**\n", "**उपलब्ध न होने वाली जानकारी:**\n", "**उपलब्ध नसलेली माहिती:**\n") + _format_bullets(guidance["unavailable_info"]))
        return "\n\n".join(parts)

    if focus_mode == "fallback":
        v_fb: List[str] = []
        if scheme_alts:
            v_fb.append(_t(lang_code, f"Accepted Alternatives in Scheme Guidelines: {', '.join(scheme_alts)}", f"योजना दिशानिर्देशों में मान्य विकल्प: {', '.join(scheme_alts)}", f"योजनेत स्वीकारलेले पर्याय: {', '.join(scheme_alts)}"))
        v_fb.extend(fallback_steps or fallback_obj.get("action_steps") or [])
        parts = [
            _t(lang_code, f"🔄 **What If You Cannot Obtain {title}?**\n{scheme_ctx_line}", f"🔄 **यदि {title} प्राप्त न हो सके तो क्या करें?**\n{scheme_ctx_line}", f"🔄 **जर {title} मिळवता येत नसेल तर काय करावे?**\n{scheme_ctx_line}"),
            _t(lang_code, "**Verified Alternatives & Fallback Guidance:**\n", "**सत्यापित विकल्प और आगे के उपाय:**\n", "**पडताळलेले पर्याय आणि उपाय:**\n") + (_format_bullets(v_fb) if v_fb else _t(lang_code, "No automatic waiver exists in scheme guidelines.", "योजना नियमों में स्वतः छूट उपलब्ध नहीं है।", "योजनेच्या नियमांत आपोआप सूट उपलब्ध नाही.")),
            _t(lang_code, "**Information Unavailable:**\n", "**उपलब्ध न होने वाली जानकारी:**\n", "**उपलब्ध नसलेली माहिती:**\n") + _format_bullets([
                _t(lang_code, "Individual local Tehsil/Block officer discretion on disputed property or missing ancestral records cannot be predicted.", "विवादित संपत्ति या स्थानीय अधिकारी के विवेकाधीन निर्णय की पूर्व भविष्यवाणी उपलब्ध नहीं है।", "वादग्रस्त जमीन किंवा स्थानिक अधिकाऱ्यांच्या विशेष निर्णयाची पूर्वकल्पना उपलब्ध नाही."),
            ]),
        ]
        return "\n\n".join(parts)

    if focus_mode == "why_required":
        parts = [
            _t(lang_code, f"📌 **Why {title} Is Required**\n{scheme_ctx_line}", f"📌 **{title} क्यों आवश्यक है?**\n{scheme_ctx_line}", f"📌 **{title} का आवश्यक आहे?**\n{scheme_ctx_line}"),
            _t(lang_code, "**Verified Information:**\n", "**सत्यापित जानकारी:**\n", "**पडताळलेली माहिती:**\n") + _format_bullets([guidance.get("why_required") or _t(lang_code, "Information unavailable.", "जानकारी उपलब्ध नहीं।", "माहिती उपलब्ध नाही.")]),
        ]
        if active_scheme and active_scheme.get("waiver_reason"):
            parts.append(_t(lang_code, "**Conditional Applicability:**\n", "**शर्त आधारित लागू होने की स्थिति:**\n", "**अटींवर आधारित नियम:**\n") + active_scheme["waiver_reason"])
        return "\n\n".join(parts)

    # Default focus == "all": Full 10-element assistance + Verified / Estimated / Unavailable separation
    intro = (
        _t(
            lang_code,
            f"ℹ️ No worries — here is complete preparation assistance for **{title}** ({scheme_ctx_line}).",
            f"ℹ️ कोई बात नहीं — **{title}** प्राप्त करने की संपूर्ण सहायता नीचे दी गई है ({scheme_ctx_line})।",
            f"ℹ️ काळजी करू नका — **{title}** मिळवण्यासाठी संपूर्ण मार्गदर्शन खालीलप्रमाणे आहे ({scheme_ctx_line}).",
        )
        if is_missing_disclosure
        else _t(
            lang_code,
            f"📄 **Document Preparation Assistance: {title}**\n{scheme_ctx_line}",
            f"📄 **दस्तावेज़ तैयारी सहायता: {title}**\n{scheme_ctx_line}",
            f"📄 **कागदपत्र तयारी सहाय्य: {title}**\n{scheme_ctx_line}",
        )
    )

    sections: List[str] = [intro]

    verified_bullets = list(guidance.get("verified_info") or [])
    if verified_bullets:
        sections.append(
            _t(lang_code, "### Verified Information", "### सत्यापित जानकारी", "### पडताळलेली माहिती")
            + "\n"
            + _format_bullets(verified_bullets)
        )

    sections.append(
        _t(lang_code, "**Official Portals:**", "**आधिकारिक पोर्टल:**", "**अधिकृत पोर्टल:**")
        + "\n"
        + portal_md
    )

    if steps:
        sections.append(
            _t(lang_code, "**How to Prepare & Obtain (Step-by-Step):**", "**तैयारी और आवेदन की प्रक्रिया:**", "**तयारी आणि मिळवण्याची प्रक्रिया:**")
            + "\n"
            + _format_numbered(steps)
        )

    estimated_bullets = list(guidance.get("estimated_info") or [])
    if estimated_bullets:
        sections.append(
            _t(lang_code, "### Estimated Information", "### अनुमानित जानकारी", "### अंदाजे माहिती")
            + "\n"
            + _format_bullets(estimated_bullets)
        )

    unavailable_bullets = list(guidance.get("unavailable_info") or [])
    if unavailable_bullets:
        sections.append(
            _t(lang_code, "### Information Unavailable", "### उपलब्ध न होने वाली जानकारी", "### उपलब्ध नसलेली माहिती")
            + "\n"
            + _format_bullets(unavailable_bullets)
        )

    fallback_lines: List[str] = []
    if scheme_alts:
        fallback_lines.append(
            _t(
                lang_code,
                f"Scheme-accepted alternatives: {', '.join(scheme_alts)}",
                f"योजना में मान्य विकल्प: {', '.join(scheme_alts)}",
                f"योजनेत मान्य पर्याय: {', '.join(scheme_alts)}",
            )
        )
    fallback_lines.extend(fallback_steps)
    if fallback_lines:
        sections.append(
            _t(lang_code, "**If You Cannot Obtain It:**", "**यदि यह दस्तावेज़ न मिल सके तो क्या करें:**", "**जर हे कागदपत्र मिळू शकले नाही तर:**")
            + "\n"
            + _format_bullets(fallback_lines)
        )

    if not active_scheme and requiring:
        sections.append(
            _t(
                lang_code,
                "💡 Tell me which scheme you are applying for (e.g., PM-KISAN or PMAY-G) so I can check scheme-specific rules and alternatives.",
                "💡 कृपया बताएं आप किस योजना के लिए आवेदन कर रहे हैं (जैसे PM-KISAN या PMAY-G) ताकि मैं योजना-विशिष्ट नियम जांच सकूं।",
                "💡 तुम्ही कोणत्या योजनेसाठी अर्ज करणार आहात (उदा. PM-KISAN किंवा PMAY-G) ते सांगा म्हणजे मी त्यानुसार नेमके नियम सांगेन.",
            )
        )

    if guidance.get("vault_upload_note"):
        sections.append(f"📌 {guidance['vault_upload_note']}")

    return "\n\n".join(sections)
