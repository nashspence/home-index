import json
import pathlib

from jsonschema import Draft7Validator

SCHEMA_PATH = pathlib.Path("features/F2/docs/meilisearch_document.schema.json")


def test_file_documents_match_the_expected_schema():
    schema = json.loads(SCHEMA_PATH.read_text())
    # raises jsonschema.exceptions.SchemaError if invalid
    Draft7Validator.check_schema(schema)
