# Home Index

Home Index is a file indexing service built around [Meilisearch](https://www.meilisearch.com/). It scans a directory of files, stores metadata under a configurable location and can enrich that metadata by calling external **modules**. Modules handle tasks such as transcription, OCR, scraping, thumbnails or caption generation so your files become easily searchable.

## Features

- [F1 "I want my home server to be available when I need it"](docs/F1.md)
- F2: to link to my files by path
- F3: to know my files that were last modified within a range of time
- F4: to know my files of a specific type
- F5: to know my largest files
- F6: to know my duplicates files
- F7: to know about my files even when they are on disconnected external media
- F8: to run intensive indexing operations on other machines
- F9: to view my files in a web browser
- F10: to know which ones of my files match a concept
- F11: to know which ones of my files contain a text phrase
- F12: to separate my manually created files from my derived files

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
