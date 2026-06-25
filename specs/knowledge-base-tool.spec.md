# Spec: Knowledge Base Tool for Agent

## Purpose
Enable the agent to connect to and query a knowledge base so it can ground responses in project-specific documents, SOPs, and reference material via Retrieval-Augmented Generation (RAG).

## Problem Statement
The agent currently generates responses using only the LLM's training data and conversation history. It has no access to internal documents, runbooks, or domain-specific knowledge — leading to generic answers and an inability to reference authoritative project content.

## Goals
- Provide the agent with a tool that retrieves relevant content from a configured knowledge base.
- Support local file-based knowledge bases (directory of documents) as the initial implementation.
- Inject retrieved context into the agent's prompt so responses are grounded in real data.
- Keep the tool modular so the retrieval backend can be swapped (e.g., vector DB, AWS Bedrock Knowledge Base) without changing the agent interface.

## Non-Goals
- No document upload UI in this feature (documents are added to a directory or managed externally).
- No fine-tuning or model retraining.
- No multi-tenant knowledge base isolation.
- No real-time web search — knowledge base is static/pre-indexed content.

---

## User Stories
- As a user, I can ask the agent questions and receive answers grounded in my project documents.
- As a user, I can configure which knowledge base directory the agent uses.
- As a user, I can see when the agent used knowledge base context in its response (citation/source reference).
- As an admin, I can add or remove documents from the knowledge base without restarting the server.

---

## Architecture

### High-Level Flow
```
User Message
    │
    ▼
┌─────────────────┐
│  Agent Service   │
│  (Ollama LLM)   │
└────────┬────────┘
         │ Tool call: knowledge_base_search(query)
         ▼
┌─────────────────────┐
│  Knowledge Base Tool │
│  (Retrieval Layer)   │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Retrieval Backend   │
│  (Local / Vector DB) │
└─────────────────────┘
         │
         ▼
  Retrieved chunks injected
  into agent prompt context
```

---

## Functional Requirements

### Knowledge Base Tool

1. The tool must accept a search query string and return the top-N most relevant document chunks.
2. The tool must return results with: `content` (text), `source` (file name or doc ID), and `relevance_score`.
3. Default result count: 3 chunks. Configurable via `knowledge_base.max_results`.
4. Maximum chunk size: 1000 characters. Configurable via `knowledge_base.chunk_size`.
5. Chunk overlap: 200 characters (for context continuity during splitting).
6. The tool must handle an empty or missing knowledge base gracefully — return empty results, do not error.

### Retrieval Backend (Phase 1: Local Files)

7. Support a configurable local directory as the document source.
8. Supported file types: `.txt`, `.md`, `.pdf`, `.json`, `.csv`.
9. On startup (or on-demand), index documents by splitting into chunks and generating embeddings.
10. Use a lightweight local embedding model (e.g., `all-MiniLM-L6-v2` via `sentence-transformers`, or Ollama embedding endpoint).
11. Store embeddings in an in-memory vector index (e.g., FAISS or ChromaDB local).
12. Support re-indexing via API endpoint or file watcher.

### Agent Integration

13. The knowledge base tool must be registered with the agent service so it can be invoked during response generation.
14. When the tool returns results, the retrieved content must be injected into the prompt as a `Context:` section before the user message.
15. The agent's system prompt must include instructions to use the knowledge base context when available and cite sources.
16. If no relevant results are found (below a relevance threshold), the agent should respond using general knowledge and indicate that no matching documents were found.

---

## Backend Requirements

### New Configuration

Add to `config.py` / `.env`:

```python
# Knowledge Base
KNOWLEDGE_BASE_ENABLED = os.getenv('KNOWLEDGE_BASE_ENABLED', 'False') == 'True'
KNOWLEDGE_BASE_DIR = os.getenv('KNOWLEDGE_BASE_DIR', './knowledge_base')
KNOWLEDGE_BASE_CHUNK_SIZE = int(os.getenv('KNOWLEDGE_BASE_CHUNK_SIZE', '1000'))
KNOWLEDGE_BASE_CHUNK_OVERLAP = int(os.getenv('KNOWLEDGE_BASE_CHUNK_OVERLAP', '200'))
KNOWLEDGE_BASE_MAX_RESULTS = int(os.getenv('KNOWLEDGE_BASE_MAX_RESULTS', '3'))
KNOWLEDGE_BASE_RELEVANCE_THRESHOLD = float(os.getenv('KNOWLEDGE_BASE_RELEVANCE_THRESHOLD', '0.3'))
KNOWLEDGE_BASE_EMBEDDING_MODEL = os.getenv('KNOWLEDGE_BASE_EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
```

Add to `DEFAULT_CONFIG`:

```python
'knowledge_base': {
    'enabled': KNOWLEDGE_BASE_ENABLED,
    'directory': KNOWLEDGE_BASE_DIR,
    'chunk_size': KNOWLEDGE_BASE_CHUNK_SIZE,
    'chunk_overlap': KNOWLEDGE_BASE_CHUNK_OVERLAP,
    'max_results': KNOWLEDGE_BASE_MAX_RESULTS,
    'relevance_threshold': KNOWLEDGE_BASE_RELEVANCE_THRESHOLD,
    'embedding_model': KNOWLEDGE_BASE_EMBEDDING_MODEL
}
```

### New Service: `services/knowledge_base_service.py`

```python
class KnowledgeBaseService:
    def __init__(self, config: dict):
        """Initialize with knowledge base configuration."""

    def index_documents(self) -> dict:
        """Scan directory, chunk documents, generate embeddings, build index.
        Returns: { 'documents_indexed': int, 'chunks_created': int }"""

    def search(self, query: str, max_results: int = 3) -> list[dict]:
        """Semantic search against indexed chunks.
        Returns: [{ 'content': str, 'source': str, 'relevance_score': float }]"""

    def get_status(self) -> dict:
        """Return index status: document count, chunk count, last indexed timestamp."""
```

### New Endpoints

#### `POST /api/knowledge-base/index`
Trigger re-indexing of the knowledge base directory.

**Success Response:**
```json
{
  "success": true,
  "message": "Knowledge base indexed successfully",
  "data": {
    "documents_indexed": 12,
    "chunks_created": 87,
    "indexed_at": "2026-06-24T14:30:00Z"
  }
}
```

#### `GET /api/knowledge-base/status`
Return current knowledge base status.

**Success Response:**
```json
{
  "success": true,
  "message": "Success",
  "data": {
    "enabled": true,
    "documents_indexed": 12,
    "chunks_created": 87,
    "last_indexed": "2026-06-24T14:30:00Z",
    "directory": "./knowledge_base",
    "embedding_model": "all-MiniLM-L6-v2"
  }
}
```

#### `POST /api/knowledge-base/search`
Direct search endpoint for testing/debugging.

**Request:**
```json
{
  "query": "deployment procedure for production",
  "max_results": 5
}
```

**Success Response:**
```json
{
  "success": true,
  "message": "Success",
  "data": {
    "results": [
      {
        "content": "Production deployment requires approval from...",
        "source": "deployment-guide.md",
        "relevance_score": 0.87
      }
    ],
    "query": "deployment procedure for production",
    "result_count": 1
  }
}
```

### Agent Prompt Integration

When knowledge base is enabled and returns results, prepend to the prompt:

```
Context (from knowledge base — cite sources when using this information):
---
[Source: deployment-guide.md]
Production deployment requires approval from the release manager...
---
[Source: runbook.md]
The standard deployment window is Tuesday and Thursday...
---
```

---

## Frontend Requirements (Future — Out of Scope for Phase 1)

For Phase 1, the knowledge base is configured via `.env` and managed via API. Future UI enhancements:

- Knowledge base status indicator in the config panel (indexed doc count, last indexed)
- Re-index button
- Source citations rendered inline in agent messages (collapsible references)
- Document upload drag-and-drop

---

## New Dependencies

Add to `requirements.txt`:

```
sentence-transformers>=2.2.0
faiss-cpu>=1.7.0
pypdf>=3.0.0
```

---

## File Structure

```
backend/
  services/
    knowledge_base_service.py   # New — retrieval and indexing logic
  routes/
    knowledge_base.py           # New — API endpoints
  knowledge_base/               # New — default document directory
    .gitkeep
```

---

## Testing Requirements

1. **Unit tests** for document chunking (verify chunk size, overlap, boundary handling).
2. **Unit tests** for search relevance (known document should rank highest for matching query).
3. **Integration test**: index a test directory → search → verify results returned with correct schema.
4. **Edge cases**:
   - Empty knowledge base directory → search returns empty, no errors.
   - Unsupported file type in directory → skip gracefully, log warning.
   - Knowledge base disabled → tool is not invoked, agent responds normally.
   - Very large document → chunking completes without memory issues.

---

## Phase 2 Considerations (Future)

- **Vector database backend**: Replace in-memory FAISS with persistent store (ChromaDB, Pinecone, pgvector).
- **AWS Bedrock Knowledge Base**: Swap local retrieval for managed Bedrock KB with S3 data source.
- **Hybrid search**: Combine semantic (embedding) search with keyword (BM25) search for better recall.
- **Document metadata filtering**: Filter by document type, date, tags before semantic search.
- **Conversational retrieval**: Use conversation history to refine search queries automatically.
- **Chunking strategies**: Support paragraph-aware, markdown-header-aware, and recursive chunking.
