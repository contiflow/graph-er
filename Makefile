# Convenience targets (pipeline still requires Python 2.7 + legacy deps).
.PHONY: help run-example

help:
	@echo "Targets:"
	@echo "  make run-example  — print the recommended bib-ER command (dblp-acm1 profile)"

run-example:
	@echo 'PYTHON=python2 python RELATER/run_relater.py --config config/examples/dblp-acm1.yaml'
