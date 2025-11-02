# 🚀 How to Run - Background Processing System

## ⚡ Quick Start (Copy & Paste)

### Step 1: Install Redis (One-time setup)

```bash
# macOS
brew install redis
brew services start redis

# Ubuntu/Debian
sudo apt-get update
sudo apt-get install redis-server
sudo systemctl start redis
sudo systemctl enable redis

# Verify Redis is running
redis-cli ping  # Should return: PONG ✅
```

### Step 2: Install Dependencies (One-time setup)

```bash
# Install Python packages
pip install -r requirements.txt

# Run database migrations
python manage.py migrate
```

### Step 3: Run the System (3 Terminals)

Open **3 terminal windows** in your project directory:

#### 🔷 Terminal 1: Django Server
```bash
python manage.py runserver
```
✅ Keep this running - Django API server

#### 🔶 Terminal 2: Celery Worker
```bash
./start_celery.sh
```
OR manually:
```bash
# macOS/Linux
celery -A hero_one worker --loglevel=info

# Windows
celery -A hero_one worker --loglevel=info --pool=solo
```
✅ Keep this running - Background task processor

#### 🔹 Terminal 3: Test (Optional)
```bash
python test_background_processing.py
```
✅ Run this to test the system

---

## 📊 Expected Output

### Terminal 1 (Django)
```
Django version 5.2.7, using settings 'hero_one.settings'
Starting development server at http://127.0.0.1:8000/
Quit the server with CONTROL-C.
```

### Terminal 2 (Celery)
```
 -------------- celery@YourMachine v5.4.0
---- **** ----- 
--- * ***  * -- Darwin-23.0.0-arm64-arm-64bit 2024-11-02 13:30:00
-- * - **** --- 
- ** ---------- [config]
- ** ---------- .> app:         hero_one:0x104e3a4d0
- ** ---------- .> transport:   redis://localhost:6379/0
- ** ---------- .> results:     redis://localhost:6379/0
- *** --- * --- .> concurrency: 8 (prefork)
-- ******* ---- .> task events: OFF
--- ***** ----- 
 -------------- [queues]
                .> celery           exchange=celery(direct) key=celery
                
[tasks]
  . hero_one_api.tasks.process_content_generation_task

[2024-11-02 13:30:00,000: INFO/MainProcess] Connected to redis://localhost:6379/0
[2024-11-02 13:30:00,000: INFO/MainProcess] mingle: searching for neighbors
[2024-11-02 13:30:01,000: INFO/MainProcess] mingle: all alone
[2024-11-02 13:30:01,000: INFO/MainProcess] celery@YourMachine ready.
```

### Terminal 3 (Test)
```
🧪 Testing Background Processing with Celery
============================================================

✅ Found test file: sample.mp3
✅ Using user: user@example.com
✅ Using client: Test Client

📝 Creating test job...
✅ Job created: 123e4567-e89b-12d3-a456-426614174000

🚀 Queuing task for background processing...
✅ Task queued with ID: abc123...

📊 Monitoring progress (polling every 2 seconds)...
------------------------------------------------------------
[  2s] ██░░░░░░░░░░░░░░░░░░  10% | Status: processing
[  5s] ████░░░░░░░░░░░░░░░░  20% | Status: processing
[ 12s] ████████░░░░░░░░░░░░  40% | Status: processing
[ 25s] ██████████████░░░░░░  70% | Status: processing
[ 30s] ██████████████████░░  90% | Status: processing
[ 32s] ████████████████████ 100% | Status: completed
------------------------------------------------------------

✅ Processing completed successfully!
```

---

## 🔍 Verify Everything is Working

### 1. Check Redis
```bash
redis-cli ping
# Should return: PONG
```

### 2. Check Celery Worker
```bash
celery -A hero_one inspect active
# Should show active tasks or empty list
```

### 3. Check Django
```bash
curl http://localhost:8000/api/
# Should return API response
```

---

## 🛠️ Troubleshooting

### ❌ "redis.exceptions.ConnectionError"
**Problem:** Redis is not running

**Solution:**
```bash
# Check if Redis is running
redis-cli ping

# Start Redis
brew services start redis  # macOS
sudo systemctl start redis  # Linux

# Or start manually
redis-server
```

### ❌ "ModuleNotFoundError: No module named 'celery'"
**Problem:** Dependencies not installed

**Solution:**
```bash
pip install -r requirements.txt
```

### ❌ Tasks not processing
**Problem:** Celery worker not running

**Solution:**
```bash
# Check if worker is running
celery -A hero_one inspect active

# Start worker
./start_celery.sh
```

### ❌ "Job not found" or "No users found"
**Problem:** Database not set up

**Solution:**
```bash
# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Create a test client via Django admin or API
```

---

## 📝 API Testing with cURL

### 1. Create User & Get Token
```bash

### 1. Upload File (Background Processing)
```bash
curl -X POST http://localhost:8000/api/transcribe/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@sample.mp3" \
  -F "client_id=1"
```

**Response:**
```json
{
  "message": "File uploaded successfully. Processing in background.",
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "pending"
}
```

### 2. Check Progress
```bash
curl http://localhost:8000/api/transcribe/job/123e4567-e89b-12d3-a456-426614174000 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response (Processing):**
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "processing",
  "progress": 45
}
```

**Response (Completed):**
```json
{
  "job_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "completed",
  "progress": 100,
  "result": {
    "caption": "...",
    "description": "...",
    "hashtags": "..."
  }
}
```

---

## 🎯 Complete Workflow

```
1. Start Redis       ✅ redis-cli ping
   ↓
2. Start Django      ✅ python manage.py runserver
   ↓
3. Start Celery      ✅ ./start_celery.sh
   ↓
4. Upload File       ✅ POST /api/transcribe/upload
   ↓
5. Get job_id        ✅ Instant response
   ↓
6. Poll Status       ✅ GET /api/transcribe/job/{job_id} every 2s
   ↓
7. Show Progress     ✅ Update UI: 0% → 10% → 40% → 70% → 100%
   ↓
8. Get Result        ✅ Display caption, description, hashtags
```

---

## 📦 What You Need

### Required Services (Must be running)
1. ✅ **Redis** - Message broker
2. ✅ **Django** - API server
3. ✅ **Celery Worker** - Background processor

### Optional
4. **Flower** - Celery monitoring UI (optional)
   ```bash
   pip install flower
   celery -A hero_one flower
   # Visit http://localhost:5555
   ```
---

## 🚀 Production Checklist

- [ ] Redis running as system service
- [ ] Celery worker managed by Supervisor/systemd
- [ ] Django behind Gunicorn/uWSGI
- [ ] Nginx reverse proxy
- [ ] Environment variables configured
- [ ] Logging configured
- [ ] Monitoring set up (Flower, Sentry)
- [ ] Redis persistence enabled
- [ ] Celery worker auto-restart on failure

See `CELERY_SETUP.md` for production deployment guide.

---

## 🎉 You're All Set!

Your background processing system is ready to use. The workflow is:

1. **User uploads** → Instant response with job_id
2. **Backend processes** → Transcribes & generates content
3. **Frontend polls** → Every 2 seconds for progress
4. **User sees** → Real-time progress bar (0-100%)
5. **Results ready** → Display caption, description, hashtags

**Need help?** Check the documentation:
- `QUICK_START.md` - Quick setup guide
- `CELERY_SETUP.md` - Detailed configuration
- `README_BACKGROUND_PROCESSING.md` - Complete architecture
- `frontend_examples/` - React & JavaScript examples

**Happy coding! 🚀**
