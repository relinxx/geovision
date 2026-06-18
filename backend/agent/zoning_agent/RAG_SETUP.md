# RAG System Setup Guide

## Overview

The RAG (Retrieval-Augmented Generation) system uses ChromaDB to store zoning documents and OpenAI to generate intelligent answers to zoning questions.

## Current Status

✅ **RAG Service Created**: `rag_service.py` - Handles RAG operations  
✅ **FastAPI Integration**: Endpoint `/rag/zoning/ask` now uses RAG service  
⚠️ **Dependencies**: Need to install RAG dependencies  
⚠️ **ChromaDB**: Need to initialize database with PDFs  
⚠️ **OpenAI API Key**: Need to set environment variable  

## Setup Steps

### 1. Install RAG Dependencies

The RAG dependencies are in `zoning_agent/pyproject.toml`. Install them:

```bash
cd backend/agent/zoning_agent
poetry install
# Or with pip:
pip install langchain-chroma langchain-openai pdfplumber python-dotenv
```

### 2. Set OpenAI API Key

Create a `.env` file in the backend directory or set environment variable:

```bash
# In backend/.env
OPENAI_API_KEY=your-api-key-here

# Or export in shell:
export OPENAI_API_KEY=your-api-key-here
```

### 3. Initialize ChromaDB

Run the initialization script to process PDFs and create the vector database:

```bash
cd backend
python -m agent.zoning_agent.init_rag
```

This will:
- Process all PDFs in `backend/agent/zoning_agent/src/data/`
- Extract text and chunk it
- Create embeddings using OpenAI
- Store in ChromaDB at `backend/agent/zoning_agent/chroma_db/`

### 4. Verify Setup

Test the RAG endpoint:

```bash
curl -X POST http://localhost:8000/rag/zoning/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the height restrictions?", "apn": null, "context": {}}'
```

## How It Works

1. **User asks question** → Frontend sends to `/rag/zoning/ask`
2. **RAG Service**:
   - Retrieves relevant document chunks from ChromaDB using semantic search
   - Combines with parcel context (if parcel selected)
   - Sends to OpenAI LLM with context
3. **LLM generates answer** based on retrieved documents
4. **Response returned** to frontend

## Fallback Behavior

If RAG is not configured:
- ✅ System still works
- ✅ Returns fallback response with parcel information
- ✅ Shows helpful message about setup requirements

## Troubleshooting

### "RAG dependencies not available"
- Install: `pip install langchain-chroma langchain-openai pdfplumber python-dotenv`

### "OPENAI_API_KEY not set"
- Set environment variable or create `.env` file

### "ChromaDB not found"
- Run initialization: `python -m agent.zoning_agent.init_rag`

### "No chunks retrieved"
- ChromaDB exists but is empty
- Re-run initialization script

### Import errors
- Make sure you're running from the backend directory
- Check that `agent.zoning_agent.rag_service` can be imported

## Files

- `rag_service.py` - Main RAG service class
- `init_rag.py` - Script to initialize ChromaDB
- `src/data/` - PDF documents directory
- `chroma_db/` - Vector database (created after initialization)

## Next Steps

1. Install dependencies
2. Set OpenAI API key
3. Initialize ChromaDB
4. Test in frontend chat interface

---

*The RAG system will automatically use fallback responses if not fully configured, so the chat will always work.*

