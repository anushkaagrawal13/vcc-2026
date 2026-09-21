PYTHON ?= .venv/bin/python
CONFIG ?= config/000_zero_delta.yaml

.PHONY: help test download predict validate package
help:
	@echo 'Run in order: make test, make download, make predict, make validate, make package'
	@echo 'Authenticate first: source .venv/bin/activate && vcc login'
	@echo 'Each experiment uses CONFIG=config/<experiment>.yaml'

test:
	$(PYTHON) -m pytest -q
download:
	$(PYTHON) -m src.data.download --config $(CONFIG)
predict:
	$(PYTHON) -m src.predict --config $(CONFIG)
validate:
	$(PYTHON) -m src.evaluate --config $(CONFIG)
package:
	$(PYTHON) -m src.evaluate --config $(CONFIG) --package
