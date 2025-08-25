# App

## Install

```bash
pip install clingo google-genai
pip install fastapi uvicorn
```

## Run

### Backend

```bash
export GEMINI_API_KEY=... # or
export GOOGLE_CLOUD_PROJECT=..
uvicorn server:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```
