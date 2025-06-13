import json
import pathlib
from jsonschema import Draft7Validator

SCHEMA_PATH = pathlib.Path('docs/meilisearch_file_chunk.schema.json')

def test_chunk_schema_is_valid():
    schema = json.loads(SCHEMA_PATH.read_text())
    Draft7Validator.check_schema(schema)
