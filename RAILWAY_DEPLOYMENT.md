# Railway Deployment Guide for TraceRAG Backend

This guide provides step-by-step instructions to deploy the TraceRAG FastAPI backend to Railway.

## Prerequisites

1. Railway account (https://railway.app)
2. GitHub repository pushed (https://github.com/Yashsh101/trace-rag-system)
3. Backend code verified (locally tested)
4. Frontend deployed on Vercel

## Deployment Steps

### 1. Create Railway Project

1. Log in to Railway dashboard
2. Click "New Project"
3. Select "GitHub" to import the repository
4. Select `Yashsh101/trace-rag-system` repository
5. Railway will auto-detect the Dockerfile

### 2. Configure Environment Variables

In the Railway project, set these environment variables:

```
# Core Settings
APP_ENV=production
DEBUG=false

# Database (create or connect existing Postgres with pgvector)
DATABASE_URL=postgresql://user:password@host:port/trace_rag

# API Keys
OPENAI_API_KEY=sk_...
OPENROUTER_API_KEY=rk_...

# Authentication
ADMIN_API_KEYS=your_admin_key_1,your_admin_key_2
USER_API_KEYS=your_user_key_1

# Storage (S3-compatible)
STORAGE_BACKEND=s3
S3_BUCKET=your-bucket-name
S3_REGION=us-east-1
S3_ACCESS_KEY_ID=your_key
S3_SECRET_ACCESS_KEY=your_secret
S3_ENDPOINT=https://s3.amazonaws.com

# Rate Limiting (Redis)
RATE_LIMIT_BACKEND=redis
REDIS_URL=redis://user:password@host:port

# CORS Settings
CORS_ALLOWED_ORIGINS=https://frontend-theta-weld-99.vercel.app

# Port (Railway sets this automatically)
PORT=8000
```

### 3. Database Setup

1. Add Postgres service to Railway
2. Enable pgvector extension:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
3. Copy the CONNECTION_STRING to DATABASE_URL

### 4. Deploy

1. Configure the deployment:
   - Root Directory: `/` (default)
   - Dockerfile: `Dockerfile` (detected automatically)
   - Build command: (left empty - uses Dockerfile)
   - Start command: (uses railway.json config)

2. Click "Deploy"

3. Monitor logs to ensure:
   - Database migrations run successfully
   - Health checks pass
   - No startup errors

### 5. Verify Backend Deployment

```bash
# Health check
curl https://your-railway-backend-url.com/api/v1/health

# Readiness check
curl https://your-railway-backend-url.com/api/v1/health/ready
```

### 6. Connect Frontend to Backend

Once backend is deployed:

1. Get the production backend URL (e.g., `https://trace-rag-prod.up.railway.app`)
2. Redeploy Vercel frontend with:
   - `NEXT_PUBLIC_RAG_API_BASE_URL=https://your-backend-url.com`
   - `NEXT_PUBLIC_RAG_API_KEY=your_user_api_key`

3. Test the connection:
   - Access frontend at https://frontend-theta-weld-99.vercel.app
   - Settings should show "Production" mode
   - Test query and upload features

## Production Checklist

- [ ] Backend deploys without errors
- [ ] Health check responds with 200 OK
- [ ] Database migrations complete
- [ ] CORS allows Vercel frontend domain
- [ ] Environment variables are set correctly
- [ ] Frontend can reach backend API
- [ ] API key authentication works
- [ ] Query endpoint responds correctly
- [ ] Upload endpoint works
- [ ] Rate limiting is active

## Troubleshooting

### Build Failures
- Check logs for Python dependency errors
- Verify requirements.txt is in root directory
- Ensure Dockerfile path is correct

### Runtime Errors
- Check DATABASE_URL format: `postgresql://user:pass@host:port/db`
- Verify API keys are set
- Check CORS_ALLOWED_ORIGINS includes Vercel domain

### Health Check Failures
- Verify database is accessible
- Check if pgvector extension is installed
- Review application logs in Railway dashboard

### Frontend Can't Connect
- Verify backend URL in frontend environment variables
- Check CORS settings allow frontend domain
- Test backend URL directly with curl

## Scaling & Optimization

Once deployed:

1. Enable auto-scaling if needed
2. Configure log aggregation
3. Set up monitoring and alerts
4. Use Railway's metrics dashboard
5. Optimize database queries based on logs

## Support

- Railway Documentation: https://docs.railway.app
- TraceRAG Repository: https://github.com/Yashsh101/trace-rag-system
- Issues: Check GitHub issues for known problems
