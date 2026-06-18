# Orchestrator Quick Start Guide

## 🚀 5-Minute Setup

### Step 1: Mount Router (30 seconds)

Edit `backend/main.py` and add these lines:

```python
# Add import at the top (around line 15)
from routers import orchestrator

# Mount router after CORS middleware (around line 35)
app.include_router(orchestrator.router)
```

**Complete example**:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import orchestrator  # ← ADD THIS

app = FastAPI(title="GeoVision Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(orchestrator.router)  # ← ADD THIS

# ... rest of existing code ...
```

### Step 2: Start Server (10 seconds)

```bash
cd backend
poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Step 3: Test (2 minutes)

Open browser: `http://localhost:8000/docs`

Look for these new endpoints:
- `POST /orchestrator/plan`
- `GET /orchestrator/status/{job_id}`
- `GET /orchestrator/result/{job_id}`

### Step 4: Run Test Job (2 minutes)

```bash
# Create job
curl -X POST "http://localhost:8000/orchestrator/plan" \
  -H "Content-Type: application/json" \
  -d '{"parcel_ids": ["4042700100"], "enable_spatial": false}'

# Copy job_id from response, then check status
curl "http://localhost:8000/orchestrator/status/YOUR_JOB_ID_HERE"

# Wait for completion, then get result
curl "http://localhost:8000/orchestrator/result/YOUR_JOB_ID_HERE"
```

## ✅ Done!

Your orchestrator is now running. See `ORCHESTRATOR_IMPLEMENTATION_SUMMARY.md` for full documentation.

## 🔍 Quick Test Script

Save as `test_orchestrator.sh`:

```bash
#!/bin/bash

echo "Creating orchestration job..."
RESPONSE=$(curl -s -X POST "http://localhost:8000/orchestrator/plan" \
  -H "Content-Type: application/json" \
  -d '{"parcel_ids": ["4042700100", "4042700200"], "enable_spatial": false}')

JOB_ID=$(echo $RESPONSE | grep -o '"job_id":"[^"]*' | cut -d'"' -f4)
echo "Job created: $JOB_ID"

echo ""
echo "Polling status..."
while true; do
  STATUS=$(curl -s "http://localhost:8000/orchestrator/status/$JOB_ID")
  PROGRESS=$(echo $STATUS | grep -o '"progress":[0-9]*' | cut -d':' -f2)
  STATE=$(echo $STATUS | grep -o '"status":"[^"]*' | cut -d'"' -f4)
  STAGE=$(echo $STATUS | grep -o '"stage":"[^"]*' | cut -d'"' -f4)
  
  echo "[$STATE] Progress: $PROGRESS% - Stage: $STAGE"
  
  if [ "$STATE" = "completed" ]; then
    echo ""
    echo "Job completed! Getting result..."
    curl -s "http://localhost:8000/orchestrator/result/$JOB_ID" | python -m json.tool
    break
  fi
  
  if [ "$STATE" = "failed" ]; then
    echo "Job failed!"
    echo $STATUS | python -m json.tool
    break
  fi
  
  sleep 2
done
```

Run with:
```bash
chmod +x test_orchestrator.sh
./test_orchestrator.sh
```

## 📊 Expected Output

```
Creating orchestration job...
Job created: a1b2c3d4-e5f6-7890-abcd-ef1234567890

Polling status...
[running] Progress: 0% - Stage: environment
[running] Progress: 15% - Stage: environment
[running] Progress: 30% - Stage: zoning
[running] Progress: 45% - Stage: zoning
[running] Progress: 60% - Stage: merge
[running] Progress: 80% - Stage: merge
[completed] Progress: 100% - Stage: completed

Job completed! Getting result...
{
  "status": "completed",
  "result": {
    "stage": "merge",
    "parcel_count": 2,
    "unified_results": [...]
  }
}
```

## 🐛 Troubleshooting

**Import Error**: Make sure you're in the `backend` directory

**404 on endpoints**: Router not mounted correctly in `main.py`

**500 errors**: Check logs with `tail -f logs/app.log`

**Job not found**: Server restarted (jobs are in-memory only)

## 📚 Next Steps

1. ✅ Test with your actual parcel IDs
2. ✅ Integrate with frontend
3. ✅ Monitor logs for performance
4. ✅ Read full documentation in `ORCHESTRATOR_IMPLEMENTATION_SUMMARY.md`
