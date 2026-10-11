PYTHON ?= python
.PHONY: data features backtest results figures paper test
data features backtest results figures paper test:
	$(PYTHON) -m src.research.reproduce $@
