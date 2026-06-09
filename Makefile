.PHONY: test examples check

test:
	PYTHONPATH=src python3 -m unittest discover -s tests

examples:
	PYTHONPATH=src python3 -m harness_trajecdebug.cli diagnose \
		--trace examples/traces/train-fasttext-kimi-k26-minimal.json \
		--run-id train-fasttext-kimi-k26-minimal \
		--output examples/diagnoses/train-fasttext-kimi-k26-diagnosis.json
	PYTHONPATH=src python3 -m harness_trajecdebug.cli diagnose \
		--trace examples/traces/cancel-async-tasks-passed-minimal.json \
		--run-id cancel-async-tasks-passed-minimal \
		--output examples/diagnoses/cancel-async-tasks-diagnosis.json

check: test examples
	python3 -m py_compile src/harness_trajecdebug/*.py
