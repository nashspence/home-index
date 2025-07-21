# Home Index

Home Index is a personal file search engine that syncs and enriches metadata.

## Features

1. [F1 Scheduled file‑sync](features/F1/SPEC.md)
2. [F2 Search for unique files by metadata](features/F2/SPEC.md)
3. [F3 Offline media to remains searchable](features/F3/SPEC.md)
4. [F4 Modules enrich your project files](features/F4/SPEC.md)
5. [F5 Search file chunks by concept](features/F5/SPEC.md)
6. [F6 Remote file operations via API](features/F6/SPEC.md)

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
