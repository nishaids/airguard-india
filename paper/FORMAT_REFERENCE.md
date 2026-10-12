# Publication layout adaptation

The uploaded **LogSight Paper.docx** was inspected as a read-only presentation reference. Its SHA-256 is `c939393c3fd49a975080839898d4220e29ccee26a0b3f4b18893949b6101a8c1`. It is not included in this repository, and none of its scientific content, author identities, hyperparameters or results are used in AirGuard.

## Reference profile

The six-page reference uses an A4 two-column body, a full-width title and author area, an abstract followed by keywords, centred Roman-numbered major headings, lettered italic subsections, numbered equations, captions above tables and below figures, and numbered citations. Its measured body styling is approximately 9 pt Times New Roman, with an 18 pt column gap. The major section sequence is Introduction, Related Work, Proposed Method, Experimental Setup, Results and Discussion, Limitations, and Conclusion and Future Work.

Some narrow reference tables break words and header labels awkwardly, and its wide architecture graphic has small labels. AirGuard adopts the structural cues while using IEEEtran's standard body size, margins, section styles and citation formatting. Compact tables keep numeric comparisons readable. Native vector diagrams and plots remain sharp without external image dependencies. Multi-line equations prevent column overflow.

## Two manuscript variants

| Variant | Entry point | Layout and purpose |
| --- | --- | --- |
| Conference | `paper/conference/main.tex` | IEEEtran conference mode, A4, compact reference-inspired section flow |
| Journal | `paper/journal/main.tex` | IEEEtran journal mode, Letter, expanded availability, baseline-support, advisory and reproducibility detail |
| Existing editor | `paper/station_calibration_skeleton.tex` | Same journal narrative, flattened in place with embedded bibliography; the existing editor remains open |

The journal's extra detail explains issue-time admissibility, sensor QC, Severe censoring, the raw CAMS support contract, calibration and advisory limitations. It does not add invented experiment results. Both variants separate the completed non-CAMS preliminary findings from the pending primary archived-CAMS experiment.

There is no named target venue yet. IEEE's official [journal template guidance](https://journals.ieeeauthorcenter.ieee.org/create-your-ieee-journal-article/authoring-tools-and-templates/tools-for-ieee-authors/ieee-article-templates/) and [conference author guidance](https://events.ieee.org/planning-basics/ieee-conference-publications/publishing-information-for-ieee-conference-authors/) require the appropriate venue template and instructions. These drafts provide an IEEE layout basis; formatting alone does not establish submission readiness or acceptance.

## Evidence and safety

`paper/publication_format_manifest.json` records input evidence identities and generated source hashes. Only existing JSON summaries and verified bibliography entries are read during formatting. No model is fitted, no target data is materialised, no ADS request is made, no credential file is opened and no production change is deployed. The immutable protocol hash is checked before writing.

The sample model scores and acquisition suggestions in the user's pasted planning attachment are not verified AirGuard results. They do not enter the manuscript or alter the locked study. Missing CAMS comparison results remain explicitly marked `[RESULT PENDING CAMS ARCHIVE EXPERIMENT]`. The model-selection lock remains pending; final-test access and submission readiness remain false.

## Refresh and compile

From the repository root, run `python scripts/format_publication_drafts.py` to refresh both variants and the existing editor source from current development summaries. This deliberately regenerates the narrative: preserve any manual manuscript edits before refreshing, or apply shared narrative revisions in the formatter. The historical packaging scripts delegate to this formatter once its manifest exists; their earlier implementations and research artifacts remain preserved in Git.

Compile `main.tex` from each variant's own directory with the pinned `logs/toolchain/tectonic-0.17.0/tectonic.exe` and `--keep-logs`. The editor source is also checked with Codex's built-in LaTeX compiler. Render every page and inspect figures, tables, equations, references and page endings. `paper/publication_layout_validation.json` records the latest compile and visual review evidence; diagnostic renders remain under `logs/` and are not deliverables.
