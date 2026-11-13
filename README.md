# ask-the-plan
very very accurate with your building blueprints!!

The preliminary local IFC query engine lives in `ifc_engine/` and uses the shared
query/evidence contracts. See [setup, CLI examples, and supported operations](docs/IFC_ENGINE.md).

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m ifc_engine --help
.venv/bin/python -m unittest discover -s tests -v
```
