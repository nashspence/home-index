# ruff: noqa: E402
# mypy: ignore-errors
from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

import pytest

# Ensure project root is importable when running tests directly
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def stub_dependencies(monkeypatch):
    modules = {
        "debugpy": types.ModuleType("debugpy"),
        "xxhash": types.ModuleType("xxhash"),
        "magic": types.ModuleType("magic"),
        "apscheduler": types.ModuleType("apscheduler"),
        "apscheduler.schedulers": types.ModuleType("apscheduler.schedulers"),
        "apscheduler.schedulers.background": types.ModuleType(
            "apscheduler.schedulers.background"
        ),
        "apscheduler.triggers": types.ModuleType("apscheduler.triggers"),
        "apscheduler.triggers.interval": types.ModuleType(
            "apscheduler.triggers.interval"
        ),
        "apscheduler.triggers.cron": types.ModuleType("apscheduler.triggers.cron"),
        "meilisearch_python_sdk": types.ModuleType("meilisearch_python_sdk"),
        "meilisearch_python_sdk.models": types.ModuleType(
            "meilisearch_python_sdk.models"
        ),
        "meilisearch_python_sdk.models.settings": types.ModuleType(
            "meilisearch_python_sdk.models.settings"
        ),
        "meilisearch": types.ModuleType("meilisearch"),
        "meilisearch.models": types.ModuleType("meilisearch.models"),
        "meilisearch.models.embedders": types.ModuleType(
            "meilisearch.models.embedders"
        ),
        "sentence_transformers": types.ModuleType("sentence_transformers"),
        "langchain_core.documents": types.ModuleType("langchain_core.documents"),
        "langchain_text_splitters": types.ModuleType("langchain_text_splitters"),
        "torch": types.ModuleType("torch"),
        "transformers": types.ModuleType("transformers"),
    }

    # Provide minimal implementations for modules used during import
    magic_mod = modules["magic"]

    class DummyMagic:
        def __init__(self, *args, **kwargs):
            pass

        def from_file(self, path):
            return "text/plain"

    magic_mod.Magic = DummyMagic

    xxhash_mod = modules["xxhash"]

    class DummyHasher:
        def update(self, _):
            pass

        def hexdigest(self):
            return "0"

    def xxh64():
        return DummyHasher()

    xxhash_mod.xxh64 = xxh64

    sched_bg = modules["apscheduler.schedulers.background"]

    class DummyScheduler:
        def add_job(self, *args, **kwargs):
            pass

        def start(self):
            pass

    sched_bg.BackgroundScheduler = DummyScheduler

    modules["apscheduler.triggers.interval"].IntervalTrigger = type(
        "IntervalTrigger",
        (),
        {"__init__": lambda self, *a, **k: None},
    )

    modules["apscheduler.triggers.cron"].CronTrigger = type(
        "CronTrigger",
        (),
        {"__init__": lambda self, *a, **k: None},
    )

    sdk_mod = modules["meilisearch_python_sdk"]

    class DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def health(self):
            return {}

    sdk_mod.AsyncClient = DummyAsyncClient

    meili_emb_mod = modules["meilisearch_python_sdk.models.settings"]

    class Embedders:
        def __init__(self, embedders):
            self.embedders = embedders

    class HuggingFaceEmbedder:
        def __init__(
            self, model: str, document_template: str, dimensions: int | None = None
        ):
            self.model = model
            self.document_template = document_template
            self.dimensions = dimensions

    meili_emb_mod.Embedders = Embedders
    meili_emb_mod.HuggingFaceEmbedder = HuggingFaceEmbedder

    class MeilisearchSettings:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

        def model_dump(self):
            return self.__dict__

    meili_emb_mod.MeilisearchSettings = MeilisearchSettings

    lc_doc_mod = modules["langchain_core.documents"]

    class DummyDocument:
        def __init__(self, page_content, metadata=None):
            self.page_content = page_content
            self.metadata = metadata or {}

    lc_doc_mod.Document = DummyDocument

    lc_split_mod = modules["langchain_text_splitters"]

    class DummyTextSplitter:
        @classmethod
        def from_huggingface_tokenizer(cls, tok, chunk_size=1, chunk_overlap=0):
            inst = cls()
            inst.size = chunk_size
            return inst

        def split_documents(self, docs):
            result = []
            for doc in docs:
                tokens = doc.page_content.split()
                for i in range(0, len(tokens), self.size):
                    text = " ".join(tokens[i : i + self.size])
                    result.append(DummyDocument(text, doc.metadata))
            return result

    lc_split_mod.TokenTextSplitter = DummyTextSplitter

    transformers_mod = modules["transformers"]

    class DummyTokenizer:
        def __init__(self, *args, **kwargs):
            pass

        def tokenize(self, text):
            return text.split()

    transformers_mod.AutoTokenizer = type(
        "AutoTokenizer",
        (),
        {"from_pretrained": staticmethod(lambda name: DummyTokenizer())},
    )

    # Link parent packages to submodules
    modules["apscheduler"].schedulers = modules["apscheduler.schedulers"]
    modules["apscheduler"].triggers = modules["apscheduler.triggers"]
    modules["apscheduler.schedulers"].background = sched_bg
    modules["apscheduler.triggers"].interval = modules["apscheduler.triggers.interval"]
    modules["apscheduler.triggers"].cron = modules["apscheduler.triggers.cron"]
    modules["meilisearch"].models = modules["meilisearch.models"]
    modules["meilisearch.models"].embedders = modules["meilisearch.models.embedders"]
    modules["meilisearch_python_sdk"].models = modules["meilisearch_python_sdk.models"]
    modules["meilisearch_python_sdk.models"].settings = modules[
        "meilisearch_python_sdk.models.settings"
    ]

    for name, module in modules.items():
        sys.modules.setdefault(name, module)
    for mod in ["features.F1", "features.F1.scheduler", "features.F1.sync"]:
        sys.modules.pop(mod, None)

    # Attempt to use real apscheduler if installed
    modules_to_restore = [
        "apscheduler",
        "apscheduler.schedulers",
        "apscheduler.schedulers.background",
        "apscheduler.triggers",
        "apscheduler.triggers.interval",
        "apscheduler.triggers.cron",
    ]
    originals = {mod: sys.modules.get(mod) for mod in modules_to_restore}
    try:
        for mod in modules_to_restore:
            sys.modules.pop(mod, None)
        import apscheduler  # noqa: F401
    except ModuleNotFoundError:
        for mod, value in originals.items():
            if value is not None:
                sys.modules[mod] = value
    else:
        for mod in modules_to_restore:
            sys.modules[mod] = importlib.import_module(mod)

    import features.F1 as f1

    importlib.reload(f1)
    try:
        yield
    finally:
        for name in modules:
            sys.modules.pop(name, None)
