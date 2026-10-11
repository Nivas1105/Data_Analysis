.PHONY: setup demo test clean
setup:
	pip install -r requirements.txt
demo:
	PYTHONPATH=src python -m fq.cli demo
test:
	PYTHONPATH=src pytest -q
clean:
	rm -rf data reports/*.md reports/*.json reports/charts reports/exports
