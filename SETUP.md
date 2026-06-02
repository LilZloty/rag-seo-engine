# RAG SEO Engine - Setup Guide

> 💡 For the canonical, up-to-date quickstart see **`STACK.md` §14**. This guide adds onboarding context and troubleshooting around that.

## Prerequisites

- **Docker Desktop** (for running Postgres, Redis, Qdrant; also runs the backend + frontend + Celery in full-compose mode)
- **Python 3.12+** (project standard; `pyproject.toml` requires ≥ 3.10 but the Docker image and venvs target 3.12)
- **Node.js 18+** and npm
- **Ollama** (for local LLM — optional if you'll set `LLM_PROVIDER` to a hosted provider in `.env`)
- **Git**

## Step 1: Install Ollama (Free Local LLM)

### Windows
1. Download from https://ollama.ai/download
2. Install and run Ollama
3. Open terminal and pull the default model (`llama3.2:latest` — matches `OLLAMA_MODEL` default in `backend/app/core/config.py`):
```bash
ollama pull llama3.2:latest
```
4. Optional: also pull the Nomic embedding model used in production (`EMBEDDING_PROVIDER=ollama`):
```bash
ollama pull nomic-embed-text
```

### Verify Ollama is running:
```bash
ollama list
```

## Step 2: Start Docker Services

```bash
# Navigate to the project root directory first
cd /path/to/RAG-SEO-ENGINE
docker-compose up -d
```

Verify services are running:
```bash
docker-compose ps
```

For local dev you typically only need the data plane:
```bash
docker compose up -d postgres redis qdrant
```
The full compose stack is 8 services: `postgres`, `redis`, `qdrant`, `backend`, `frontend`, `celery-worker`, `celery-beat`, `celery-flower`. Run them all with `docker compose up -d`. See `STACK.md` §10 for what each does.

## Step 3: Set Up Backend

### Create Virtual Environment
```bash
cd backend
python -m venv venv
venv\Scripts\activate
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Initialize Database
```bash
python -c "from app.db.session import engine; from app.models.product import Base; Base.metadata.create_all(bind=engine)"
```

## Step 4: Set Up Frontend

```bash
cd frontend
npm install
```

## Step 5: Start Services

### Terminal 1 - Backend
```bash
cd backend
venv\Scripts\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Terminal 2 - Frontend
```bash
cd frontend
npm run dev
```

## Step 6: Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## Troubleshooting

### Port Already in Use
If port 8000 or 3000 is already in use, change in the startup command:
```bash
# Backend on port 8001
uvicorn app.main:app --reload --port 8001

# Frontend on port 3001
npm run dev -- -p 3001
```

### Ollama Not Responding
Make sure Ollama is running:
```bash
# On Windows
# Check Ollama is running in system tray
# Or restart from: Start Menu > Ollama
```

### Docker Services Not Starting
```bash
docker-compose down
docker-compose up -d --force-recreate
```

### Database Connection Issues
```bash
docker-compose logs postgres
```

### Import Errors in Python
Make sure you activated the virtual environment:
```bash
cd backend
venv\Scripts\activate
```

## Optional: Install Playwright for Scraping

```bash
cd backend
playwright install chromium
```

## Testing the Connection

1. Open http://localhost:3000 in your browser
2. Click "Sincronizar Shopify" to fetch products
3. Click "Editar" on any product
4. Click "Generar Contenido con IA" (make sure Ollama is running)
5. Edit the generated content if needed
6. Click "Publicar en Shopify" to push to your store

## Memory Optimization (15.9GB RAM)

If you experience memory issues, you can:

1. **Reduce Docker memory limits** (edit docker-compose.yml):
```yaml
postgres:
  command:
    - "postgres"
    - "-c" "shared_buffers=128MB"  # Reduced from 256MB
```

2. **Close other applications** while running the app

3. **Use smaller LLM model**:
```bash
ollama pull llama3.2:3b
# Then update OLLAMA_MODEL in backend/.env (not config.py — it's a settings env var)
```

## Production Deployment Guide

When ready to scale to a production server:

1. Get a cloud VPS (Hetzner, DigitalOcean, AWS)
2. Install Docker and Docker Compose
3. Upload the code via Git
4. Set environment variables in production (`backend/.env`)
5. Use HTTPS (Let's Encrypt)
6. For hosted LLM, set `LLM_PROVIDER` to one of: `anthropic` / `openai` / `grok` / `perplexity` / `kimi` / `minimax` / `mistral`. See `STACK.md` §8 for the provider/model matrix.

---

**Need Help?**
- Check API docs: http://localhost:8000/docs
- Check logs in terminal windows
- Ensure Docker services are running: `docker-compose ps`
