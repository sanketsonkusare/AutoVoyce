# Railway Deployment Guide

This guide will help you deploy both the frontend and backend separately on Railway.

## Prerequisites

1. Railway account (sign up at https://railway.app)
2. Railway CLI installed (optional): `npm i -g @railway/cli`
3. All environment variables ready

---

## Backend Deployment

### Step 1: Create Backend Service

1. Go to Railway dashboard
2. Click "New Project"
3. Select "Empty Project"
4. Click "Add Service" → "GitHub Repo" (or "Empty Service" if deploying manually)
5. Select your repository
6. **Important**: Set the **Root Directory** to `backend` in the service settings

### Step 2: Configure Backend Service

**Build Settings:**

- **Root Directory**: `backend`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python -m uvicorn src.main.main:app --host 0.0.0.0 --port $PORT`

**Or use Railway.json (already configured):**

- Railway will automatically detect `backend/railway.json` and use those settings

### Step 3: Set Backend Environment Variables

In Railway dashboard → Backend Service → Variables, add:

```
GOOGLE_API_KEY=your_google_api_key
GROQ_API_KEY=your_groq_api_key
SERP_API_KEY=your_serp_api_key
SEARCH_LIMIT=10
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX_NAME=your_index_name
PINECONE_HOST_URL=your_pinecone_host_url
ELEVENLABS_API_KEY=your_elevenlabs_api_key
```

### Step 4: Get Backend URL

After deployment, Railway will provide a URL like:

- `https://your-backend-service.up.railway.app`

**Copy this URL** - you'll need it for the frontend!

---

## Frontend Deployment

### Step 1: Create Frontend Service

1. In the same Railway project (or create a new one)
2. Click "Add Service" → "GitHub Repo"
3. Select the same repository
4. **Important**: Set the **Root Directory** to `frontend` in the service settings

### Step 2: Configure Frontend Service

**Build Settings:**

- **Root Directory**: `frontend`
- **Build Command**: `npm install && npm run build`
- **Start Command**: `npm start`

**Or use Railway.json (already configured):**

- Railway will automatically detect `frontend/railway.json` and use those settings

### Step 3: Set Frontend Environment Variables

In Railway dashboard → Frontend Service → Variables, add:

```
NEXT_PUBLIC_API_URL=https://your-backend-service.up.railway.app
NEXT_PUBLIC_ELEVENLABS_VOICE_ID=your_voice_id (optional, defaults to JBFqnCBsd6RMkjVDRZzb)
NODE_ENV=production
```

**Important**: Replace `https://your-backend-service.up.railway.app` with your actual backend URL from Step 4 above.

---

## Update Backend CORS Settings

Before deploying, update the backend CORS settings to allow your frontend domain.

### Update `backend/src/main/main.py`:

```python
# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Local development
        "https://your-frontend-service.up.railway.app",  # Railway frontend URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Replace `https://your-frontend-service.up.railway.app` with your actual Railway frontend URL after deployment.

---

## Deployment Steps Summary

### Backend:

1. ✅ Create backend service in Railway
2. ✅ Set root directory to `backend`
3. ✅ Add all environment variables
4. ✅ Deploy (Railway auto-detects railway.json)
5. ✅ Copy backend URL

### Frontend:

1. ✅ Create frontend service in Railway
2. ✅ Set root directory to `frontend`
3. ✅ Add `NEXT_PUBLIC_API_URL` with backend URL
4. ✅ Update backend CORS with frontend URL
5. ✅ Redeploy backend (if CORS was updated)
6. ✅ Deploy frontend

---

## Build & Start Commands Reference

### Backend:

- **Build**: `pip install -r requirements.txt`
- **Start**: `python -m uvicorn src.main.main:app --host 0.0.0.0 --port $PORT`

### Frontend:

- **Build**: `npm install && npm run build`
- **Start**: `npm start`

---

## Troubleshooting

### Backend Issues:

1. **Port binding error**: Make sure you're using `$PORT` environment variable (Railway provides this)
2. **Module not found**: Ensure `requirements.txt` has all dependencies
3. **CORS errors**: Update CORS settings in `main.py` with your frontend URL

### Frontend Issues:

1. **API connection errors**: Check `NEXT_PUBLIC_API_URL` is set correctly
2. **Build failures**: Check Node.js version (Railway auto-detects, but you can specify in `package.json`)
3. **Environment variables not working**: Make sure `NEXT_PUBLIC_` prefix is used for client-side variables

### General:

1. **Check logs**: Railway dashboard → Service → Deployments → View Logs
2. **Redeploy**: If environment variables change, you may need to redeploy
3. **Health checks**: Backend should respond at `/` endpoint

---

## Environment Variables Checklist

### Backend (Required):

- [ ] `GOOGLE_API_KEY`
- [ ] `GROQ_API_KEY`
- [ ] `SERP_API_KEY`
- [ ] `PINECONE_API_KEY`
- [ ] `PINECONE_INDEX_NAME`
- [ ] `PINECONE_HOST_URL`
- [ ] `ELEVENLABS_API_KEY`
- [ ] `SEARCH_LIMIT` (optional, defaults to 10)

### Frontend (Required):

- [ ] `NEXT_PUBLIC_API_URL` (your backend Railway URL)
- [ ] `NEXT_PUBLIC_ELEVENLABS_VOICE_ID` (optional)

---

## Quick Deploy Commands (Using Railway CLI)

If you have Railway CLI installed:

```bash
# Backend
cd backend
railway login
railway init
railway up

# Frontend (in new terminal)
cd frontend
railway login
railway init
railway up
```

---

## Post-Deployment

1. Test backend health: `https://your-backend.up.railway.app/`
2. Test frontend: `https://your-frontend.up.railway.app`
3. Verify API connection from frontend
4. Test voice features (may need HTTPS for microphone access)

---

## Notes

- Railway automatically provides `$PORT` environment variable
- Railway uses Nixpacks builder by default (auto-detects Python/Node.js)
- Both services can be in the same Railway project or separate projects
- Railway provides free tier with generous limits
- Custom domains can be added in Railway dashboard
