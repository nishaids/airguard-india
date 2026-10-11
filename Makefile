PYTHON ?= python
.PHONY: data features backtest results figures paper test refs tables rules article checks

# Evidence stages. Each one writes results/*.json and reports PENDING rather
# than a number when its inputs are absent.
data features backtest results figures paper test:
	$(PYTHON) -m src.research.reproduce $@

# Generated paper inputs. Nothing in the manuscript is typed by hand: the
# bibliography is fetched and verified, the tables are read from artefacts.
refs:
	$(PYTHON) -m scripts.build_refs

tables:
	$(PYTHON) -m scripts.export_evidence_table
	$(PYTHON) -m scripts.export_hai_factors

# Static checks that need no LaTeX toolchain. `rules` fails while the author
# placeholders are unresolved, which is a human action, so it is not part of
# `checks`.
rules:
	$(PYTHON) -m scripts.check_paper_rules

article:
	$(PYTHON) -m scripts.check_article_originality

checks:
	$(PYTHON) -m scripts.check_generated_paths
	$(PYTHON) -m scripts.check_public_exports
	$(PYTHON) -m scripts.check_article_originality
