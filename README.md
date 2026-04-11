# AlzheiCare AI Assistant — FastAPI Service

Intelligent AI assistant for Alzheimer's disease caregiving support.  
Part of the AlzheiCare platform — runs independently, called internally by NestJS.

---

## Stack

 Component | Technology 
 Framework | FastAPI (Python 3.12) 
 LLM | Groq — `llama-3.3-70b-versatile` 
 STT | Groq — `whisper-large-v3` 
 TTS | Groq — `canopylabs/orpheus-v1-english` 
 LLM Fallback | OpenRouter — `meta-llama/llama-3.3-70b-instruct:free` 
 Web Search | Tavily API 
 Memory | Redis (TTL: 7 days) 
 Auth | JWT (shared secret with NestJS) 
 Streaming | Server-Sent Events (SSE) 

---

## Quick Start

```bash
# 1. Clone and enter directory
cd alzheicare-ai

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        
# 3. Install dependencies
pip install -r requirements.txt

# 4 Edit .env and fill in your API keys

# 5. Start Redis (with Docker)
docker run -d -p 6379:6379 redis:7-alpine

# 6. Run the service
uvicorn main:app --reload --port 8000

# http://localhost:8000/docs

# Start everything (FastAPI + Redis)
docker compose -f docker/docker-compose.yml up -d

# View logs
docker logs alzheicare-ai -f



  