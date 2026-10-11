# Submission checklist

Rules are from the conference call and IEEE policy, as recorded in
`docs/MASTER_SPEC.md` Part E. Everything checkable without a LaTeX run is
checked by `python -m scripts.check_paper_rules`, which writes
`results/paper_rules.json` and exits non-zero on a failure. Do not tick a line
here by hand that the script can decide.

## Automated (run the script)

| Rule | State |
| --- | --- |
| `\documentclass[conference]{IEEEtran}` | checked, passing |
| No clickable links: `hyperref` and `fancyhdr` absent | checked, passing |
| No headers, footers or page numbers: no `\pagestyle`, `\thispagestyle`, `\pagenumbering` | checked, passing |
| Every figure is an existing vector PDF | checked, passing |
| Every table comes from a generated `.tex` | checked, passing |
| `refs.bib` is generated, not hand-edited | checked, passing |
| Every `\cite` key resolves to an entry | checked, passing |
| Every cited entry was verified against a publisher record | checked, passing |
| No entry that failed verification is cited | checked, passing |
| AI-use disclosure present in the Acknowledgment | checked, passing |
| Ethics statement present | checked, passing |
| Author placeholders resolved | **checked, failing** — see below |

## Needs a LaTeX toolchain (none installed in this environment)

| Rule | How to check |
| --- | --- |
| At most 6 pages including references | compile and count; `make paper` is gated until results exist |
| Fonts embedded | `pdffonts main.pdf`, every font `emb` |
| Figure text at least 8 pt, legible in greyscale | inspect the compiled figures |
| Paper size per the CFP | set once a conference is chosen |
| IEEE PDF eXpress validation | required by some venues only |

Install a TeX distribution, or compile on Overleaf, then record the page count
and `pdffonts` output in `results/paper_rules.json`.

## Needs a human decision

| Item | Why it cannot be automated |
| --- | --- |
| Author full names, emails, order, affiliation wording | `\author{}` still contains `NAME` placeholders. Every listed author must meet IEEE authorship criteria: substantive contribution, drafting or revising, and approval of the final version. |
| Target conference and its CFP | Deadline, page limit, whether references count, similarity threshold, fees and copyright all follow from the venue. None is chosen. |
| Whether each cited source supports the claim attached to it | Verification confirms a record exists and its title matches. It does not read the paper. |
| Adoption of any health coefficient | `config/hai_factors.yaml` adopts none. A qualified reviewer must check source, exposure window, population and units. |
| Similarity check before submission | Run the venue's tool. The Medium article must not share sentences with the paper; `python -m scripts.check_article_originality` measures the overlap. |
| Preprint notice wording | If posting to arXiv or TechRxiv before acceptance, add the venue's required notice, and the IEEE copyright notice after acceptance. |

## Blocking the submission, not the draft

The manuscript is an unsubmitted draft and says so in its own abstract. Beyond
the human decisions above, submission waits on evidence that cannot be hurried:

- No matched issue-time station pairs exist yet, so there is no accuracy,
  interval-coverage or advisory result to report. `results/backtest_main.json`
  and its siblings are PENDING with the reason recorded.
- The archived CAMS forecasts needed for a retrospective backtest require ADS
  credentials and licence acceptance (`HUMAN_ACTIONS.md`).
- The prospective record began on 11 October 2026. A 30-day record cannot be
  backdated; it takes 30 days.

`make paper` refuses to build while `results/evidence_index.json` reports
`paper_submittable: false`. That gate is deliberate: a compiled PDF from empty
inputs would look like a finished study.
