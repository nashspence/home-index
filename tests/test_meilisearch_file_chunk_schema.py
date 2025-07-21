import json
import pathlib
from jsonschema import Draft7Validator

SCHEMA_PATH = pathlib.Path("features/F5/docs/meilisearch_file_chunk.schema.json")


def test_chunk_documents_follow_the_chunk_schema():
    schema = json.loads(SCHEMA_PATH.read_text())
    Draft7Validator.check_schema(schema)
