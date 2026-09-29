"""Static translation dictionary for the application interface.

Advisory text itself lives in :mod:`src.features.hai`, beside the index that
produces it, so that the health message and the number it describes cannot drift
apart. This module covers the surrounding interface: labels, headings and the
fixed explanatory strings.

No translation service is used. The dictionary is static, which keeps the
application free to run, free of network dependencies at request time, and
deterministic.
"""

from __future__ import annotations

from typing import Dict

from src.features.hai import BAND_ACTION, BAND_LABELS, COHORT_CLAUSE, DISCLAIMER, LANGUAGES

__all__ = [
    "LANGUAGES",
    "BAND_LABELS",
    "BAND_ACTION",
    "COHORT_CLAUSE",
    "DISCLAIMER",
    "UI",
    "translate",
    "cohort_label",
]

#: Interface strings keyed by language then by token.
UI: Dict[str, Dict[str, str]] = {
    "en": {
        "city": "City",
        "cohort": "Who is this for?",
        "date": "Date",
        "language": "Language",
        "forecast_heading": "Next-day forecast",
        "predicted_aqi": "Predicted AQI tomorrow",
        "predicted_band": "Predicted band",
        "confidence": "Model confidence",
        "hai": "Health Advisory Index",
        "band": "Advisory band",
        "dominant": "Main pollutant",
        "safe_window": "Cleanest outdoor window",
        "advisory": "What to do",
        "observed_today": "Measured today",
        "history": "Recent history",
        "disclaimer": "Important",
        "actual": "Actual outcome (from the historical record)",
        "no_data": "No data available for that selection.",
        "what_if": "What if concentrations were lower?",
    },
    "ta": {
        "city": "நகரம்",
        "cohort": "இது யாருக்கு?",
        "date": "தேதி",
        "language": "மொழி",
        "forecast_heading": "நாளைய முன்னறிவிப்பு",
        "predicted_aqi": "நாளைய கணிக்கப்பட்ட AQI",
        "predicted_band": "கணிக்கப்பட்ட நிலை",
        "confidence": "மாதிரியின் நம்பகத்தன்மை",
        "hai": "சுகாதார ஆலோசனை குறியீடு",
        "band": "ஆலோசனை நிலை",
        "dominant": "முதன்மை மாசுபாடு",
        "safe_window": "தூய்மையான வெளிப்புற நேரம்",
        "advisory": "என்ன செய்ய வேண்டும்",
        "observed_today": "இன்று அளவிடப்பட்டது",
        "history": "சமீபத்திய வரலாறு",
        "disclaimer": "முக்கியம்",
        "actual": "உண்மையான முடிவு (வரலாற்று பதிவிலிருந்து)",
        "no_data": "இந்த தேர்வுக்கு தரவு இல்லை.",
        "what_if": "மாசு குறைந்தால் என்ன ஆகும்?",
    },
    "hi": {
        "city": "शहर",
        "cohort": "यह किसके लिए है?",
        "date": "तारीख़",
        "language": "भाषा",
        "forecast_heading": "कल का पूर्वानुमान",
        "predicted_aqi": "कल का अनुमानित AQI",
        "predicted_band": "अनुमानित श्रेणी",
        "confidence": "मॉडल का विश्वास",
        "hai": "स्वास्थ्य सलाह सूचकांक",
        "band": "सलाह श्रेणी",
        "dominant": "प्रमुख प्रदूषक",
        "safe_window": "सबसे साफ़ बाहरी समय",
        "advisory": "क्या करें",
        "observed_today": "आज मापा गया",
        "history": "हाल का इतिहास",
        "disclaimer": "महत्वपूर्ण",
        "actual": "वास्तविक परिणाम (ऐतिहासिक रिकॉर्ड से)",
        "no_data": "इस चयन के लिए कोई डेटा उपलब्ध नहीं है।",
        "what_if": "यदि प्रदूषण कम होता तो क्या होता?",
    },
}

#: Cohort names by language.
COHORT_NAMES: Dict[str, Dict[str, str]] = {
    "en": {
        "healthy_adult": "Healthy adult",
        "children": "Children (under 14)",
        "elderly_60plus": "Elderly (60+)",
        "asthma_copd": "Asthma / COPD",
        "cardiac": "Cardiac patients",
        "pregnant": "Pregnant women",
        "outdoor_worker": "Outdoor workers",
    },
    "ta": {
        "healthy_adult": "ஆரோக்கியமான பெரியவர்",
        "children": "குழந்தைகள் (14 வயதுக்கு கீழ்)",
        "elderly_60plus": "முதியவர்கள் (60+)",
        "asthma_copd": "ஆஸ்துமா / COPD",
        "cardiac": "இதய நோயாளிகள்",
        "pregnant": "கர்ப்பிணிப் பெண்கள்",
        "outdoor_worker": "வெளிப்புறத் தொழிலாளர்கள்",
    },
    "hi": {
        "healthy_adult": "स्वस्थ वयस्क",
        "children": "बच्चे (14 वर्ष से कम)",
        "elderly_60plus": "बुज़ुर्ग (60+)",
        "asthma_copd": "अस्थमा / सीओपीडी",
        "cardiac": "हृदय रोगी",
        "pregnant": "गर्भवती महिलाएँ",
        "outdoor_worker": "बाहरी कामगार",
    },
}


def translate(token: str, language: str = "en") -> str:
    """Return an interface string, falling back to English then to the token."""
    return UI.get(language, UI["en"]).get(token, UI["en"].get(token, token))


def cohort_label(cohort: str, language: str = "en") -> str:
    """Return a cohort name in the requested language."""
    return COHORT_NAMES.get(language, COHORT_NAMES["en"]).get(
        cohort, COHORT_NAMES["en"].get(cohort, cohort)
    )
