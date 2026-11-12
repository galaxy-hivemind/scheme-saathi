"""
Scheme Saathi Multilingual Knowledge Registry.
Provides verified, authentic translations and localized content for English ('en'),
Hindi ('hi'), and Marathi ('mr'), ensuring 100% clean responses with zero language mixing.
"""
from typing import Dict, Any, Optional, List


MINISTRY_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "Government of Maharashtra": {
        "en": "Government of Maharashtra",
        "hi": "महाराष्ट्र सरकार",
        "mr": "महाराष्ट्र शासन",
    },
    "Ministry of Agriculture and Farmers Welfare": {
        "en": "Ministry of Agriculture and Farmers Welfare",
        "hi": "कृषि एवं किसान कल्याण मंत्रालय",
        "mr": "कृषी आणि शेतकरी कल्याण मंत्रालय",
    },
    "Ministry of Education": {
        "en": "Ministry of Education",
        "hi": "शिक्षा मंत्रालय",
        "mr": "शिक्षण मंत्रालय",
    },
    "Ministry of Finance": {
        "en": "Ministry of Finance",
        "hi": "वित्त मंत्रालय",
        "mr": "वित्त मंत्रालय",
    },
    "Ministry of Fisheries, Animal Husbandry and Dairying": {
        "en": "Ministry of Fisheries, Animal Husbandry and Dairying",
        "hi": "मत्स्यपालन, पशुपालन एवं डेयरी मंत्रालय",
        "mr": "मत्स्यव्यवसाय, पशुसंवर्धन आणि दुग्धव्यवसाय मंत्रालय",
    },
    "Ministry of Health and Family Welfare": {
        "en": "Ministry of Health and Family Welfare",
        "hi": "स्वास्थ्य एवं परिवार कल्याण मंत्रालय",
        "mr": "आरोग्य आणि कुटुंब कल्याण मंत्रालय",
    },
    "Ministry of Housing and Urban Affairs": {
        "en": "Ministry of Housing and Urban Affairs",
        "hi": "आवास एवं शहरी कार्य मंत्रालय",
        "mr": "गृहनिर्माण आणि शहरी व्यवहार मंत्रालय",
    },
    "Ministry of Micro, Small and Medium Enterprises": {
        "en": "Ministry of Micro, Small and Medium Enterprises",
        "hi": "सूक्ष्म, लघु एवं मध्यम उद्यम मंत्रालय",
        "mr": "सूक्ष्म, लघु आणि मध्यम उद्योग मंत्रालय",
    },
    "Ministry of Petroleum and Natural Gas": {
        "en": "Ministry of Petroleum and Natural Gas",
        "hi": "पेट्रोलियम एवं प्राकृतिक गैस मंत्रालय",
        "mr": "पेट्रोलियम आणि नैसर्गिक वायू मंत्रालय",
    },
    "Ministry of Rural Development": {
        "en": "Ministry of Rural Development",
        "hi": "ग्रामीण विकास मंत्रालय",
        "mr": "ग्रामीण विकास मंत्रालय",
    },
    "Ministry of Skill Development and Entrepreneurship": {
        "en": "Ministry of Skill Development and Entrepreneurship",
        "hi": "कौशल विकास एवं उद्यमशीलता मंत्रालय",
        "mr": "कौशल्य विकास आणि उद्योजकता मंत्रालय",
    },
    "Ministry of Social Justice and Empowerment": {
        "en": "Ministry of Social Justice and Empowerment",
        "hi": "सामाजिक न्याय एवं अधिकारिता मंत्रालय",
        "mr": "सामाजिक न्याय आणि विशेष सहाय्य मंत्रालय",
    },
    "Ministry of Women and Child Development": {
        "en": "Ministry of Women and Child Development",
        "hi": "महिला एवं बाल विकास मंत्रालय",
        "mr": "महिला आणि बाल विकास मंत्रालय",
    },
}

CATEGORY_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "agriculture": {
        "en": "Agriculture & Allied Sectors",
        "hi": "कृषि एवं संबद्ध क्षेत्र",
        "mr": "कृषी आणि संलग्न क्षेत्र",
    },
    "education": {
        "en": "Education & Scholarships",
        "hi": "शिक्षा एवं छात्रवृत्ति",
        "mr": "शिक्षण आणि शिष्यवृत्ती",
    },
    "employment": {
        "en": "Employment & Livelihood",
        "hi": "रोजगार एवं आजीविका",
        "mr": "रोजगार आणि उपजीविका",
    },
    "financial_inclusion": {
        "en": "Banking & Financial Inclusion",
        "hi": "बैंकिंग एवं वित्तीय समावेशन",
        "mr": "बँकिंग आणि वित्तीय समावेशन",
    },
    "health": {
        "en": "Healthcare & Medical Insurance",
        "hi": "स्वास्थ्य एवं चिकित्सा बीमा",
        "mr": "आरोग्य आणि वैद्यकीय विमा",
    },
    "housing": {
        "en": "Housing & Urban/Rural Shelter",
        "hi": "आवास एवं आश्रय",
        "mr": "गृहनिर्माण आणि निवारा",
    },
    "skill_development": {
        "en": "Skill Training & Entrepreneurship",
        "hi": "कौशल विकास एवं उद्यमिता",
        "mr": "कौशल्य विकास आणि उद्योजकता",
    },
    "social_security": {
        "en": "Social Security & Pensions",
        "hi": "सामाजिक सुरक्षा एवं पेंशन",
        "mr": "सामाजिक सुरक्षा आणि पेन्शन",
    },
    "women_welfare": {
        "en": "Women & Child Welfare",
        "hi": "महिला एवं बाल कल्याण",
        "mr": "महिला आणि बाल कल्याण",
    },
}

# Localized metadata for core welfare schemes
SCHEME_LOCALIZED_METADATA: Dict[str, Dict[str, Dict[str, Any]]] = {
    "PM-KISAN": {
        "en": {
            "name": "Pradhan Mantri Kisan Samman Nidhi",
            "description": "Central sector scheme providing income support of ₹6,000 per year in three equal instalments of ₹2,000 to all landholding farmer families across India directly into their Aadhaar-seeded bank accounts.",
            "benefits": "₹6,000 per year transferred in 3 equal instalments of ₹2,000 every 4 months via Direct Benefit Transfer (DBT) directly into Aadhaar-seeded bank accounts.",
            "target_beneficiaries": "Small, marginal, and all cultivable landholding farmer families.",
            "eligibility_summary": "All landholding farmer families possessing cultivable agricultural land registered in their name. Institutional landholders, serving/retired government employees, professionals, and income-tax payers are excluded.",
            "disbursement_mode": "Direct Benefit Transfer (DBT) via Aadhaar Payment Bridge (APB)",
        },
        "hi": {
            "name": "प्रधानमंत्री किसान सम्मान निधि",
            "description": "देश के सभी भूमिधारक किसान परिवारों को प्रति वर्ष ₹6,000 की वित्तीय सहायता प्रदान करने वाली केंद्रीय क्षेत्र योजना, जो सीधे आधार-सीडेड बैंक खाते में भेजी जाती है।",
            "benefits": "प्रति वर्ष ₹6,000 की आर्थिक सहायता। हर 4 महीने में ₹2,000 की 3 समान किस्तें सीधे आधार-सीडेड बैंक खाते में डीबीटी (DBT) द्वारा अंतरित की जाती हैं।",
            "target_beneficiaries": "सभी कृषि योग्य भूमिधारक किसान परिवार (लघु एवं सीमांत किसान)।",
            "eligibility_summary": "वे सभी किसान परिवार जिनके नाम पर कृषि योग्य भूमि दर्ज है। संस्थागत भूमिधारक, सरकारी कर्मचारी, संवैधानिक पदों के धारक, पेशेवर और आयकर दाता इस योजना से बाहर हैं।",
            "disbursement_mode": "आधार भुगतान प्रणाली (APB) के माध्यम से प्रत्यक्ष लाभ अंतरण (DBT)",
        },
        "mr": {
            "name": "प्रधानमंत्री किसान सन्मान निधी",
            "description": "देशातील सर्व शेतजमीनधारक शेतकरी कुटुंबांना वर्षाला ₹६,००० चे थेट आर्थिक सहाय्य देणारी केंद्र शासनाची प्रमुख कल्याणकारी योजना.",
            "benefits": "दरवर्षी ₹६,००० थेट बँक खात्यात. दर ४ महिन्यांनी ₹२,००० चा १ हप्ता (वर्षाला ३ हप्ते) थेट आधारशी जोडलेल्या बँक खात्यावर DBT द्वारे जमा होतो.",
            "target_beneficiaries": "सर्व शेतजमीनधारक शेतकरी कुटुंबे (अल्प, अत्यल्प व इतर शेतकरी).",
            "eligibility_summary": "ज्या शेतकरी कुटुंबांच्या नावावर लागवडीयोग्य शेतजमीन आहे ते सर्व पात्र आहेत. संस्थात्मक जमीनधारक, शासकीय कर्मचारी, निवृत्तीवेतनधारक (₹१०,०००+), डॉक्टर/इंजिनिअर/वकील आणि आयकर भरणारे शेतकरी या योजनेसाठी अपात्र आहेत.",
            "disbursement_mode": "थेट लाभ हस्तांतरण (DBT) द्वारे आधार संलग्न बँक खात्यात",
        },
    },
    "AB-PMJAY": {
        "en": {
            "name": "Ayushman Bharat - Pradhan Mantri Jan Arogya Yojana",
            "description": "World's largest government-funded healthcare assurance scheme offering cashless secondary and tertiary hospital care coverage up to ₹5,00,000 per family per year.",
            "benefits": "Cashless hospitalization coverage of up to ₹5,00,000 per family per year across 27,000+ empanelled public and private hospitals across India.",
            "target_beneficiaries": "Deprived rural families and identified occupational categories of urban workers based on SECC 2011 / NFSA ration card data.",
            "eligibility_summary": "Households identified under Socio-Economic Caste Census (SECC 2011) or possessing eligible Antyodaya/Priority Ration Cards. Includes senior citizens aged 70+ under expanded Ayushman coverage.",
            "disbursement_mode": "100% Cashless and paperless treatment at empanelled healthcare providers",
        },
        "hi": {
            "name": "आयुष्मान भारत - प्रधानमंत्री जन आरोग्य योजना",
            "description": "विश्व की सबसे बड़ी स्वास्थ्य बीमा योजना, जो पात्र परिवारों को द्वितीयक और तृतीयक उपचार के लिए प्रति वर्ष ₹5 लाख तक का कैशलेस स्वास्थ्य सुरक्षा कवर प्रदान करती है।",
            "benefits": "प्रति परिवार प्रति वर्ष ₹5,00,000 तक का कैशलेस अस्पताल उपचार। देश के 27,000 से अधिक सूचीबद्ध सरकारी और निजी अस्पतालों में 1,900+ उपचार शामिल हैं।",
            "target_beneficiaries": "एसईसीसी 2011 सूची में शामिल ग्रामीण व शहरी गरीब परिवार तथा प्राथमिकता राशन कार्ड धारक।",
            "eligibility_summary": "सामाजिक, आर्थिक और जातिगत जनगणना (SECC 2011) के आधार पर चयनित परिवार या अंत्योदय/पात्रता गृहस्थी राशन कार्ड धारक। 70 वर्ष से अधिक आयु के वरिष्ठ नागरिकों के लिए भी विस्तारित।",
            "disbursement_mode": "सूचीबद्ध अस्पतालों में पूर्णतः कैशलेस और पेपरलेस उपचार",
        },
        "mr": {
            "name": "आयुष्मान भारत - प्रधानमंत्री जन आरोग्य योजना",
            "description": "जगातील सर्वात मोठी शासकीय आरोग्य संरक्षण योजना, ज्यामध्ये पात्र कुटुंबांना दरवर्षी ₹५ लाखांपर्यंत मोफत व कॅशलेस वैद्यकीय उपचार मिळतात.",
            "benefits": "कुटुंबाला दरवर्षी ₹५,००,००० पर्यंत मोफत व कॅशलेस वैद्यकीय उपचार संरक्षण. देशातील २७,००० हून अधिक सरकारी व खाजगी रुग्णालयांमध्ये १,९००+ उपचारांचा समावेश.",
            "target_beneficiaries": "सामाजिक व आर्थिक जात जनगणना (SECC 2011) मधील पात्र ग्रामीण व शहरी दुर्बल कुटुंबे आणि रेशन कार्ड धारक.",
            "eligibility_summary": "SECC २०११ च्या यादीत समाविष्ट कुटुंबे किंवा पिवळे/केशरी रेशन कार्ड धारक कुटुंबे. ७० वर्षांवरील ज्येष्ठ नागरिकांसाठी विस्तारित कवच.",
            "disbursement_mode": "संलग्न रुग्णालयांमध्ये १००% कॅशलेस व मोफत उपचार",
        },
    },
    "KCC": {
        "en": {
            "name": "Kisan Credit Card Scheme",
            "description": "Provides timely, cost-effective institutional short-term credit up to ₹3,00,000 to farmers for crop cultivation, animal husbandry, and allied agricultural activities at a concessional interest rate.",
            "benefits": "Revolving credit limit up to ₹3,00,000 at benchmark rate of 7% per annum, reduced to an effective rate of 4% per annum upon prompt repayment within 1 year.",
            "target_beneficiaries": "Owner cultivators, tenant farmers, oral lessees, sharecroppers, and SHG/JLG farmer groups.",
            "eligibility_summary": "All individual or joint borrower farmers cultivating land, tenant farmers, dairy/fisheries farmers. Age: 18 to 75 years.",
            "disbursement_mode": "Credit limit sanctioned via KCC RuPay debit card and savings account",
        },
        "hi": {
            "name": "किसान क्रेडिट कार्ड योजना",
            "description": "किसानों को फसलों की खेती, पशुपालन और संबद्ध गतिविधियों के लिए समय पर और सस्ती ब्याज दर पर ₹3,00,000 तक का संस्थागत ऋण उपलब्ध कराने की योजना।",
            "benefits": "₹3,00,000 तक का अल्पकालिक कृषि ऋण। समय पर पुनर्भुगतान करने पर प्रभावी ब्याज दर मात्र 4% प्रति वर्ष (3% शीघ्र भुगतान प्रोत्साहन के साथ)।",
            "target_beneficiaries": "सभी भूमिधर किसान, बटाईदार किसान, काश्तकार और स्वयं सहायता समूहों (SHG) के सदस्य।",
            "eligibility_summary": "कृषि योग्य भूमि पर खेती करने वाले सभी किसान, पशुपालक एवं मत्स्यपालक। आयु सीमा: 18 से 75 वर्ष।",
            "disbursement_mode": "केसीसी रूपे (RuPay) कार्ड और बैंक खाते के माध्यम से आहरण",
        },
        "mr": {
            "name": "किसान क्रेडिट कार्ड योजना",
            "description": "शेतकऱ्यांना पीक लागवड, दुग्धव्यवसाय, मत्स्यव्यवसाय आणि खेळत्या भांडवलासाठी ₹३,००,००० पर्यंतचे स्वस्त दरातील अल्पमुदत कृषी कर्ज देणारी योजना.",
            "benefits": "₹३,००,००० पर्यंतचे अल्पमुदत पीक कर्ज. वेळेवर परतफेड केल्यास ३% सवलतीसह निव्वळ व्याज दर केवळ ४% वार्षिक. ₹१.६ लाखांपर्यंत विनातारण कर्ज.",
            "target_beneficiaries": "जमीन मालक शेतकरी, कुळ शेतकरी, बटाईदार आणि शेतकरी बचत गट (SHG/JLG).",
            "eligibility_summary": "लागवडीखालील शेतजमीन असणारे सर्व शेतकरी, पशुपालक व मच्छिमार. वय: १८ ते ७५ वर्षे.",
            "disbursement_mode": "केसीसी रूपे (RuPay) कार्ड आणि बँक खात्याद्वारे कर्ज वितरण",
        },
    },
    "MLBY-MH": {
        "en": {
            "name": "Mukhyamantri Majhi Ladki Bahin Yojana",
            "description": "Maharashtra flagship welfare scheme granting direct monthly financial assistance of ₹1,500 (₹18,000/year) to economically weaker women aged 21-65 years.",
            "benefits": "Direct financial assistance of ₹1,500 per month (₹18,000 per year) transferred via DBT into Aadhaar-linked individual bank accounts.",
            "target_beneficiaries": "Eligible women aged 21 to 65 years who are permanent residents of Maharashtra.",
            "eligibility_summary": "Women aged 21 to 65 years with permanent Maharashtra domicile, holding Yellow or Orange Ration Card, and combined family income not exceeding ₹2.5 Lakh per annum.",
            "disbursement_mode": "Direct Benefit Transfer (DBT) directly into Aadhaar-seeded bank account",
        },
        "hi": {
            "name": "मुख्यमंत्री माझी लाड़की बहिन योजना",
            "description": "महाराष्ट्र सरकार की महत्वाकांक्षी योजना, जिसके तहत 21-65 आयु वर्ग की आर्थिक रूप से कमजोर पात्र महिलाओं को प्रति माह ₹1,500 की सीधी आर्थिक सहायता दी जाती है।",
            "benefits": "प्रति माह ₹1,500 (वार्षिक ₹18,000) की प्रत्यक्ष वित्तीय सहायता, जो सीधे लाभार्थी महिला के आधार-लिंक बैंक खाते में डीबीटी द्वारा भेजी जाती है।",
            "target_beneficiaries": "महाराष्ट्र की स्थायी निवासी 21 से 65 वर्ष आयु वर्ग की पात्र महिलाएं।",
            "eligibility_summary": "21 से 65 वर्ष की महिलाएं, जो महाराष्ट्र की स्थायी निवासी हैं, पीला या नारंगी राशन कार्ड धारक हैं, और पारिवारिक वार्षिक आय ₹2.5 लाख से अधिक नहीं है।",
            "disbursement_mode": "प्रत्यक्ष लाभ अंतरण (DBT) सीधे आधार से जुड़े बैंक खाते में",
        },
        "mr": {
            "name": "मुख्यमंत्री माझी लाडकी बहीण योजना",
            "description": "महाराष्ट्र शासनाची महत्वाकांक्षी योजना, ज्यामध्ये राज्यातील २१ ते ६५ वयोगटातील पात्र महिलांना स्वावलंबनासाठी दरमहा ₹१,५०० (वर्षाला ₹१८,०००) थेट बँक खात्यात दिले जातात.",
            "benefits": "दरमहा ₹१,५०० (वर्षाला ₹१८,०००) थेट आर्थिक सहाय्य, जे कोणत्याही मध्यस्थाशिवाय आधार जोडलेल्या वैयक्तिक बँक खात्यात DBT द्वारे जमा होते.",
            "target_beneficiaries": "महाराष्ट्रातील २१ ते ६५ वर्षे वयोगटातील विवाहित, विधवा, घटस्फोटित व निराधार पात्र महिला.",
            "eligibility_summary": "वय २१ ते ६५ वर्षे, महाराष्ट्र राज्याचे अधिवास (डोमिसाईल/रेशन कार्ड), पिवळे किंवा केशरी रेशन कार्ड आणि कुटुंबाचे एकत्रित वार्षिक उत्पन्न ₹२.५० लाखांपेक्षा जास्त नसावे.",
            "disbursement_mode": "थेट लाभ हस्तांतरण (DBT) द्वारे आधार संलग्न वैयक्तिक बँक खात्यात",
        },
    },
    "NSMSNY-MH": {
        "en": {
            "name": "Namo Shetkari Maha Samman Nidhi Yojana",
            "description": "Maharashtra government scheme offering additional ₹6,000 per year to farmers registered under PM-KISAN, granting Maharashtra farmers ₹12,000 in total annual assistance.",
            "benefits": "₹6,000 per year (in 3 instalments of ₹2,000) from Maharashtra Government, combined with PM-KISAN ₹6,000, totaling ₹12,000 per year.",
            "target_beneficiaries": "All verified and approved PM-KISAN beneficiary farmers in the State of Maharashtra.",
            "eligibility_summary": "Must be an active, verified, and approved beneficiary under PM-KISAN in Maharashtra with landholding records and active Aadhaar e-KYC.",
            "disbursement_mode": "Direct Benefit Transfer (DBT) credited alongside PM-KISAN instalments",
        },
        "hi": {
            "name": "नमो शेतकरी महा सम्मान निधि योजना",
            "description": "महाराष्ट्र सरकार द्वारा PM-KISAN के पंजीकृत किसानों को अतिरिक्त ₹6,000 प्रति वर्ष की सहायता, जिससे महाराष्ट्र के किसानों को कुल ₹12,000 प्रति वर्ष मिलते हैं।",
            "benefits": "महाराष्ट्र सरकार द्वारा ₹6,000 प्रति वर्ष (₹2,000 की 3 किस्तें)। PM-KISAN के साथ मिलकर महाराष्ट्र के किसानों को कुल ₹12,000 प्रति वर्ष प्राप्त होते हैं।",
            "target_beneficiaries": "महाराष्ट्र राज्य के सभी सत्यापित और स्वीकृत PM-KISAN लाभार्थी किसान।",
            "eligibility_summary": "महाराष्ट्र में PM-KISAN के तहत पंजीकृत व स्वीकृत किसान जिनका ई-केवाईसी और बैंक आधार सीडिंग पूर्ण है।",
            "disbursement_mode": "प्रत्यक्ष लाभ अंतरण (DBT) सीधे आधार-सीडेड बैंक खाते में",
        },
        "mr": {
            "name": "नमो शेतकरी महासन्मान निधी योजना",
            "description": "महाराष्ट्र शासनाकडून PM-KISAN पात्र शेतकऱ्यांना अतिरिक्त ₹६,००० वार्षिक सहाय्य, ज्यामुळे महाराष्ट्रातील शेतकऱ्यांना एकूण ₹१२,००० वार्षिक आर्थिक लाभ मिळतो.",
            "benefits": "महाराष्ट्र शासनाकडून वर्षाला ₹६,००० (३ हप्त्यांमध्ये ₹२,०००). PM-KISAN चे ₹६,००० मिळून एकूण ₹१२,००० वार्षिक आर्थिक लाभ थेट बँक खात्यात.",
            "target_beneficiaries": "महाराष्ट्र राज्यातील सर्व नोंदणीकृत आणि मंजूर PM-KISAN लाभार्थी शेतकरी.",
            "eligibility_summary": "PM-KISAN योजनेत पात्र असणारे महाराष्ट्रातील शेतकरी. स्वतंत्र अर्जाची गरज नाही; केवळ आधार e-KYC आणि बँक आधार सीडिंग सक्रिय असणे आवश्यक आहे.",
            "disbursement_mode": "थेट लाभ हस्तांतरण (DBT) द्वारे बँक खात्यात",
        },
    },
    "PMAY-G": {
        "en": {
            "name": "Pradhan Mantri Awaas Yojana - Gramin",
            "description": "Provides financial grant assistance to houseless and kutcha house living rural households for constructing durable pucca houses with basic amenities.",
            "benefits": "Financial assistance of ₹1,20,000 in plains and ₹1,30,000 in hilly/difficult areas, plus 90-95 days of unskilled labor wages under MGNREGA and ₹12,000 for toilet construction.",
            "target_beneficiaries": "Houseless rural families and households living in zero, one, or two room kutcha houses identified under SECC 2011 / Awaas+.",
            "eligibility_summary": "Rural households without pucca house anywhere in India. Families with motorized vehicles, agricultural equipment, or salaried members are excluded.",
            "disbursement_mode": "Instalment-based DBT directly into Aadhaar-linked bank accounts linked to house construction milestones",
        },
        "hi": {
            "name": "प्रधानमंत्री आवास योजना - ग्रामीण",
            "description": "ग्रामीण क्षेत्रों के बेघर और कच्चे घरों में रहने वाले परिवारों को बुनियादी सुविधाओं से युक्त पक्का मकान बनाने हेतु आर्थिक अनुदान सहायता।",
            "benefits": "मैदानी क्षेत्रों में ₹1,20,000 और पहाड़ी/दुर्गम क्षेत्रों में ₹1,30,000 की वित्तीय सहायता, साथ ही मनरेगा के तहत 90-95 दिनों की मजदूरी और शौचालय निर्माण हेतु ₹12,000 अतिरिक्त।",
            "target_beneficiaries": "ग्रामीण क्षेत्रों के बेघर परिवार और कच्चे मकानों में रहने वाले वंचित परिवार।",
            "eligibility_summary": "भारत में कहीं भी पक्का मकान न रखने वाले ग्रामीण परिवार। दो/चार पहिया वाहन, सरकारी नौकरी या ₹10,000 से अधिक मासिक आय वाले परिवार अपात्र हैं।",
            "disbursement_mode": "निर्माण की प्रगति के अनुसार किस्तों में प्रत्यक्ष लाभ अंतरण (DBT)",
        },
        "mr": {
            "name": "प्रधानमंत्री आवास योजना - ग्रामीण",
            "description": "ग्रामीण भागातील बेघर आणि कच्च्या घरात राहणाऱ्या गरीब कुटुंबांना मूलभूत सुविधांसह पक्के घर बांधण्यासाठी थेट शासकीय अनुदान देणारी योजना.",
            "benefits": "सपाट भागात ₹१,२०,००० आणि डोंगरी/दुर्गम भागात ₹१,३०,००० चे अनुदान, अधिक मनरेगा अंतर्गत ९०-९५ दिवसांची अकुशल मजुरी आणि शौचालय बांधकामासाठी ₹१२,००० स्वतंत्र.",
            "target_beneficiaries": "ग्रामीण भागातील बेघर कुटुंबे आणि कच्च्या घरात राहणारे सामाजिक-आर्थिकदृष्ट्या दुर्बल घटक.",
            "eligibility_summary": "संपूर्ण भारतात कुठेही पक्के घर नसलेले ग्रामीण कुटुंब. घरात चारचाकी वाहन, शासकीय नोकरी किंवा ₹१०,००० पेक्षा जास्त मासिक उत्पन्न असल्यास अपात्र.",
            "disbursement_mode": "बांधकामाच्या टप्प्यांनुसार थेट बँक खात्यात हप्त्यांमध्ये DBT जमा",
        },
    },
    "APY": {
        "en": {
            "name": "Atal Pension Yojana",
            "description": "Guaranteed minimum monthly pension scheme for all Indian citizens in the unorganized sector upon reaching 60 years of age.",
            "benefits": "Guaranteed monthly pension of ₹1,000, ₹2,000, ₹3,000, ₹4,000, or ₹5,000 per month from age 60 until demise, with same pension to spouse and corpus refund to nominee.",
            "target_beneficiaries": "All Indian citizens aged 18 to 40 years, especially unorganized sector workers.",
            "eligibility_summary": "Any Indian citizen aged 18 to 40 having a savings bank account. Income-tax payers joining after October 1, 2022 are not eligible.",
            "disbursement_mode": "Monthly direct pension credit into pensioner's savings bank account via auto-credit",
        },
        "hi": {
            "name": "अटल पेंशन योजना",
            "description": "असंगठित क्षेत्र के सभी भारतीय नागरिकों के लिए 60 वर्ष की आयु के बाद निश्चित मासिक पेंशन प्रदान करने वाली भारत सरकार की सामाजिक सुरक्षा योजना।",
            "benefits": "60 वर्ष की आयु के बाद ₹1,000, ₹2,000, ₹3,000, ₹4,000 या ₹5,000 प्रति माह की निश्चित आजीवन पेंशन। जीवनसाथी को समान पेंशन तथा नामित व्यक्ति को कुल राशि की वापसी।",
            "target_beneficiaries": "18 से 40 वर्ष की आयु के सभी भारतीय नागरिक, विशेषकर असंगठित क्षेत्र के कामगार।",
            "eligibility_summary": "18 से 40 वर्ष के भारतीय नागरिक जिनके पास बचत बैंक खाता है। 1 अक्टूबर 2022 के बाद आयकरदाता इस योजना में शामिल होने के लिए पात्र नहीं हैं।",
            "disbursement_mode": "60 वर्ष के पश्चात प्रति माह सीधे बचत बैंक खाते में पेंशन अंतरण",
        },
        "mr": {
            "name": "अटल पेन्शन योजना",
            "description": "असंघटित क्षेत्रातील कामगार व सर्वसामान्य नागरिकांना वयाच्या ६० वर्षांनंतर निश्चित मासिक पेन्शनची हमी देणारी केंद्र सरकारची सामाजिक सुरक्षा योजना.",
            "benefits": "वयाच्या ६० वर्षांनंतर दरमहा ₹१,०००, ₹२,०००, ₹३,०००, ₹४,००० किंवा ₹५,००० ची हमीदार पेन्शन. मृत्यूनंतर पती/पत्नीला समान पेन्शन आणि वारसाला संपूर्ण जमा निधी परत.",
            "target_beneficiaries": "१८ ते ४० वयोगटातील सर्व भारतीय नागरिक, प्रामुख्याने असंघटित क्षेत्रातील कष्टकरी.",
            "eligibility_summary": "१८ ते ४० वर्षे वयोगटातील बँक खातेधारक भारतीय नागरिक. १ ऑक्टोबर २०२२ नंतर आयकर भरणारे नागरिक या योजनेसाठी अपात्र आहेत.",
            "disbursement_mode": "वयाच्या ६० वर्षांनंतर दरमहा थेट बचत बँक खात्यात पेन्शन जमा",
        },
    },
    "PM-SVANIDHI": {
        "en": {
            "name": "PM Street Vendor's AtmaNirbhar Nidhi",
            "description": "Micro-credit collateral-free working capital loan scheme for urban street vendors to resume and scale livelihoods.",
            "benefits": "Collateral-free working capital loan starting at ₹10,000 (1st tranche), ₹20,000 (2nd tranche), and ₹50,000 (3rd tranche) with 7% interest subsidy and cashback on digital transactions.",
            "target_beneficiaries": "Urban and peri-urban street vendors, hawkers, thelawalas, and small service providers.",
            "eligibility_summary": "Street vendors possessing Certificate of Vending (CoV) / Identity Card issued by Urban Local Bodies (ULB) or Letter of Recommendation (LoR).",
            "disbursement_mode": "Disbursed directly into vendor's savings bank account",
        },
        "hi": {
            "name": "पीएम स्वनिधि (स्ट्रीट वेंडर्स आत्मनिर्भर निधि)",
            "description": "शहरी रेहड़ी-पटरी विक्रेताओं (स्ट्रीट वेंडर्स) को आजीविका पुनः शुरू करने और विस्तार के लिए बिना किसी गारंटी के कार्यशील पूंजी ऋण प्रदान करने वाली योजना।",
            "benefits": "बिना गारंटी ₹10,000 की पहली किस्त, ₹20,000 की दूसरी किस्त और ₹50,000 की तीसरी किस्त। समय पर भुगतान पर 7% ब्याज सब्सिडी और डिजिटल लेनदेन पर ₹1,200 तक वार्षिक कैशबैक।",
            "target_beneficiaries": "शहरी और अर्ध-शहरी क्षेत्रों के रेहड़ी-पटरी, ठेला लगाने वाले और फेरीवाले।",
            "eligibility_summary": "शहरी स्थानीय निकाय (ULB) द्वारा जारी वेंडिंग प्रमाण पत्र या पहचान पत्र धारक अथवा सिफारिश पत्र (LoR) प्राप्त स्ट्रीट वेंडर्स।",
            "disbursement_mode": "बैंक शाखा या डिजिटल ऋण मंच के माध्यम से सीधे बैंक खाते में",
        },
        "mr": {
            "name": "पीएम स्वनिधी (पथविक्रेता आत्मनिर्भर निधी)",
            "description": "शहरी भागातील फेरीवाले, हातगाडी चालक आणि पथविक्रेत्यांना विनातारण खेळते भांडवल कर्ज उपलब्ध करून देणारी केंद्र शासनाची योजना.",
            "benefits": "कोणत्याही तारणाशिवाय ₹१०,००० (पहिला हप्ता), ₹२०,००० (दुसरा हप्ता) आणि ₹५०,००० (तिसरा हप्ता) चे सुलभ कर्ज. वेळेवर परतफेडीवर ७% व्याज अनुदान आणि डिजिटल व्यवहारांवर कॅशबॅक.",
            "target_beneficiaries": "शहरी भागातील नोंदणीकृत फेरीवाले, भाजी/फळ विक्रेते, खाद्यपदार्थ स्टॉलधारक.",
            "eligibility_summary": "नगरपालिका/महानगरपालिकेकडून विक्री प्रमाणपत्र (CoV) किंवा ओळखपत्र मिळालेले किंवा शिफारस पत्र (LoR) असलेले पथविक्रेते.",
            "disbursement_mode": "थेट बँक खात्यात कर्ज वितरण",
        },
    },
}


def get_localized_ministry(ministry_name: Optional[str], lang: str = "en") -> str:
    """Returns localized ministry name or original name as fallback."""
    if not ministry_name:
        if lang == "mr":
            return "सक्षम शासकीय मंत्रालय"
        elif lang == "hi":
            return "सक्षम सरकारी मंत्रालय"
        return "Competent Administrative Authority"

    item = MINISTRY_TRANSLATIONS.get(ministry_name)
    if item and lang in item:
        return item[lang]
    return ministry_name


def get_localized_category(category_key: Optional[str], lang: str = "en") -> str:
    """Returns localized category display name."""
    if not category_key:
        return "General Welfare" if lang == "en" else "कल्याणकारी योजना"

    norm_cat = category_key.lower().strip()
    item = CATEGORY_TRANSLATIONS.get(norm_cat)
    if item and lang in item:
        return item[lang]
    return category_key.replace("_", " ").title()


def get_localized_scheme_metadata(scheme_code: str, lang: str = "en") -> Optional[Dict[str, Any]]:
    """Returns verified localized metadata dictionary for a scheme."""
    scheme_entry = SCHEME_LOCALIZED_METADATA.get(scheme_code.upper().strip())
    if not scheme_entry:
        return None
    return scheme_entry.get(lang) or scheme_entry.get("en")
