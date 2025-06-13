import json
import pathlib

from jsonschema import Draft7Validator

SCHEMA_PATH = pathlib.Path('docs/meilisearch_document.schema.json')


def test_schema_is_valid():
    schema = json.loads(SCHEMA_PATH.read_text())
    # raises jsonschema.exceptions.SchemaError if invalid
    Draft7Validator.check_schema(schema)
