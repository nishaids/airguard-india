"""One-command reproduction of the entire AirGuard India pipeline.

Running this script from a fresh clone regenerates every result, every figure and
every report in the repository, in dependency order:

    acquire -> quality -> clean -> features -> safe windows -> EDA
            -> regression -> classification -> clustering -> tuning
            -> evaluation -> explainability -> policy simulation
            -> cards -> notebooks -> reports

Usage
-----
::

    python run_all.py                  # run everything
    python run_all.py --from features  # resume from a named stage
    python run_all.py --only eda       # run one stage
    python run_all.py --list           # list the stages and exit
    python run_all.py --skip notebooks # run everything except a stage

Every stage is idempotent. The script exits with a non-zero status if any stage
fails, and prints a timing summary at the end.
"""

from __future__ import annotations

import argparse
import importlib
import sys
import time
import traceback
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import config  # noqa: E402

# Windows consoles default to cp1252, which cannot encode the box-drawing and
# tick characters a progress report naturally reaches for. Rather than losing the
# pipeline to a UnicodeEncodeError on the last line of a successful stage, the
# streams are reconfigured to UTF-8 where the interpreter supports it and the
# progress markers are plain ASCII regardless.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover - older interpreters
        pass

LOGGER = config.get_logger("run_all")

#: Ordered pipeline stages: (name, module path, description).
STAGES: List[Tuple[str, str, str]] = [
    ("acquire", "src.data.acquire", "Download the dataset and write the provenance record"),
    ("quality", "src.data.quality", "Assess data quality and decide city retention"),
    ("clean", "src.data.clean", "Clean, select the imputation strategy, validate"),
    ("features", "src.features.build", "Engineer features, build the HAI, split the data"),
    ("safe_windows", "src.features.safe_window", "Compute the safest outdoor windows"),
    ("eda", "src.eda.plots", "Generate exploratory figures, statistics and insights"),
    ("regression", "src.models.train_regression", "Train and evaluate the regression models"),
    ("classification", "src.models.train_classification", "Train and evaluate the classifiers"),
    ("clustering", "src.models.train_clustering", "Discover city pollution archetypes"),
    ("tuning", "src.models.tune", "Optimise hyperparameters for the winning models"),
    ("evaluation", "src.models.evaluate", "Build comparison tables and diagnostic figures"),
    ("explain", "src.models.explain", "Compute SHAP explanations"),
    ("policy", "src.simulate.policy", "Run the counterfactual policy scenarios"),
    ("cards", "src.report.cards", "Generate the data card and the model card"),
    ("diagrams", "src.report.diagrams", "Draw the pipeline and project-plan schematics"),
    ("notebooks", "src.report.notebooks", "Build and execute the three phase notebooks"),
    ("reports", "src.report.build_docx", "Generate the three review documents"),
    ("readme", "src.report.readme", "Inject the live results table into the README"),
    ("smoke", "tests.test_smoke", "Run the smoke tests over the artefacts and the app"),
    ("audit", "src.report.audit", "Audit the project against its Definition of Done"),
]

STAGE_NAMES = [name for name, _, _ in STAGES]


def run_stage(name: str, module_path: str) -> Tuple[bool, float, Optional[str]]:
    """Import a stage module and call its ``main``.

    Returns
    -------
    tuple
        ``(succeeded, elapsed_seconds, error_text)``.
    """
    started = time.perf_counter()
    try:
        module = importlib.import_module(module_path)
        if not hasattr(module, "main"):
            raise AttributeError(f"{module_path} has no main()")
        outcome = module.main()
        # A stage that returns a non-zero integer is reporting failure in the
        # POSIX sense rather than raising; the smoke-test stage does this.
        if isinstance(outcome, int) and outcome != 0:
            return (
                False,
                time.perf_counter() - started,
                f"{module_path}.main() returned exit status {outcome}",
            )
        return True, time.perf_counter() - started, None
    except Exception:
        return False, time.perf_counter() - started, traceback.format_exc()


def select_stages(args: argparse.Namespace) -> List[Tuple[str, str, str]]:
    """Resolve the command-line selection into an ordered stage list."""
    if args.only:
        unknown = [s for s in args.only if s not in STAGE_NAMES]
        if unknown:
            raise SystemExit(f"Unknown stage(s): {', '.join(unknown)}. Use --list.")
        return [s for s in STAGES if s[0] in set(args.only)]

    stages = STAGES
    if args.start_from:
        if args.start_from not in STAGE_NAMES:
            raise SystemExit(f"Unknown stage '{args.start_from}'. Use --list.")
        index = STAGE_NAMES.index(args.start_from)
        stages = STAGES[index:]
    if args.skip:
        skip = set(args.skip)
        stages = [s for s in stages if s[0] not in skip]
    return stages


def main() -> int:
    """Run the selected stages and report a timing summary."""
    parser = argparse.ArgumentParser(
        description="Reproduce the AirGuard India pipeline end to end.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--from", dest="start_from", metavar="STAGE",
                        help="resume from this stage onwards")
    parser.add_argument("--only", nargs="+", metavar="STAGE", help="run only these stages")
    parser.add_argument("--skip", nargs="+", metavar="STAGE", help="skip these stages")
    parser.add_argument("--list", action="store_true", help="list the stages and exit")
    parser.add_argument("--continue-on-error", action="store_true",
                        help="keep going after a stage fails")
    args = parser.parse_args()

    if args.list:
        print("Pipeline stages, in order:\n")
        for index, (name, module_path, description) in enumerate(STAGES, start=1):
            print(f"  {index:2}. {name:<15} {description}")
            print(f"      {module_path}")
        return 0

    config.set_global_seed()
    config.ensure_dirs()

    stages = select_stages(args)
    LOGGER.info("Running %s of %s stages", len(stages), len(STAGES))
    print("=" * 78)

    timings: List[Tuple[str, bool, float]] = []
    failures: List[str] = []

    for index, (name, module_path, description) in enumerate(stages, start=1):
        print(f"\n[{index}/{len(stages)}] {name} — {description}")
        print("-" * 78)
        succeeded, elapsed, error = run_stage(name, module_path)
        timings.append((name, succeeded, elapsed))

        if succeeded:
            print(f"  [ok]   {name} completed in {elapsed:.1f}s")
        else:
            print(f"  [FAIL] {name} failed after {elapsed:.1f}s")
            print(error)
            failures.append(name)
            if not args.continue_on_error:
                break

    print("\n" + "=" * 78)
    print("PIPELINE SUMMARY")
    print("=" * 78)
    total = sum(t for _, _, t in timings)
    for name, succeeded, elapsed in timings:
        status = "ok  " if succeeded else "FAIL"
        share = 100.0 * elapsed / total if total else 0.0
        print(f"  {status}  {name:<15} {elapsed:>8.1f}s  ({share:>5.1f}%)")
    print("-" * 78)
    print(f"  Total: {total:.1f}s ({total / 60:.1f} min)")

    if failures:
        print(f"\n  {len(failures)} stage(s) failed: {', '.join(failures)}")
        return 1

    figures = sorted(config.FIGURES_DIR.glob("*.png"))
    results = sorted(config.RESULTS_DIR.glob("*.json")) + sorted(config.RESULTS_DIR.glob("*.csv"))
    reports = sorted(config.REPORTS_DIR.glob("*.docx"))
    models = sorted(config.MODELS_DIR.glob("*.joblib"))
    print(
        f"\n  Artefacts: {len(figures)} figures, {len(results)} result files, "
        f"{len(models)} model artefacts, {len(reports)} review documents."
    )
    print("  Launch the application with:  streamlit run app/Home.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
