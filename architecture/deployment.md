# Deployment Guide — Google Cloud Run

## Prerequisites

- `gcloud` CLI authenticated
- Docker installed
- GCP project with Cloud Run and Artifact Registry enabled

## 1. Set variables

```bash
export PROJECT_ID=your-gcp-project-id
export REGION=us-central1
export REPO=regai
```

## 2. Create Artifact Registry repo

```bash
gcloud artifacts repositories create $REPO \
  --repository-format=docker \
  --location=$REGION
```

## 3. Build and push backend

```bash
cd backend
docker build -t $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/backend:latest .
docker push $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/backend:latest
```

## 4. Deploy backend to Cloud Run

```bash
gcloud run deploy regai-backend \
  --image $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/backend:latest \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=...,MONGODB_URI=...,SECRET_KEY=...
```

## 5. Build and push frontend

```bash
cd frontend
docker build -t $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/frontend:latest .
docker push $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/frontend:latest
```

## 6. Deploy frontend to Cloud Run

```bash
gcloud run deploy regai-frontend \
  --image $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/frontend:latest \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars NEXT_PUBLIC_API_URL=https://regai-backend-<hash>-uc.a.run.app/api/v1
```

## Notes

- Arize Phoenix can be deployed as a separate Cloud Run service or used via Arize Cloud.
- Store secrets in Google Secret Manager and reference them with `--set-secrets` instead of `--set-env-vars` for production.
