# Home Index

Home Index is a personal file search engine that syncs and enriches metadata.

## Features

- [F1 "I want scheduled file sync"](features/F1/specification.md)
- [F2 "I want to search for unique files by metadata"](features/F2/specification.md)
- [F3 "I want metadata for files on offline media"](features/F3/specification.md)
- [F4 "I want modules to enrich files"](docs/F4.md)
- [F5 "I want to search file chunks by concept"](docs/F5.md)
- [F6 "I want remote file operations"](docs/F6.md) – mountable WebDAV share
  and JSON API update metadata and search index soon after changes without a
  full rescan

### Well-known modules

A few maintained modules provide common functionality out of the box:

- [home-index-read](https://github.com/nashspence/home-index-read) – perform OCR on images and PDFs using EasyOCR.
- [home-index-scrape](https://github.com/nashspence/home-index-scrape) – extract metadata with tools like ExifTool and Apache Tika.
- [home-index-caption](https://github.com/nashspence/home-index-caption) – generate image and video captions using the BLIP model.
- [home-index-transcribe](https://github.com/nashspence/home-index-transcribe) – create transcripts from media with WhisperX.
- [home-index-thumbnail](https://github.com/nashspence/home-index-thumbnail) – produce WebP thumbnails and previews.

## Front-end interfaces

[home-index-rag-query](https://github.com/nashspence/home-index-rag-query) – offers a Streamlit-driven RAG experience, letting you ask questions against
your files using a locally run language model backed by Meilisearch.

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.

## Planned Maintenance
- None
