# SmartDoc AI

## AI-Powered Document Intelligence Assistant

SmartDoc AI is a document question-answering system that allows users to upload PDF documents and ask questions using natural language. It uses Retrieval-Augmented Generation (RAG) to retrieve relevant information from documents and generate grounded answers with source references.

## Features

* Upload single or multiple PDF documents
* Ask natural-language questions
* RAG-based document question answering
* Semantic search using embeddings
* Document and page-level source references
* Multi-document querying
* Conversational follow-up questions
* Study-all mode
* Learning-oriented requests for teaching, study plans, quizzes, flashcards, revision, and exam preparation
* Page-scoped retrieval using natural language (for example, "pages 2 to 4")
* Share and download answers
* Chrome Extension interface
* REST API with Swagger documentation
* Cloud deployment using Render

## Technology Stack

* Python
* FastAPI
* JavaScript
* HTML & CSS
* Chrome Extension
* RAG
* Text Embeddings
* Vector Search
* Google Gemini
* Pydantic
* Git & GitHub
* Render
* Swagger / OpenAPI

## How It Works

```text
PDF Upload
    ↓
Text Extraction
    ↓
Document Chunking
    ↓
Embeddings
    ↓
Vector Search
    ↓
Relevant Context
    ↓
Gemini
    ↓
Grounded Answer + Sources
```

## Architecture

```text
Chrome Extension
       ↓
FastAPI Backend
       ↓
Document Processing
       ↓
RAG Retrieval
       ↓
Gemini
       ↓
Answer + Source References
```

## API

| Method | Endpoint                  | Purpose              |
| ------ | ------------------------- | -------------------- |
| GET    | `/api/v1/health`          | Health check         |
| GET    | `/api/v1/documents`       | List documents       |
| POST   | `/api/v1/documents`       | Upload PDF           |
| POST   | `/api/v1/documents/batch` | Upload multiple PDFs |
| DELETE | `/api/v1/documents/{id}`  | Delete document      |
| POST   | `/api/v1/documents/clear` | Clear documents      |
| POST   | `/api/v1/query`           | Ask a document-grounded question or learning task |
| POST   | `/api/v1/share`           | Create share link    |
| GET    | `/api/v1/share/{id}`      | Get shared answer    |

## Deployment

Backend: Render

API Documentation:
https://smartdoc-ai-backend-hvv9.onrender.com/docs

## Project Status

Core document processing, RAG retrieval, Gemini integration, multi-document support, Chrome Extension, API, testing, and cloud deployment are implemented.

Answer-quality optimization and additional features are under continuous development.

SmartDoc remains document-grounded: learning workflows use only the selected PDF evidence and do
not silently fall back to unlabelled general-AI knowledge.

## Future Improvements

* Improved retrieval accuracy
* Hybrid search and reranking
* OCR for scanned PDFs
* Table and image understanding
* User authentication
* Persistent document storage
* Multilingual document support

Interests: Artificial Intelligence, Machine Learning, Generative AI, RAG, and Software Development.

##
