# Home Index

Home Index is a personal file search engine that syncs and enriches metadata.

## Features

- [F1 "I want scheduled file sync"](docs/F1.md)
- F2 "I want metadata stored by file ID"
- F3 "I want each path linked to its metadata"
- F4 "I want to detect duplicate files"
- F5 "I want metadata for files on offline media"
- F6 "I want to search my file metadata"
- F7 "I want modules to enrich files"
- F8 "I want those modules to run on other machines"
- F9 "I want to search file chunks by concept"

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

- Add documentation for features F2–F9.
- Expand acceptance tests to cover all features.
