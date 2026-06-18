from pathlib import Path
import os
import sys

# Ensure backend root is on sys.path so `agent` package resolves
BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from agent.zoning_agent.rag_service import RagService


def main() -> None:
    backend_dir = BACKEND_DIR  # .../backend
    persist = backend_dir / 'agent' / 'zoning_agent' / 'src' / 'chroma_db'
    data_dir = backend_dir / 'agent' / 'zoning_agent' / 'src' / 'data'

    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        print('ERROR: GEMINI_API_KEY not set in environment')
        raise SystemExit(1)

    rag = RagService(persist_dir=persist)
    added = rag.ingest_dir(data_dir)
    print(f'INGEST_COMPLETED added={added} persist={persist}')


if __name__ == '__main__':
    main()
