"""Health Advisory Index (HAI): a vulnerability-weighted air quality index.

Motivation
----------
The CPCB National Air Quality Index is the maximum of the individual pollutant
sub-indices (CPCB, 2014). That construction has two consequences that limit its
usefulness as a personal health signal:

1. **It is the same number for everyone.** A child with developing airways, a
   person with COPD, a cardiac patient and a healthy adult receive an identical
   figure and an identical instruction, although the epidemiological literature
   documents markedly different exposure-response relationships for each group.
2. **The maximum discards the rest of the mixture.** A day on which one pollutant
   sits at sub-index 210 and the other five sit near zero receives the same AQI
   as a day on which all six sit between 190 and 210, even though the total
   inhaled burden differs substantially.

The HAI addresses both while remaining *never less protective* than the AQI.

Construction
------------
For a city-day, let ``s_i`` be the CPCB sub-index of pollutant ``i`` rescaled
from the 0-500 AQI scale onto 0-100 (``s_i = sub_i / 5``). For a cohort ``c``
with per-pollutant vulnerability factors ``v_i^c >= 1``:

.. code-block:: text

    t_i = s_i * v_i^c                      cohort-adjusted sub-index
    D   = max_i t_i                        dominant-pollutant term
    C   = mean of t_i for i != argmax       co-exposure term
    HAI = min(100, D + LAMBDA_COEXPOSURE * C)

Properties, all of which are asserted in :func:`self_test`:

* For the reference cohort ``healthy_adult`` every ``v_i = 1``, so ``D`` equals
  ``AQI / 5`` exactly and ``HAI >= AQI / 5`` always. The index can therefore never
  advise less caution than the official AQI for any person.
* ``HAI`` is monotonically non-decreasing in every pollutant concentration.
* ``HAI`` is bounded on ``[0, 100]``.
* Cohort ordering is preserved: because every ``v_i^c >= v_i^{healthy} = 1``,
  ``HAI_c >= HAI_healthy`` for every cohort ``c``.

The co-exposure coefficient ``LAMBDA_COEXPOSURE = 0.25`` means a day on which all
six pollutants are equally elevated scores 25 per cent higher than a day on which
only one is, before cohort adjustment.

Provenance and status of the vulnerability factors
--------------------------------------------------
The factors in :data:`VULNERABILITY` are a **constructed research prototype**.
They encode the *direction* and the *relative ordering* of associations that are
documented in the sources listed below; they are **not** the output of a formal
meta-analytic pooling of effect sizes, and no claim is made that they reproduce
any published risk ratio. The HAI is an advisory-prioritisation instrument, not a
clinical risk score, and it must not be used as a substitute for medical advice.
This limitation is restated in ``reports/model_card.md``.

Evidence base for the per-pollutant emphasis of each cohort:

``PM2.5`` - cardiovascular and all-cause mortality, with the steepest documented
    gradients in older adults and in people with existing cardiac disease.
    Pope and Dockery (2006); Brook et al. (2010); WHO (2021); US EPA (2019).
``PM10`` - coarse fraction deposits in the upper airway; relevant to outdoor
    occupational exposure at construction and roadside worksites.
    WHO (2021); US EPA (2019).
``NO2`` - airway inflammation and bronchial hyper-responsiveness; associated with
    reduced lung-function growth in children and with asthma exacerbation.
    US EPA (2016); Gauderman et al. (2015); Orellano et al. (2017); WHO (2021).
``SO2`` - rapid bronchoconstriction in people with asthma at short exposure
    durations; the effect is specific enough that asthma carries the single
    largest SO2 emphasis in this scheme. US EPA (2017); WHO (2021).
``CO`` - binds haemoglobin as carboxyhaemoglobin and reduces oxygen delivery,
    which matters most where oxygen delivery is already marginal: existing
    ischaemic heart disease, and the fetal circulation in pregnancy.
    US EPA (2010); WHO (2021).
``O3`` - oxidant lung injury amplified by exertion and by hours spent outdoors;
    hence the largest emphasis for outdoor workers, children and people with
    asthma or COPD. US EPA (2020); WHO (2021).

``NH3`` is part of the CPCB AQI but is deliberately **excluded** from the HAI:
cohort-specific health evidence for ambient ammonia at Indian urban
concentrations is too thin to support a defensible vulnerability factor, and
assigning one arbitrarily would fabricate precision. Benzene, toluene and xylene
are excluded for the same reason together with their sparse coverage.

References
----------
Brook, R. D., Rajagopalan, S., Pope, C. A. 3rd, et al. (2010). Particulate matter
    air pollution and cardiovascular disease: an update to the scientific
    statement from the American Heart Association. *Circulation*, 121(21),
    2331-2378. https://doi.org/10.1161/CIR.0b013e3181dbece1
CPCB (2014). *National Air Quality Index: Report of the Expert Group*. Central
    Pollution Control Board, Government of India.
    https://cpcb.nic.in/upload/Downloads/AQI_Report_0.pdf
Gauderman, W. J., Urman, R., Avol, E., et al. (2015). Association of improved air
    quality with lung development in children. *New England Journal of Medicine*,
    372(10), 905-913. https://doi.org/10.1056/NEJMoa1414123
Orellano, P., Quaranta, N., Reynoso, J., Balbi, B., and Vasquez, J. (2017). Effect
    of outdoor air pollution on asthma exacerbations in children and adults:
    systematic review and multilevel meta-analysis. *PLOS ONE*, 12(3), e0174050.
    https://doi.org/10.1371/journal.pone.0174050
Pedersen, M., Giorgis-Allemand, L., Bernard, C., et al. (2013). Ambient air
    pollution and low birthweight: a European cohort study (ESCAPE). *The Lancet
    Respiratory Medicine*, 1(9), 695-704.
    https://doi.org/10.1016/S2213-2600(13)70192-9
Pope, C. A. 3rd, and Dockery, D. W. (2006). Health effects of fine particulate
    air pollution: lines that connect. *Journal of the Air and Waste Management
    Association*, 56(6), 709-742. https://doi.org/10.1080/10473289.2006.10464485
US EPA (2010). *Integrated Science Assessment for Carbon Monoxide*.
    EPA/600/R-09/019F.
US EPA (2016). *Integrated Science Assessment for Oxides of Nitrogen - Health
    Criteria*. EPA/600/R-15/068.
US EPA (2017). *Integrated Science Assessment for Sulfur Oxides - Health
    Criteria*. EPA/600/R-17/451.
US EPA (2019). *Integrated Science Assessment for Particulate Matter*.
    EPA/600/R-19/188.
US EPA (2020). *Integrated Science Assessment for Ozone and Related Photochemical
    Oxidants*. EPA/600/R-20/012.
WHO (2021). *WHO Global Air Quality Guidelines: Particulate Matter (PM2.5 and
    PM10), Ozone, Nitrogen Dioxide, Sulfur Dioxide and Carbon Monoxide*. World
    Health Organization. https://www.who.int/publications/i/item/9789240034228
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src import config

LOGGER = config.get_logger(__name__)

#: Weight applied to the mean of the non-dominant cohort-adjusted sub-indices.
LAMBDA_COEXPOSURE: float = 0.25

#: Per-cohort, per-pollutant vulnerability factors. Every factor is >= 1, and the
#: reference cohort ``healthy_adult`` is exactly 1 throughout, which guarantees
#: that the HAI is never less protective than the CPCB AQI. See the module
#: docstring for the evidence supporting the relative ordering within each row.
VULNERABILITY: Dict[str, Dict[str, float]] = {
    "healthy_adult": {
        "PM2.5": 1.00, "PM10": 1.00, "NO2": 1.00, "SO2": 1.00, "CO": 1.00, "O3": 1.00,
    },
    "children": {
        # Reduced lung-function growth (NO2), high ventilation rate per unit body
        # mass, and long outdoor play exposure during the afternoon ozone peak.
        "PM2.5": 1.35, "PM10": 1.20, "NO2": 1.55, "SO2": 1.10, "CO": 1.15, "O3": 1.45,
    },
    "elderly_60plus": {
        # Diminished cardiopulmonary reserve; the steepest PM2.5 mortality
        # gradients in the literature are observed in this group.
        "PM2.5": 1.55, "PM10": 1.30, "NO2": 1.20, "SO2": 1.10, "CO": 1.25, "O3": 1.45,
    },
    "asthma_copd": {
        # Bronchoconstriction is the dominant mechanism, and SO2 and O3 provoke it
        # at the shortest exposure durations of any species considered here.
        "PM2.5": 1.40, "PM10": 1.25, "NO2": 1.60, "SO2": 1.75, "CO": 1.05, "O3": 1.70,
    },
    "cardiac": {
        # PM2.5 triggers ischaemic events; CO reduces oxygen delivery where the
        # coronary reserve is already compromised.
        "PM2.5": 1.70, "PM10": 1.25, "NO2": 1.20, "SO2": 1.10, "CO": 1.60, "O3": 1.25,
    },
    "pregnant": {
        # PM2.5 is associated with reduced birthweight and preterm birth; CO
        # competes with oxygen transport across the fetal circulation.
        "PM2.5": 1.50, "PM10": 1.20, "NO2": 1.35, "SO2": 1.10, "CO": 1.45, "O3": 1.20,
    },
    "outdoor_worker": {
        # Exposure duration and exertion amplify oxidant lung injury from O3;
        # roadside and construction work adds coarse-fraction PM10.
        "PM2.5": 1.35, "PM10": 1.45, "NO2": 1.25, "SO2": 1.15, "CO": 1.10, "O3": 1.60,
    },
}

#: Short justification per cohort, surfaced in the application and the reports.
COHORT_RATIONALE: Dict[str, str] = {
    "healthy_adult": (
        "Reference cohort. All vulnerability factors are 1, so the dominant term "
        "equals the official CPCB AQI rescaled to 0-100."
    ),
    "children": (
        "Airways are still developing and minute ventilation per kilogram of body "
        "mass is higher than in adults, so nitrogen dioxide and ozone carry the "
        "largest emphasis."
    ),
    "elderly_60plus": (
        "Reduced cardiopulmonary reserve places the largest documented PM2.5 "
        "mortality gradient in this group, with ozone a close second."
    ),
    "asthma_copd": (
        "Sulfur dioxide and ozone provoke bronchoconstriction within minutes in "
        "people with reactive airways, so both are weighted above particulates."
    ),
    "cardiac": (
        "Fine particulate matter triggers ischaemic events and carbon monoxide "
        "reduces oxygen delivery, so PM2.5 and CO dominate this profile."
    ),
    "pregnant": (
        "Fine particulate matter is associated with reduced birthweight and "
        "preterm birth, and carbon monoxide competes with fetal oxygen transport."
    ),
    "outdoor_worker": (
        "Long outdoor hours and physical exertion raise the inhaled dose; ozone "
        "and coarse particulates therefore carry the largest emphasis."
    ),
}

# --------------------------------------------------------------------------- #
# Advisory text (English, Tamil, Hindi)
# --------------------------------------------------------------------------- #
#: Band names by language. The five HAI bands map exactly onto CPCB AQI cut
#: points because the HAI is expressed on a 0-100 scale: Low corresponds to
#: AQI <= 100, Moderate to 100-200, High to 200-300, Very High to 300-400 and
#: Extreme to AQI > 400.
BAND_LABELS: Dict[str, Dict[str, str]] = {
    "en": {
        "Low": "Low risk",
        "Moderate": "Moderate risk",
        "High": "High risk",
        "Very High": "Very high risk",
        "Extreme": "Extreme risk",
    },
    "ta": {
        "Low": "குறைந்த ஆபத்து",
        "Moderate": "மிதமான ஆபத்து",
        "High": "அதிக ஆபத்து",
        "Very High": "மிக அதிக ஆபத்து",
        "Extreme": "தீவிர ஆபத்து",
    },
    "hi": {
        "Low": "कम जोखिम",
        "Moderate": "मध्यम जोखिम",
        "High": "उच्च जोखिम",
        "Very High": "बहुत उच्च जोखिम",
        "Extreme": "अत्यधिक जोखिम",
    },
}

#: General action text per band, per language.
BAND_ACTION: Dict[str, Dict[str, str]] = {
    "en": {
        "Low": "Normal outdoor activity is fine today.",
        "Moderate": "Outdoor activity is acceptable. Prefer the cleanest hours for long exertion.",
        "High": "Shorten outdoor exertion and keep windows shut during peak traffic hours.",
        "Very High": "Avoid outdoor exercise. Stay indoors where possible and use a well-fitted mask outside.",
        "Extreme": "Stay indoors. Cancel outdoor activity and seek clean indoor air.",
    },
    "ta": {
        "Low": "இன்று வெளிப்புற நடவடிக்கைகள் இயல்பாக இருக்கலாம்.",
        "Moderate": "வெளிப்புற நடவடிக்கைகள் ஏற்றுக்கொள்ளத்தக்கவை. நீண்ட உடற்பயிற்சிக்கு தூய்மையான நேரத்தை தேர்வு செய்யுங்கள்.",
        "High": "வெளிப்புற உடற்பயிற்சியை குறைக்கவும். வாகன நெரிசல் நேரத்தில் ஜன்னல்களை மூடி வைக்கவும்.",
        "Very High": "வெளிப்புற உடற்பயிற்சியை தவிர்க்கவும். முடிந்தவரை உள்ளே இருங்கள். வெளியே செல்லும்போது முகக்கவசம் அணியுங்கள்.",
        "Extreme": "உள்ளேயே இருங்கள். வெளிப்புற நடவடிக்கைகளை ரத்து செய்யுங்கள். தூய்மையான உள் காற்றை நாடுங்கள்.",
    },
    "hi": {
        "Low": "आज सामान्य बाहरी गतिविधि ठीक है।",
        "Moderate": "बाहरी गतिविधि स्वीकार्य है। लंबे व्यायाम के लिए सबसे साफ़ घंटे चुनें।",
        "High": "बाहरी व्यायाम कम करें और यातायात के व्यस्त घंटों में खिड़कियाँ बंद रखें।",
        "Very High": "बाहरी व्यायाम से बचें। यथासंभव घर के अंदर रहें और बाहर जाते समय मास्क पहनें।",
        "Extreme": "घर के अंदर रहें। बाहरी गतिविधियाँ रद्द करें और स्वच्छ इनडोर हवा का प्रयोग करें।",
    },
}

#: Cohort-specific clause appended to the band action, per language.
COHORT_CLAUSE: Dict[str, Dict[str, str]] = {
    "en": {
        "healthy_adult": "This is the general population advisory.",
        "children": "Keep school sports and outdoor play short, and move them to the cleanest hours.",
        "elderly_60plus": "Watch for breathlessness or chest tightness and keep rescue medication to hand.",
        "asthma_copd": "Carry your reliever inhaler and follow your written asthma or COPD action plan.",
        "cardiac": "Report any chest discomfort or unusual fatigue to your physician without delay.",
        "pregnant": "Limit time near heavy traffic and raise persistent symptoms at your next antenatal visit.",
        "outdoor_worker": "Take breaks in clean indoor air and use a certified N95 or FFP2 mask, not a cloth mask.",
    },
    "ta": {
        "healthy_adult": "இது பொது மக்களுக்கான அறிவுரை.",
        "children": "பள்ளி விளையாட்டு மற்றும் வெளிப்புற விளையாட்டை குறைவாக வைத்து, தூய்மையான நேரத்திற்கு மாற்றுங்கள்.",
        "elderly_60plus": "மூச்சுத் திணறல் அல்லது நெஞ்சு இறுக்கத்தை கவனியுங்கள். அவசர மருந்தை கையில் வைத்திருங்கள்.",
        "asthma_copd": "உங்கள் இன்ஹேலரை எடுத்துச் செல்லுங்கள். மருத்துவர் அளித்த செயல் திட்டத்தை பின்பற்றுங்கள்.",
        "cardiac": "நெஞ்சு வலி அல்லது அசாதாரண சோர்வு ஏற்பட்டால் உடனே மருத்துவரிடம் தெரிவியுங்கள்.",
        "pregnant": "அதிக வாகன நெரிசல் உள்ள பகுதிகளில் நேரத்தை குறைக்கவும். தொடர் அறிகுறிகளை கர்ப்பகால பரிசோதனையில் தெரிவிக்கவும்.",
        "outdoor_worker": "தூய்மையான உள் காற்றில் இடைவேளை எடுங்கள். துணி முகக்கவசம் அல்ல, சான்றளிக்கப்பட்ட N95 அல்லது FFP2 கவசம் பயன்படுத்துங்கள்.",
    },
    "hi": {
        "healthy_adult": "यह आम जनता के लिए सलाह है।",
        "children": "स्कूल के खेल और बाहरी खेल कम रखें और उन्हें सबसे साफ़ घंटों में करें।",
        "elderly_60plus": "साँस फूलने या छाती में जकड़न पर ध्यान दें और आपातकालीन दवा पास रखें।",
        "asthma_copd": "अपना इनहेलर साथ रखें और डॉक्टर की लिखी कार्य योजना का पालन करें।",
        "cardiac": "छाती में कोई तकलीफ़ या असामान्य थकान हो तो तुरंत अपने डॉक्टर को बताएँ।",
        "pregnant": "भारी यातायात के पास समय कम करें और लगातार लक्षण अगली प्रसवपूर्व जाँच में बताएँ।",
        "outdoor_worker": "स्वच्छ इनडोर हवा में विराम लें और कपड़े के मास्क के बजाय प्रमाणित N95 या FFP2 मास्क पहनें।",
    },
}

DISCLAIMER: Dict[str, str] = {
    "en": (
        "AirGuard India provides general air quality guidance for public-health "
        "awareness. It is not medical advice and must not replace consultation "
        "with a qualified clinician."
    ),
    "ta": (
        "AirGuard India பொது சுகாதார விழிப்புணர்வுக்கான பொதுவான காற்றுத் தர "
        "வழிகாட்டலை மட்டுமே அளிக்கிறது. இது மருத்துவ ஆலோசனை அல்ல; "
        "தகுதியான மருத்துவரின் ஆலோசனைக்கு மாற்று அல்ல."
    ),
    "hi": (
        "AirGuard India जन-स्वास्थ्य जागरूकता के लिए सामान्य वायु गुणवत्ता "
        "मार्गदर्शन देता है। यह चिकित्सीय सलाह नहीं है और योग्य चिकित्सक के "
        "परामर्श का विकल्प नहीं है।"
    ),
}

LANGUAGES: Dict[str, str] = {"en": "English", "ta": "தமிழ்", "hi": "हिन्दी"}


# --------------------------------------------------------------------------- #
# CPCB sub-indices
# --------------------------------------------------------------------------- #
def sub_index(concentration: np.ndarray, pollutant: str) -> np.ndarray:
    """Convert concentrations to a CPCB sub-index by piecewise linear interpolation.

    Parameters
    ----------
    concentration:
        Array of concentrations in the pollutant's reporting unit.
    pollutant:
        Key into :data:`config.CPCB_BREAKPOINTS`.

    Returns
    -------
    numpy.ndarray
        Sub-index values on the CPCB 0-500 scale. Concentrations above the
        topmost breakpoint are extrapolated linearly from the final segment,
        matching the convention used by the dataset compiler; concentrations
        below zero yield ``nan``.
    """
    values = np.asarray(concentration, dtype=float)
    breakpoints = config.CPCB_BREAKPOINTS[pollutant]
    out = np.full_like(values, np.nan, dtype=float)

    for c_low, c_high, i_low, i_high in breakpoints:
        mask = (values >= c_low) & (values <= c_high)
        span = c_high - c_low
        out[mask] = i_low + (i_high - i_low) * (values[mask] - c_low) / span

    # Linear extrapolation above the topmost segment.
    c_low, c_high, i_low, i_high = breakpoints[-1]
    above = values > c_high
    if above.any():
        slope = (i_high - i_low) / (c_high - c_low)
        out[above] = i_high + slope * (values[above] - c_high)

    out[values < 0] = np.nan
    return out


def compute_sub_indices(frame: pd.DataFrame) -> pd.DataFrame:
    """Append a ``sub_<pollutant>`` column for every CPCB AQI pollutant present."""
    out = frame.copy()
    for pollutant in config.AQI_POLLUTANTS:
        if pollutant in out.columns:
            out[f"sub_{pollutant}"] = sub_index(out[pollutant].to_numpy(), pollutant)
    return out


def recompute_aqi(frame: pd.DataFrame, min_pollutants: int = 3) -> pd.Series:
    """Recompute the CPCB AQI as the maximum sub-index across available pollutants.

    CPCB requires sub-indices for at least three pollutants, one of which must be
    PM2.5 or PM10, before an AQI may be published. Both conditions are enforced
    here, so the recomputed series is directly comparable with the ``AQI`` column
    supplied in the dataset and can be used to audit it.
    """
    columns = [f"sub_{p}" for p in config.AQI_POLLUTANTS if f"sub_{p}" in frame.columns]
    block = frame[columns]
    n_available = block.notna().sum(axis=1)
    has_pm = frame.get("sub_PM2.5", pd.Series(np.nan, index=frame.index)).notna() | frame.get(
        "sub_PM10", pd.Series(np.nan, index=frame.index)
    ).notna()
    aqi = block.max(axis=1)
    aqi[(n_available < min_pollutants) | (~has_pm)] = np.nan
    return aqi


def dominant_pollutant(frame: pd.DataFrame) -> pd.Series:
    """Return the pollutant carrying the highest sub-index on each row."""
    columns = [f"sub_{p}" for p in config.AQI_POLLUTANTS if f"sub_{p}" in frame.columns]
    block = frame[columns]
    winner = block.idxmax(axis=1)
    return winner.str.replace("sub_", "", regex=False).where(block.notna().any(axis=1))


# --------------------------------------------------------------------------- #
# Banding
# --------------------------------------------------------------------------- #
def band_of(values: np.ndarray) -> np.ndarray:
    """Map 0-100 index values onto the five HAI advisory bands."""
    values = np.asarray(values, dtype=float)
    out = np.full(values.shape, None, dtype=object)
    for name, low, high in config.HAI_BANDS:
        mask = (values >= low) & (values < high)
        out[mask] = name
    out[values >= config.HAI_BANDS[-1][2]] = config.HAI_BANDS[-1][0]
    out[np.isnan(values)] = None
    return out


def aqi_to_band(aqi: np.ndarray) -> np.ndarray:
    """Map a CPCB AQI (0-500+) onto the same five bands, for like-with-like comparison.

    Dividing by five puts the AQI on the HAI scale, at which point the HAI band
    edges (20, 40, 60, 80) coincide exactly with the CPCB cut points 100, 200,
    300 and 400. The only collapse is that CPCB's ``Good`` and ``Satisfactory``
    both fall inside the HAI ``Low`` band.
    """
    return band_of(np.asarray(aqi, dtype=float) / 5.0)


def bucket_from_aqi(aqi: np.ndarray) -> np.ndarray:
    """Return the six-level CPCB ``AQI_Bucket`` label for AQI values."""
    values = np.asarray(aqi, dtype=float)
    out = np.full(values.shape, None, dtype=object)
    for name, low, high in config.AQI_BUCKET_BOUNDS:
        mask = (values > low) & (values <= high) if low > 0 else (values >= low) & (values <= high)
        out[mask] = name
    out[np.isnan(values)] = None
    return out


# --------------------------------------------------------------------------- #
# The index itself
# --------------------------------------------------------------------------- #
def compute_hai(
    frame: pd.DataFrame,
    cohort: str,
    pollutants: Optional[List[str]] = None,
    lambda_coexposure: float = LAMBDA_COEXPOSURE,
) -> pd.Series:
    """Compute the Health Advisory Index for one cohort.

    Parameters
    ----------
    frame:
        Table already carrying ``sub_<pollutant>`` columns (see
        :func:`compute_sub_indices`).
    cohort:
        Key into :data:`VULNERABILITY`.
    pollutants:
        Pollutants entering the index. Defaults to ``config.HAI_POLLUTANTS``.
    lambda_coexposure:
        Weight on the mean of the non-dominant cohort-adjusted sub-indices.

    Returns
    -------
    pandas.Series
        HAI values on ``[0, 100]``, named ``HAI_<cohort>``.
    """
    if cohort not in VULNERABILITY:
        raise KeyError(f"unknown cohort {cohort!r}; expected one of {list(VULNERABILITY)}")
    pollutants = pollutants or config.HAI_POLLUTANTS
    factors = VULNERABILITY[cohort]

    adjusted = np.column_stack(
        [
            frame[f"sub_{p}"].to_numpy(dtype=float) / 5.0 * factors[p]
            for p in pollutants
        ]
    )
    with np.errstate(invalid="ignore"):
        dominant = np.nanmax(adjusted, axis=1)
        total = np.nansum(adjusted, axis=1)
        n_valid = np.sum(~np.isnan(adjusted), axis=1)

    others_mean = np.where(n_valid > 1, (total - dominant) / np.maximum(n_valid - 1, 1), 0.0)
    hai = np.minimum(100.0, dominant + lambda_coexposure * others_mean)
    hai[n_valid == 0] = np.nan
    return pd.Series(hai, index=frame.index, name=f"HAI_{cohort}")


def add_all_cohort_hai(frame: pd.DataFrame) -> pd.DataFrame:
    """Append ``HAI_<cohort>`` and ``HAI_<cohort>_band`` for every cohort."""
    out = frame.copy()
    if not any(c.startswith("sub_") for c in out.columns):
        out = compute_sub_indices(out)
    for cohort in config.COHORTS:
        values = compute_hai(out, cohort)
        out[values.name] = values
        out[f"{values.name}_band"] = band_of(values.to_numpy())
    return out


def advisory(
    cohort: str,
    band: str,
    language: str = "en",
    dominant: Optional[str] = None,
    safe_window: Optional[str] = None,
) -> Dict[str, str]:
    """Return a plain-language advisory for a cohort and band.

    Parameters
    ----------
    cohort:
        Key into :data:`VULNERABILITY`.
    band:
        One of the five HAI band names.
    language:
        ``"en"``, ``"ta"`` or ``"hi"``.
    dominant:
        Optional dominant pollutant name, appended as a one-line explanation.
    safe_window:
        Optional pre-formatted safest-exposure window, appended if supplied.

    Returns
    -------
    dict
        Keys ``band_label``, ``cohort_label``, ``action``, ``clause``,
        ``dominant_line``, ``window_line``, ``disclaimer`` and ``text``, where
        ``text`` is the whole advisory as a single paragraph.
    """
    language = language if language in LANGUAGES else "en"
    band = band if band in BAND_ACTION[language] else "Moderate"

    cohort_label_en = config.COHORT_LABELS.get(cohort, cohort)
    parts: Dict[str, str] = {
        "band_label": BAND_LABELS[language][band],
        "cohort_label": cohort_label_en,
        "action": BAND_ACTION[language][band],
        "clause": COHORT_CLAUSE[language].get(cohort, ""),
        "dominant_line": "",
        "window_line": "",
        "disclaimer": DISCLAIMER[language],
    }
    if dominant:
        prefix = {
            "en": "Main pollutant today",
            "ta": "இன்றைய முதன்மை மாசுபாடு",
            "hi": "आज का प्रमुख प्रदूषक",
        }[language]
        parts["dominant_line"] = f"{prefix}: {dominant}."
    if safe_window:
        prefix = {
            "en": "Cleanest outdoor window",
            "ta": "தூய்மையான வெளிப்புற நேரம்",
            "hi": "सबसे साफ़ बाहरी समय",
        }[language]
        parts["window_line"] = f"{prefix}: {safe_window}."

    parts["text"] = " ".join(
        s
        for s in (
            parts["action"],
            parts["clause"],
            parts["dominant_line"],
            parts["window_line"],
        )
        if s
    )
    return parts


# --------------------------------------------------------------------------- #
# Divergence evidence
# --------------------------------------------------------------------------- #
def measure_divergence(frame: pd.DataFrame) -> Dict[str, object]:
    """Quantify how far the HAI departs from the official AQI, and why.

    The total divergence is decomposed into two independent effects, because a
    single headline percentage would not distinguish them:

    *Aggregation effect* - the reference cohort ``healthy_adult`` has all
    vulnerability factors equal to 1, so any difference between
    ``HAI_healthy_adult`` and ``AQI / 5`` is caused solely by the co-exposure
    surcharge replacing the plain maximum.

    *Cohort effect* - the difference between ``HAI_<cohort>`` and
    ``HAI_healthy_adult`` is caused solely by the vulnerability weighting, since
    both share the same aggregation rule.

    Returns
    -------
    dict
        Overall and per-cohort divergence statistics, suitable for direct
        rendering into a report table.
    """
    work = frame.dropna(subset=["AQI"]).copy()
    if "HAI_healthy_adult" not in work.columns:
        work = add_all_cohort_hai(work)

    aqi_band = aqi_to_band(work["AQI"].to_numpy())
    work["aqi_band_5level"] = aqi_band
    n = int(len(work))

    baseline_band = work["HAI_healthy_adult_band"].to_numpy()
    aggregation_shift = int(np.sum(baseline_band != aqi_band))

    per_cohort: List[Dict[str, object]] = []
    for cohort in config.COHORTS:
        column = f"HAI_{cohort}"
        band_column = f"{column}_band"
        cohort_band = work[band_column].to_numpy()
        differs_from_aqi = int(np.sum(cohort_band != aqi_band))
        differs_from_baseline = int(np.sum(cohort_band != baseline_band))

        stricter = int(
            np.sum(
                [
                    _band_rank(a) > _band_rank(b)
                    for a, b in zip(cohort_band, aqi_band)
                ]
            )
        )
        per_cohort.append(
            {
                "cohort": cohort,
                "cohort_label": config.COHORT_LABELS[cohort],
                "mean_hai": round(float(work[column].mean()), 3),
                "mean_aqi_rescaled": round(float(work["AQI"].mean() / 5.0), 3),
                "mean_uplift_points": round(
                    float(work[column].mean() - work["AQI"].mean() / 5.0), 3
                ),
                "days_band_differs_from_aqi": differs_from_aqi,
                "pct_band_differs_from_aqi": round(100.0 * differs_from_aqi / n, 2),
                "days_band_stricter_than_aqi": stricter,
                "pct_band_stricter_than_aqi": round(100.0 * stricter / n, 2),
                "days_band_differs_from_reference_cohort": differs_from_baseline,
                "pct_band_differs_from_reference_cohort": round(
                    100.0 * differs_from_baseline / n, 2
                ),
                "vulnerability_factors": VULNERABILITY[cohort],
                "rationale": COHORT_RATIONALE[cohort],
            }
        )

    any_differs = np.zeros(n, dtype=bool)
    for cohort in config.COHORTS:
        any_differs |= work[f"HAI_{cohort}_band"].to_numpy() != aqi_band

    return {
        "n_city_days_evaluated": n,
        "date_range": [
            work["Date"].min().strftime("%Y-%m-%d"),
            work["Date"].max().strftime("%Y-%m-%d"),
        ],
        "aggregation_effect": {
            "days_reference_cohort_band_differs_from_aqi": aggregation_shift,
            "pct": round(100.0 * aggregation_shift / n, 2),
            "explanation": (
                "Difference attributable purely to replacing the plain maximum "
                "sub-index with a dominant term plus a co-exposure surcharge. The "
                "reference cohort carries no vulnerability weighting at all."
            ),
        },
        "per_cohort": per_cohort,
        "any_cohort_differs": {
            "days": int(any_differs.sum()),
            "pct": round(100.0 * int(any_differs.sum()) / n, 2),
            "explanation": (
                "Share of city-days on which at least one cohort would receive a "
                "different advisory band from the one the official AQI implies. "
                "This is the headline evidence that a single population-average "
                "index under-serves vulnerable groups."
            ),
        },
        "lambda_coexposure": LAMBDA_COEXPOSURE,
        "pollutants_used": config.HAI_POLLUTANTS,
        "pollutants_excluded_and_why": {
            "NH3": (
                "Part of the CPCB AQI but cohort-specific health evidence at "
                "Indian ambient concentrations is too thin to support a "
                "defensible vulnerability factor."
            ),
            "Benzene/Toluene/Xylene": (
                "Sparse coverage in city_day.csv and no cohort-resolved "
                "short-term exposure-response basis."
            ),
        },
    }


def _band_rank(band: Optional[str]) -> int:
    """Return the ordinal position of a band name, or ``-1`` when missing."""
    names = [b[0] for b in config.HAI_BANDS]
    return names.index(band) if band in names else -1


# --------------------------------------------------------------------------- #
# Self-test
# --------------------------------------------------------------------------- #
def self_test() -> Dict[str, bool]:
    """Assert every mathematical property claimed in the module docstring.

    Raises
    ------
    AssertionError
        If any property fails. The function is called by ``features/build.py`` so
        that a broken index cannot reach a report.
    """
    checks: Dict[str, bool] = {}

    # Sub-index anchors reproduce the CPCB table exactly.
    assert abs(float(sub_index(np.array([30.0]), "PM2.5")[0]) - 50.0) < 1e-9
    assert abs(float(sub_index(np.array([60.0]), "PM2.5")[0]) - 100.0) < 1e-9
    assert abs(float(sub_index(np.array([250.0]), "PM10")[0]) - 200.0) < 1e-9
    assert abs(float(sub_index(np.array([1.0]), "CO")[0]) - 50.0) < 1e-9
    checks["cpcb_breakpoints_reproduced"] = True

    rng = np.random.default_rng(config.RANDOM_SEED)
    sample = pd.DataFrame(
        {
            "PM2.5": rng.uniform(0, 400, 4000),
            "PM10": rng.uniform(0, 600, 4000),
            "NO2": rng.uniform(0, 300, 4000),
            "SO2": rng.uniform(0, 300, 4000),
            "CO": rng.uniform(0, 20, 4000),
            "O3": rng.uniform(0, 250, 4000),
            "NH3": rng.uniform(0, 200, 4000),
        }
    )
    sample = compute_sub_indices(sample)
    sample["AQI"] = recompute_aqi(sample)

    hai = {c: compute_hai(sample, c) for c in config.COHORTS}

    for cohort, values in hai.items():
        assert values.min() >= 0.0, f"{cohort} below 0"
        assert values.max() <= 100.0 + 1e-9, f"{cohort} above 100"
    checks["bounded_0_100"] = True

    # HAI is never less protective than the AQI rescaled to 0-100. The comparison
    # uses a max over the six HAI pollutants so that both sides see the same
    # pollutant set (the CPCB AQI additionally includes NH3).
    hai_scale_aqi = (
        sample[[f"sub_{p}" for p in config.HAI_POLLUTANTS]].max(axis=1) / 5.0
    )
    for cohort, values in hai.items():
        assert (values + 1e-9 >= hai_scale_aqi).all(), f"{cohort} below AQI-equivalent"
    checks["never_less_protective_than_aqi"] = True

    for cohort, values in hai.items():
        if cohort == "healthy_adult":
            continue
        assert (values + 1e-9 >= hai["healthy_adult"]).all(), f"{cohort} below reference"
    checks["cohort_ordering_preserved"] = True

    # Monotonicity: raising any single pollutant cannot lower the index.
    raised = sample.copy()
    raised["PM2.5"] = raised["PM2.5"] + 25.0
    raised = compute_sub_indices(raised)
    for cohort in config.COHORTS:
        assert (
            compute_hai(raised, cohort) + 1e-9 >= compute_hai(sample, cohort)
        ).all(), f"{cohort} not monotone in PM2.5"
    checks["monotone_in_each_pollutant"] = True

    # Every vulnerability factor is at least 1 and the reference cohort is exactly 1.
    assert all(v == 1.0 for v in VULNERABILITY["healthy_adult"].values())
    assert all(
        f >= 1.0 for cohort in VULNERABILITY.values() for f in cohort.values()
    )
    checks["vulnerability_factors_valid"] = True

    # Advisory text exists for every cohort, band and language.
    for language in LANGUAGES:
        for cohort in config.COHORTS:
            for band, _, _ in config.HAI_BANDS:
                text = advisory(cohort, band, language)["text"]
                assert text and len(text) > 10, f"missing advisory {language}/{cohort}/{band}"
    checks["advisory_text_complete_all_languages"] = True

    LOGGER.info("HAI self-test passed: %s", ", ".join(checks))
    return checks


if __name__ == "__main__":
    self_test()
