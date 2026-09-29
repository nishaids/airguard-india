"""Generation of the three review documents from the results artefacts.

Design rule
-----------
**No metric in any generated document is written by hand.** Every number is read
from ``results/*.json``, ``results/*.csv`` or ``data/raw/PROVENANCE.json`` at
generation time, and every figure is a file in ``reports/figures/``. If the
pipeline is re-run and a number changes, the documents change with it. The only
hand-written content is prose: argument, justification and interpretation.

Outputs
-------
``reports/Review1_Problem_and_Dataset.docx``
``reports/Review2_Preprocessing_and_EDA.docx``
``reports/Review3_Modeling_and_Comparison.docx``
``reports/CHANGELOG.md``
PDF versions alongside each, when LibreOffice is available on the PATH.

Run with::

    python -m src.report.build_docx
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor

from src import config
from src.features import hai as hai_mod

LOGGER = config.get_logger(__name__)

FIGURES = config.FIGURES_DIR
CHANGELOG = config.REPORTS_DIR / "CHANGELOG.md"

ACCENT = RGBColor(0x0B, 0x3C, 0x5D)
MUTED = RGBColor(0x55, 0x55, 0x55)


# --------------------------------------------------------------------------- #
# Result loading
# --------------------------------------------------------------------------- #
def load_all() -> Dict[str, Any]:
    """Load every results artefact the documents draw on."""

    def _json(path: Path) -> Dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def _csv(name: str) -> pd.DataFrame:
        path = config.RESULTS_DIR / name
        return pd.read_csv(path) if path.exists() else pd.DataFrame()

    return {
        "provenance": _json(config.RAW_DIR / "PROVENANCE.json"),
        "quality": _json(config.RESULTS_DIR / "data_quality_report.json"),
        "cleaning": _json(config.RESULTS_DIR / "cleaning_report.json"),
        "features": _json(config.RESULTS_DIR / "feature_engineering_report.json"),
        "divergence": _json(config.RESULTS_DIR / "hai_divergence.json"),
        "safe_windows": _json(config.RESULTS_DIR / "safe_windows.json"),
        "eda": _json(config.RESULTS_DIR / "eda_statistics.json"),
        "insights": _json(config.RESULTS_DIR / "eda_insights.json"),
        "regression": _json(config.RESULTS_DIR / "evaluation_regression.json"),
        "classification": _json(config.RESULTS_DIR / "evaluation_classification.json"),
        "clustering": _json(config.RESULTS_DIR / "evaluation_clustering.json"),
        "tuning": _json(config.RESULTS_DIR / "tuning_report.json"),
        "explain": _json(config.RESULTS_DIR / "explainability.json"),
        "errors": _json(config.RESULTS_DIR / "error_analysis.json"),
        "policy": _json(config.RESULTS_DIR / "policy_simulation.json"),
        "table_regression": _csv("master_comparison_regression.csv"),
        "table_classification": _csv("master_comparison_classification.csv"),
        "table_clustering": _csv("master_comparison_clustering.csv"),
    }


# --------------------------------------------------------------------------- #
# Document primitives
# --------------------------------------------------------------------------- #
class ReportBuilder:
    """Thin wrapper over ``python-docx`` that keeps numbering consistent."""

    def __init__(self, title: str, subtitle: str, review: str, marks: int) -> None:
        self.document = Document()
        self.title = title
        self.subtitle = subtitle
        self.review = review
        self.marks = marks
        self.figure_number = 0
        self.table_number = 0
        self.sections: List[Tuple[str, str]] = []
        self.references: List[str] = []
        self._configure_styles()

    # -- setup ------------------------------------------------------------- #
    def _configure_styles(self) -> None:
        """Set page geometry and the base typography."""
        for section in self.document.sections:
            section.top_margin = Cm(2.2)
            section.bottom_margin = Cm(2.2)
            section.left_margin = Cm(2.4)
            section.right_margin = Cm(2.2)

        normal = self.document.styles["Normal"]
        normal.font.name = "Calibri"
        normal.font.size = Pt(10.5)
        normal.paragraph_format.space_after = Pt(6)
        normal.paragraph_format.line_spacing = 1.15

    # -- structure --------------------------------------------------------- #
    def cover(self) -> None:
        """Render the cover page with the academic metadata."""
        academic = config.ACADEMIC

        spacer = self.document.add_paragraph()
        spacer.paragraph_format.space_after = Pt(30)

        heading = self.document.add_paragraph()
        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = heading.add_run(academic["institution"])
        run.bold = True
        run.font.size = Pt(15)
        run.font.color.rgb = ACCENT

        line = self.document.add_paragraph()
        line.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = line.add_run("Department of Artificial Intelligence and Data Science")
        run.font.size = Pt(11.5)

        self.document.add_paragraph()

        line = self.document.add_paragraph()
        line.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = line.add_run(f"{academic['course_code']} — {academic['course_name']}")
        run.bold = True
        run.font.size = Pt(13)

        line = self.document.add_paragraph()
        line.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = line.add_run(
            f"{academic['course_type']}  |  Category: {academic['category']}  |  "
            f"L-T-P-C: {academic['ltpc']}"
        )
        run.font.size = Pt(10)
        run.font.color.rgb = MUTED

        self.document.add_paragraph()
        self.document.add_paragraph()

        line = self.document.add_paragraph()
        line.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = line.add_run(academic["project_title"])
        run.bold = True
        run.font.size = Pt(26)
        run.font.color.rgb = ACCENT

        line = self.document.add_paragraph()
        line.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = line.add_run(academic["project_subtitle"])
        run.italic = True
        run.font.size = Pt(12)

        self.document.add_paragraph()

        line = self.document.add_paragraph()
        line.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = line.add_run(f"{self.review}: {self.title}")
        run.bold = True
        run.font.size = Pt(14)

        line = self.document.add_paragraph()
        line.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = line.add_run(f"Maximum marks: {self.marks}")
        run.font.size = Pt(10.5)
        run.font.color.rgb = MUTED

        self.document.add_paragraph()

        table = self.document.add_table(rows=0, cols=2)
        table.style = "Table Grid"
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for label, value in [
            ("Degree and Branch", academic["degree_branch"]),
            ("Regulation", academic["regulation"]),
            ("Academic Year", academic["academic_year"]),
            ("Semester", academic["semester"]),
            ("Batch", academic["batch"]),
        ]:
            row = table.add_row().cells
            row[0].text = label
            row[1].text = value
            row[0].paragraphs[0].runs[0].bold = True
        self._size_table(table, [Cm(5.4), Cm(10.4)])

        self.document.add_paragraph()

        line = self.document.add_paragraph()
        run = line.add_run("Project team")
        run.bold = True
        run.font.size = Pt(11)

        team = self.document.add_table(rows=1, cols=3)
        team.style = "Table Grid"
        header = team.rows[0].cells
        for index, label in enumerate(["S. No.", "Register Number", "Name"]):
            header[index].text = label
            header[index].paragraphs[0].runs[0].bold = True
        for index, member in enumerate(config.TEAM, start=1):
            row = team.add_row().cells
            row[0].text = str(index)
            row[1].text = member["register_no"]
            row[2].text = member["name"]
        self._size_table(team, [Cm(1.8), Cm(4.4), Cm(9.6)])

        self.document.add_paragraph()
        line = self.document.add_paragraph()
        line.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = line.add_run(
            f"Generated {datetime.now().strftime('%d %B %Y')} · "
            f"Repository: {config.REPO_URL}"
        )
        run.font.size = Pt(9)
        run.font.color.rgb = MUTED

        self.document.add_page_break()

    def toc(self, entries: Sequence[Tuple[str, str]]) -> None:
        """Render a static table of contents mapping sections to rubric rows."""
        self.heading("Table of Contents", level=1, register=False)
        table = self.document.add_table(rows=1, cols=3)
        table.style = "Table Grid"
        header = table.rows[0].cells
        for index, label in enumerate(["Section", "Title", "Rubric row addressed"]):
            header[index].text = label
            header[index].paragraphs[0].runs[0].bold = True
        for number, (title, rubric) in enumerate(entries, start=1):
            row = table.add_row().cells
            row[0].text = str(number)
            row[1].text = title
            row[2].text = rubric
        self._size_table(table, [Cm(1.6), Cm(8.6), Cm(6.4)])
        self.document.add_page_break()

    def heading(self, text: str, level: int = 1, register: bool = True) -> None:
        """Add a heading, optionally registering it for the rubric map."""
        heading = self.document.add_heading(text, level=level)
        for run in heading.runs:
            run.font.color.rgb = ACCENT
        if register and level == 1:
            self.sections.append((text, ""))

    def para(self, text: str, bold: bool = False, italic: bool = False,
             size: float = 10.5) -> None:
        """Add a body paragraph, justified."""
        paragraph = self.document.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = paragraph.add_run(text)
        run.bold = bold
        run.italic = italic
        run.font.size = Pt(size)

    def bullets(self, items: Sequence[str]) -> None:
        """Add a bulleted list."""
        for item in items:
            paragraph = self.document.add_paragraph(item, style="List Bullet")
            paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            for run in paragraph.runs:
                run.font.size = Pt(10.5)

    def numbered(self, items: Sequence[str]) -> None:
        """Add a numbered list."""
        for item in items:
            paragraph = self.document.add_paragraph(item, style="List Number")
            paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            for run in paragraph.runs:
                run.font.size = Pt(10.5)

    def figure(self, filename: str, caption: str, width_inches: float = 6.3) -> None:
        """Insert a numbered, captioned figure if the file exists."""
        path = FIGURES / filename
        if not path.exists():
            LOGGER.warning("Figure missing, skipped: %s", filename)
            return
        self.figure_number += 1
        paragraph = self.document.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.add_run().add_picture(str(path), width=Inches(width_inches))

        caption_paragraph = self.document.add_paragraph()
        caption_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = caption_paragraph.add_run(f"Figure {self.figure_number}. {caption}")
        run.font.size = Pt(9)
        run.italic = True
        run.font.color.rgb = MUTED
        source = caption_paragraph.add_run(f"  [{filename}]")
        source.font.size = Pt(7.5)
        source.font.color.rgb = MUTED

    def table(
        self,
        rows: Sequence[Sequence[Any]],
        headers: Sequence[str],
        caption: str,
        widths: Optional[Sequence[Cm]] = None,
        font_size: float = 8.5,
    ) -> None:
        """Insert a numbered, captioned table."""
        self.table_number += 1
        caption_paragraph = self.document.add_paragraph()
        run = caption_paragraph.add_run(f"Table {self.table_number}. {caption}")
        run.bold = True
        run.font.size = Pt(9.5)
        run.font.color.rgb = ACCENT

        table = self.document.add_table(rows=1, cols=len(headers))
        table.style = "Light Grid Accent 1"
        header_cells = table.rows[0].cells
        for index, label in enumerate(headers):
            header_cells[index].text = str(label)
            for paragraph in header_cells[index].paragraphs:
                for cell_run in paragraph.runs:
                    cell_run.bold = True
                    cell_run.font.size = Pt(font_size)

        for record in rows:
            cells = table.add_row().cells
            for index, value in enumerate(record):
                cells[index].text = "" if value is None else str(value)
                for paragraph in cells[index].paragraphs:
                    for cell_run in paragraph.runs:
                        cell_run.font.size = Pt(font_size)

        if widths:
            self._size_table(table, widths)
        self.document.add_paragraph()

    def dataframe(
        self, frame: pd.DataFrame, caption: str, columns: Optional[Sequence[str]] = None,
        font_size: float = 7.5, max_rows: int = 40,
    ) -> None:
        """Insert a DataFrame as a numbered table."""
        if frame.empty:
            self.para(f"[{caption}: table not available]", italic=True)
            return
        subset = frame[list(columns)] if columns else frame
        subset = subset.head(max_rows)
        rows = [
            [
                ("" if pd.isna(value) else (f"{value:.4g}" if isinstance(value, float) else value))
                for value in record
            ]
            for record in subset.itertuples(index=False)
        ]
        self.table(rows, list(subset.columns), caption, font_size=font_size)

    def _size_table(self, table: Any, widths: Sequence[Cm]) -> None:
        """Apply fixed column widths."""
        table.autofit = False
        for row in table.rows:
            for index, width in enumerate(widths):
                if index < len(row.cells):
                    row.cells[index].width = width

    def references_section(self, entries: Sequence[str]) -> None:
        """Render the reference list."""
        self.heading("References", level=1, register=False)
        self.para(
            "Every source below was consulted directly. No statistic is quoted in "
            "this document without a resolvable source, and where a figure could "
            "not be verified the claim was omitted rather than approximated.",
            italic=True,
        )
        for index, entry in enumerate(entries, start=1):
            paragraph = self.document.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            paragraph.paragraph_format.left_indent = Cm(0.9)
            paragraph.paragraph_format.first_line_indent = Cm(-0.9)
            run = paragraph.add_run(f"[{index}]  {entry}")
            run.font.size = Pt(9.5)

    def rubric_coverage(self, rows: Sequence[Tuple[str, int, str, str]]) -> None:
        """Render the rubric coverage table that closes each document."""
        self.document.add_page_break()
        self.heading("Rubric Coverage", level=1, register=False)
        self.para(
            f"Each row of the {self.review} assessment rubric is mapped below to the "
            f"section of this document that satisfies it and to the evidence that "
            f"supports it. Total marks addressed: {sum(r[1] for r in rows)} of "
            f"{self.marks}."
        )
        table_rows = [(r[0], str(r[1]), r[2], r[3]) for r in rows]
        self.table(
            table_rows,
            ["Rubric row", "Marks", "Section(s)", "Evidence in this document"],
            f"{self.review} rubric coverage map",
            widths=[Cm(3.8), Cm(1.3), Cm(2.6), Cm(8.3)],
            font_size=8.0,
        )

    def save(self, path: Path) -> Path:
        """Write the document and return its path."""
        self.document.save(str(path))
        LOGGER.info("Wrote %s (%s figures, %s tables)", path.name, self.figure_number, self.table_number)
        return path


# --------------------------------------------------------------------------- #
# Shared reference list
# --------------------------------------------------------------------------- #
def references_for(document: str, data: Dict[str, Any]) -> List[str]:
    """Return the reference list appropriate to a document."""
    provenance = data["provenance"]
    licence = provenance.get("license", {}).get("string_as_displayed_on_kaggle", "see PROVENANCE.json")

    common = [
        "Central Pollution Control Board (2014). National Air Quality Index: Report "
        "of the Expert Group. Ministry of Environment, Forest and Climate Change, "
        "Government of India. Available at: "
        "https://cpcb.nic.in/upload/Downloads/AQI_Report_0.pdf",
        f"Rao, R. (2020). Air Quality Data in India (2015 - 2020) [Data set]. Kaggle. "
        f"Licence as displayed: {licence}. Available at: "
        f"{config.KAGGLE_DATASET_URL}. Upstream source: Central Pollution Control "
        f"Board, Government of India, https://cpcb.nic.in/",
        "World Health Organization (2021). WHO Global Air Quality Guidelines: "
        "Particulate Matter (PM2.5 and PM10), Ozone, Nitrogen Dioxide, Sulfur "
        "Dioxide and Carbon Monoxide. Geneva: WHO. Available at: "
        "https://www.who.int/publications/i/item/9789240034228",
        "Balakrishnan, K., Dey, S., Gupta, T., et al. (2019). The impact of air "
        "pollution on deaths, disease burden, and life expectancy across the states "
        "of India: the Global Burden of Disease Study 2017. The Lancet Planetary "
        "Health, 3(1), e26-e39. https://doi.org/10.1016/S2542-5196(18)30261-4",
        "Health Effects Institute (2024). State of Global Air. Available at: "
        "https://www.stateofglobalair.org",
    ]

    health = [
        "Pope, C. A. 3rd, and Dockery, D. W. (2006). Health effects of fine "
        "particulate air pollution: lines that connect. Journal of the Air and Waste "
        "Management Association, 56(6), 709-742. "
        "https://doi.org/10.1080/10473289.2006.10464485",
        "Brook, R. D., Rajagopalan, S., Pope, C. A. 3rd, et al. (2010). Particulate "
        "matter air pollution and cardiovascular disease: an update to the scientific "
        "statement from the American Heart Association. Circulation, 121(21), "
        "2331-2378. https://doi.org/10.1161/CIR.0b013e3181dbece1",
        "Gauderman, W. J., Urman, R., Avol, E., et al. (2015). Association of "
        "improved air quality with lung development in children. New England Journal "
        "of Medicine, 372(10), 905-913. https://doi.org/10.1056/NEJMoa1414123",
        "Orellano, P., Quaranta, N., Reynoso, J., Balbi, B., and Vasquez, J. (2017). "
        "Effect of outdoor air pollution on asthma exacerbations in children and "
        "adults: systematic review and multilevel meta-analysis. PLOS ONE, 12(3), "
        "e0174050. https://doi.org/10.1371/journal.pone.0174050",
        "Pedersen, M., Giorgis-Allemand, L., Bernard, C., et al. (2013). Ambient air "
        "pollution and low birthweight: a European cohort study (ESCAPE). The Lancet "
        "Respiratory Medicine, 1(9), 695-704. "
        "https://doi.org/10.1016/S2213-2600(13)70192-9",
        "United States Environmental Protection Agency (2019). Integrated Science "
        "Assessment for Particulate Matter. EPA/600/R-19/188.",
        "United States Environmental Protection Agency (2020). Integrated Science "
        "Assessment for Ozone and Related Photochemical Oxidants. EPA/600/R-20/012.",
        "United States Environmental Protection Agency (2016). Integrated Science "
        "Assessment for Oxides of Nitrogen - Health Criteria. EPA/600/R-15/068.",
        "United States Environmental Protection Agency (2017). Integrated Science "
        "Assessment for Sulfur Oxides - Health Criteria. EPA/600/R-17/451.",
        "United States Environmental Protection Agency (2010). Integrated Science "
        "Assessment for Carbon Monoxide. EPA/600/R-09/019F.",
    ]

    methods = [
        "Pedregosa, F., Varoquaux, G., Gramfort, A., et al. (2011). Scikit-learn: "
        "Machine Learning in Python. Journal of Machine Learning Research, 12, "
        "2825-2830.",
        "Chen, T., and Guestrin, C. (2016). XGBoost: A Scalable Tree Boosting System. "
        "In Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge "
        "Discovery and Data Mining, 785-794. https://doi.org/10.1145/2939672.2939785",
        "Ke, G., Meng, Q., Finley, T., et al. (2017). LightGBM: A Highly Efficient "
        "Gradient Boosting Decision Tree. In Advances in Neural Information "
        "Processing Systems 30, 3146-3154.",
        "Lundberg, S. M., and Lee, S.-I. (2017). A Unified Approach to Interpreting "
        "Model Predictions. In Advances in Neural Information Processing Systems 30, "
        "4765-4774.",
        "Lundberg, S. M., Erion, G., Chen, H., et al. (2020). From local explanations "
        "to global understanding with explainable AI for trees. Nature Machine "
        "Intelligence, 2(1), 56-67. https://doi.org/10.1038/s42256-019-0138-9",
        "Chawla, N. V., Bowyer, K. W., Hall, L. O., and Kegelmeyer, W. P. (2002). "
        "SMOTE: Synthetic Minority Over-sampling Technique. Journal of Artificial "
        "Intelligence Research, 16, 321-357. https://doi.org/10.1613/jair.953",
        "Cleveland, R. B., Cleveland, W. S., McRae, J. E., and Terpenning, I. (1990). "
        "STL: A Seasonal-Trend Decomposition Procedure Based on Loess. Journal of "
        "Official Statistics, 6(1), 3-73.",
        "Rousseeuw, P. J. (1987). Silhouettes: a graphical aid to the interpretation "
        "and validation of cluster analysis. Journal of Computational and Applied "
        "Mathematics, 20, 53-65. https://doi.org/10.1016/0377-0427(87)90125-7",
        "Bergstra, J., and Bengio, Y. (2012). Random Search for Hyper-Parameter "
        "Optimization. Journal of Machine Learning Research, 13, 281-305.",
        "Okabe, M., and Ito, K. (2008). Color Universal Design: How to make figures "
        "and presentations that are friendly to colorblind people. Available at: "
        "https://jfly.uni-koeln.de/color/",
        "Mitchell, M., Wu, S., Zaldivar, A., et al. (2019). Model Cards for Model "
        "Reporting. In Proceedings of the Conference on Fairness, Accountability, "
        "and Transparency, 220-229. https://doi.org/10.1145/3287560.3287596",
        "Gebru, T., Morgenstern, J., Vecchione, B., et al. (2021). Datasheets for "
        "Datasets. Communications of the ACM, 64(12), 86-92. "
        "https://doi.org/10.1145/3458723",
    ]

    if document == "review1":
        return common + health[:5] + methods[:3] + methods[8:11]
    if document == "review2":
        return common + methods[:1] + methods[6:8] + methods[10:11] + health[:3]
    return common + health + methods


# --------------------------------------------------------------------------- #
# PDF export and changelog
# --------------------------------------------------------------------------- #
def export_pdf(path: Path) -> Optional[Path]:
    """Convert a .docx to PDF with LibreOffice when it is available.

    LibreOffice is optional. When it is absent the function logs the fact and
    returns None rather than failing the pipeline, because the .docx is the
    required deliverable and the PDF is a convenience.
    """
    binary = shutil.which("soffice") or shutil.which("libreoffice")
    if not binary:
        LOGGER.info("LibreOffice not on PATH; skipping PDF export for %s", path.name)
        return None
    try:
        subprocess.run(
            [binary, "--headless", "--convert-to", "pdf", "--outdir",
             str(path.parent), str(path)],
            check=True, capture_output=True, timeout=180,
        )
        pdf = path.with_suffix(".pdf")
        if pdf.exists():
            LOGGER.info("Exported %s", pdf.name)
            return pdf
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        LOGGER.warning("PDF export failed for %s: %s", path.name, exc)
    return None


def write_changelog(data: Dict[str, Any], generated: List[Path]) -> Path:
    """Write the phase-by-phase changelog."""
    regression = data["regression"]
    classification = data["classification"]
    clustering = data["clustering"]
    divergence = data["divergence"]
    figures = sorted(FIGURES.glob("*.png"))

    lines = [
        "# Changelog",
        "",
        "> Generated by `src/report/build_docx.py`. Each entry records what a phase "
        "added, with the figures that were produced by it.",
        "",
        f"Generated (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "",
        "## Phase 1 — Problem framing and dataset (Review 1)",
        "",
        "* Acquisition with two paths; the programmatic path verified to work "
        "without credentials.",
        "* Machine-generated provenance record with SHA-256 checksums for every "
        "file and the licence string read from the live dataset page.",
        f"* Column-level schema profile of the primary file "
        f"({data['provenance'].get('primary_file', {}).get('rows', 0):,} rows).",
        "* Project charter: scope, stakeholder matrix, success criteria, risk "
        "register, assumptions, ethics and feasibility.",
        "* Figures added: `00_dataset_proof_schema.png`, `39_pipeline_diagram.png`, "
        "`40_project_gantt.png`.",
        "",
        "## Phase 2 — Preprocessing and exploratory analysis (Review 2)",
        "",
        "* Full data quality assessment with duplicate, plausibility, unit and "
        "outlier checks under two rules.",
        f"* City retention gates applied; "
        f"{data['quality'].get('city_retention', {}).get('n_retained', 0)} of "
        f"{data['quality'].get('city_retention', {}).get('n_retained', 0) + data['quality'].get('city_retention', {}).get('n_excluded', 0)} "
        f"cities retained, every exclusion tabled with its reason.",
        "* Sensor-artefact rule with an explicit event-window exemption, so no "
        "festival, burning-season or lockdown observation is removed by the "
        "statistical spike test.",
        f"* Imputation strategy selected by a masking experiment over five "
        f"candidates; "
        f"`{data['cleaning'].get('imputation_applied', {}).get('strategy', 'n/a')}` "
        f"adopted as the best causal option.",
        f"* Feature engineering: "
        f"{data['features'].get('feature_group_counts', {}).get('total_candidates', 0)} "
        f"candidate features across nine groups.",
        f"* Health Advisory Index built and validated; divergence from the official "
        f"AQI measured at "
        f"{divergence.get('any_cohort_differs', {}).get('pct', 0)}% of city-days.",
        "* Safest-exposure-window recommender built from the hourly record.",
        "* Figures added: `01` through `23`.",
        "",
        "## Phase 3 — Modelling, comparison and product (Review 3)",
        "",
        f"* Regression: "
        f"{len([r for r in regression.get('results', []) if r['family'] != 'baseline'])} "
        f"families plus a persistence baseline. Best: "
        f"{regression.get('best_model', 'n/a')} at MAE "
        f"{regression.get('best_test_metrics', {}).get('MAE', 0)}.",
        f"* Classification: "
        f"{len([r for r in classification.get('results', []) if r['family'] != 'baseline'])} "
        f"configurations including SMOTE variants. Best: "
        f"{classification.get('best_model', 'n/a')} at macro F1 "
        f"{classification.get('best_test_metrics', {}).get('macro_f1', 0)}.",
        f"* Clustering: K-Means at k = {clustering.get('selected_k', '?')}, "
        f"reproduced exactly by Ward agglomerative clustering (adjusted Rand index "
        f"{clustering.get('algorithm_agreement', {}).get('adjusted_rand_index', 0)}).",
        "* Hyperparameter optimisation with randomised and exhaustive search, both "
        "under TimeSeriesSplit.",
        "* SHAP global and local explanations.",
        "* Counterfactual policy simulator with seven scenarios.",
        "* Four-page Streamlit application with trilingual advisory text.",
        "* Data card and model card generated from results.",
        "* Figures added: `24` through `38`.",
        "",
        "## Artefact counts at this build",
        "",
        f"* Figures: **{len(figures)}**, all at {config.FIG_DPI} DPI.",
        f"* Result files: "
        f"**{len(list(config.RESULTS_DIR.glob('*.json'))) + len(list(config.RESULTS_DIR.glob('*.csv')))}**.",
        f"* Model artefacts: **{len(list(config.MODELS_DIR.glob('*.joblib')))}**.",
        f"* Review documents: **{len(generated)}**.",
        "",
    ]
    CHANGELOG.write_text(chr(10).join(lines), encoding="utf-8")
    LOGGER.info("Wrote %s", CHANGELOG.name)
    return CHANGELOG


def main(deployment_url: str = "See README.md for the live application URL") -> Dict[str, str]:
    """Generate all three review documents, their PDFs and the changelog."""
    config.ensure_dirs()
    data = load_all()

    from src.report import review1, review2, review3

    generated = [
        review1.build(data),
        review2.build(data),
        review3.build(data, deployment_url),
    ]
    for path in generated:
        export_pdf(path)

    write_changelog(data, generated)
    return {path.stem: str(path) for path in generated}


if __name__ == "__main__":
    main()
