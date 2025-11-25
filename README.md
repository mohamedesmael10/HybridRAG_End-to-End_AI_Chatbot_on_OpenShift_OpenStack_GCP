# Production-Grade HybridRAG CI/CD Pipeline on GCP, GitLab, and OpenShift

This project delivers a fully production-ready CI/CD pipeline for the HybridRAG AI platform using GCP Cloud Build → Artifact Registry → Terraform → GitLab CD → OpenShift (OSD). It implements automated build → test → scan → analysis → infrastructure provisioning → deployment across five microservices, integrating Gemini AI, Pub/Sub, Vector DB, and GCS. The system follows strict DevOps and GitOps practices, with full image immutability, Helm-based deployments, infrastructure-as-code, and multi-layer secret management, providing a secure, scalable, and enterprise-grade deployment workflow.
---

## Project Links

This repository focuses on HybridRAG production deployment on OpenShift (OSD).

OSD (OpenShift) Repository:

GitHub: HybridRAG – OSD Deployment

GitLab: HybridRAG – OSD Deployment

The OpenStack version is maintained separately for development and testing:

OpenStack (Development) Repository:

GitHub: HybridRAG – OpenStack Deployment

GitLab: HybridRAG – OpenStack Deployment

---

## Table of contents

1. Overview
2. High-level architecture & flows
3. Components & responsibilities
4. CI — Cloud Build (detailed steps)
5. Terraform infra and `tf_outputs.json`
6. CD — GitLab (`deploy_to_osd`) and variable passing
7. Helm / OpenShift deployment details
8. Repo layout & file tree
9. Environment variables & secrets
10. Prerequisites
11. How to run locally (developer)
12. Secrets Management Strategy
13. Troubleshooting
14. HybridRAG – End-to-End CI/CD Architecture Diagram
15. Notes, authorship, related repos

---

## 1. Overview

This repository contains the **OpenShift (OSD) production-ready deployment** for the HybridRAG AI Chatbot. It integrates:

- **GCP Cloud Build CI** (build, scan, push, Terraform)
- **GitLab CD** (deploy to OSD)
- **OpenShift (OSD)** for runtime
- **Vertex AI** (embeddings + LLM + matching engine)
- **Redis Memory Store** (caching)
- **Pub/Sub + GCS + Firestore** for admin ingestion
- **Terraform** for infra provisioning
- **Security pipeline** (Trivy + SonarCloud)

Two-repo plan:
- **OSD repo** — this repository: Helm charts, OSD CD, docs.
- **OpenStack repo** — separate (development/testing).

---

## 2. High-level architecture & flows

### Text architecture

```
[User Frontend] -> [User Backend (OSD)] -> Redis (VPC) -> Chunk Fn -> Vertex Embedding -> Vertex Matching Engine -> Vertex LLM -> Response

[Admin Frontend] -> GCS Bucket -> Pub/Sub Topic -> Admin Backend (pull) -> Chunk Fn -> Embeddings -> Vertex Matching Engine + Firestore
```

### User flow (runtime)
1. User submits question via frontend.
2. User-backend checks Redis for cached answer.
   - If found: return cached answer.
   - Else: call chunk function to ensure context.
3. Generate embeddings (Vertex AI).
4. Query Vertex Matching Engine for top contexts.
5. Send context + question to Vertex LLM and return answer.
6. Store answer in Redis for caching.

### Admin flow (ingestion)
1. Admin uploads file → stored in GCS.
2. GCS triggers Pub/Sub (OBJECT_FINALIZE) → `bucket-events-topic`.
3. Admin backend pulls subscription, downloads file.
4. Backend calls Chunk Function to slice file into chunks.
5. Generate embeddings for chunks.
6. Upsert embeddings into Vertex Matching Engine index.
7. Save metadata in Firestore.
8. Use Dead-Letter Topic (DLT) for failed processing and retries.

---

## 3. Components & responsibilities

- **User Backend** (FastAPI): RAG orchestration, Redis caching, LLM calls.
- **Admin Backend**: Pub/Sub consumer, orchestrates chunking and indexing.
- **Chunk Function**: Splits files into chunks and returns chunked payloads.
- **Vertex AI**: embeddings and LLM; Matching Engine for vector search.
- **Redis Memory Store**: caches answers.
- **GCS / Pub/Sub / Firestore**: storage, messaging, metadata.
- **Terraform**: provisions GCP resources and outputs required values.
- **Cloud Build**: CI pipeline that builds images, runs scans, runs terraform, and triggers GitLab CD.
- **GitLab**: CD pipeline that deploys to OSD using `oc` + `helm`.

---

## 4. CI — Cloud Build (detailed steps)

**Steps performed by CI**
1. Trivy FS scan per component (fail on HIGH/CRITICAL).
2. Unit tests (`pytest` for Python, `npm test` for Node if present).
3. Build Docker images and `docker save` images to tars for scanning.
4. Trivy image scan of saved tars.
5. Push images to Artifact Registry using `${_ARTIFACT_REG_HOST}/${_PROJECT_ID}/${_REPO}` `${SHORT_SHA}` and `latest` tags.
6. SonarCloud scan and poll quality gate.
7. Terraform (terraform-infra): `init` → `plan` → `apply`; then `terraform output -json > /workspace/tf_outputs.json`.
8. Parse `tf_outputs.json` and trigger GitLab CD via API, passing all necessary variables.

**Post-apply**: Cloud Build writes `/workspace/tf_outputs.json` and the notify step reads that file to extract variables and make the `curl` trigger call.

---

## 5. Terraform infra and `tf_outputs.json`

Define outputs in `terraform-infra/outputs.tf` for all values that downstream CD needs. Example outputs:

```hcl
output "embedding_endpoint" { value = "https://..." }
output "chunk_url" { value = module.chunk_cloud_run.cloud_run_endpoint }
output "chunk_image_full" { value = "${var.artifact_registry_host}/${var.project_id}/${var.repo}/chunk-image:${var.chunk_image_tag}" }
output "deployed_index_id" { value = google_vertex_ai_index_endpoint_deployed_index.rag_deployed.deployed_index_id }
output "project_id" { value = var.project_id }
output "region" { value = var.region }
output "event_subscription_name" { value = google_pubsub_subscription.event_sub.name }
output "event_subscription_path" { value = google_pubsub_subscription.event_sub.id }
output "dlt_subscription_name" { value = google_pubsub_subscription.dlt_sub.name }
output "dlt_subscription_path" { value = google_pubsub_subscription.dlt_sub.id }
```

After apply:
```bash
terraform output -json > /workspace/tf_outputs.json
```

The Cloud Build `notify-gitlab` step parses `tf_outputs.json` using `jq` and builds the variable list sent to GitLab.

---

## 6. CD — GitLab (`deploy_to_osd`) and variable passing

**Triggering GitLab from CI**
```bash
curl -s -X POST "https://gitlab.com/api/v4/projects/${_GITLAB_PROJ_ID}/trigger/pipeline" \
  -F token="${GITLAB_TRIGGER_TOKEN}" \
  -F ref="${_GITLAB_REF:-main}" \
  -F "variables[PROJECT_ID]=${TF_PROJECT_ID}" \
  -F "variables[REGION]=${TF_REGION}" \
  -F "variables[SUBSCRIPTION_ID]=${SUBSCRIPTION_ID}" \
  -F "variables[SUBSCRIPTION_PATH]=${SUBSCRIPTION_PATH}" \
  -F ...other variables...
```

**Inside GitLab job**
- Variables passed via `variables[...]` become environment variables (e.g., `$SUBSCRIPTION_ID`, `$SUBSCRIPTION_PATH`).
- Use `helm upgrade --install` and inject env via `--set env.SUBSCRIPTION_PATH="$SUBSCRIPTION_PATH"`.
- The job typically logs into OpenShift, creates the GCP SA secret from `$GCP_SA_KEY`, resolves image names, and runs Helm installs.

**`only: triggers`** ensures this deploy job runs only when triggered by the CI API.

---

## 7. Helm / OpenShift deployment details

The GitLab `deploy_to_osd` job should:
- Install Helm binary.
- `oc login` to OSD using `$OC_TOKEN` / `$OC_SERVER`.
- Create/update `service-account.json` secret from `$GCP_SA_KEY` (supports base64 or raw JSON input).
- Compute image repo+tag for each microservice (fallback logic provided in the job script).
- Run `helm upgrade --install` for each chart with `--set env.*` values.

**Pub/Sub variables in runtime**
- Provide both `env.SUBSCRIPTION_ID` (short) and `env.SUBSCRIPTION_PATH` (full `projects/<proj>/subscriptions/<sub>`) to the app.
- Application startup should prefer `SUBSCRIPTION_PATH`; if empty, build it from `PROJECT_ID` + `SUBSCRIPTION_ID`.

---

## 8. Repo layout & file tree

```
Admin_Backend/
Admin_Frontend/
Chunk_Function/
helm/
Terraform/
User_Backend/
User_Frontend/
.gitlab-ci.yml
cloudbuild.yaml
README-OSD.md
```

Make sure each Helm chart is under `helm/<chart_name>` and `values.yaml` contains keys that can be populated by the `--set env.*` flags.

---

## 9. Environment variables & secrets

**Required at minimum for CD**
- `PROJECT_ID`, `REGION`, `IMAGE_TAG`, `ARTIFACT_REG_HOST`, `REPO`
- `EMBEDDING_ENDPOINT`, `CHUNK_URL`, `VECTOR_DB_ENDPOINT`, `VECTOR_DB_ENDPOINT_UPSERT`
- `DEPLOYED_INDEX_ID`
- `SUBSCRIPTION_ID`, `SUBSCRIPTION_PATH`
- `GCP_SA_KEY` (used to create the `service-account.json` secret)

**CI-side secrets**
- `SONAR_TOKEN` (Cloud Build via Secret Manager)
- `GITLAB` (Cloud Build via Secret Manager)
- `GITLAB_TRIGGER_TOKEN` (used in Cloud Build to call GitLab)

**GitLab-side secrets**
- `OC_TOKEN`, `OC_SERVER`, optionally `GCP_SA_KEY` if not supplied at runtime

---

## 10. Prerequisites

### Local/Operator
- Docker 20+
- Helm 3.12+
- Python 3.11+
- Node 18+
- Terraform 1.6+
- gcloud SDK
- OpenShift CLI (`oc`)

### GCP
- Enabled APIs: Cloud Build, Artifact Registry, Pub/Sub, Storage, Vertex AI, Secret Manager
- Service accounts with required IAM roles for Terraform and CI

### OpenShift
- Project (namespace) present
- Pull secret for Artifact Registry or ability to create imagePullSecrets

---

## 11. How to run locally (developer)

### User Backend (local dev)
```bash
cd User_Backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

### Admin Frontend (local dev)
```bash
cd Admin_Frontend
npm install
npm run dev
```

### Chunk Function (local run)
```bash
cd Chunk_Function
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py  # or run tests
```
---

## 12. Secrets Management Strategy
- The HybridRAG system uses a multi-layer secured secrets management design, combining:

**1️⃣ Google Cloud Secrets Manager (GCP) — CI Pipeline**

- Used by the Cloud Build CI pipeline, Terraform, and microservices that need runtime secrets during image build or deployment.

**2️⃣ HashiCorp Vault — Runtime Secrets**

- Vault is used mainly for runtime secrets inside OpenShift (OSD) using Vault Agent Injector or External Secrets Operator.

**3️⃣ GitLab Protected CI/CD Variables — CD Pipeline**

- Used only by GitLab CD (OpenShift deployment), not for CI.
---

## 13. Troubleshooting

- **Missing tf_outputs.json** – verify `terraform apply` succeeded and outputs are defined in `outputs.tf`.
- **GitLab trigger fails** – check `GITLAB_TRIGGER_TOKEN`, `_GITLAB_PROJ_ID` and check `/workspace/gitlab_trigger_response.txt` in Cloud Build logs.
- **OpenShift secret creation fails** – validate `GCP_SA_KEY` format and JSON validity.
- **Pub/Sub subscription not reachable** – confirm IAM: subscription/pull requires `roles/pubsub.subscriber` and correct network access.
- **ImagePullBackOff** – ensure OpenShift has a Docker registry secret for Artifact Registry.

---

## 14. HybridRAG – End-to-End CI/CD Architecture Diagram

                    ┌───────────────────────────────────────┐
                    │               Developer                │
                    │            (Push to GitHub)            │
                    └───────────────────────┬───────────────┘
                                            ▼
                         ┌──────────────────────────────┐
                         │       GCP Cloud Build (CI)   │
                         ├──────────────────────────────┤
                         │ - Trivy FS Scan              │
                         │ - Unit Tests (Py + Node)     │
                         │ - Build 5 Microservice Images│
                         │ - Trivy Image Scan           │
                         │ - SonarCloud Analysis        │
                         │ - Terraform Infrastructure   │
                         │   • Vertex AI                │
                         │   • Pub/Sub                  │
                         │   • GCS                      │
                         │   • Artifact Registry        │
                         │ - Export TF Outputs          │
                         │ - Trigger GitLab CD          │
                         └───────────────┬──────────────┘
                                         ▼
                   ┌──────────────────────────────────────────┐
                   │         GitLab CI/CD (Deployment)        │
                   ├──────────────────────────────────────────┤
                   │ - Login to OpenShift                     │
                   │ - Create GCP SA Secret (K8s Secret)      │
                   │ - Inject CI Outputs as env vars          │
                   │ - Deploy via Helm:                       │
                   │     • User Backend                       │
                   │     • User Frontend                      │
                   │     • Admin Backend                      │
                   │     • Admin Frontend                     │
                   │     • Chunk Processor                    │
                   └──────────────┬───────────────────────────┘
                                  ▼
                  ┌────────────────────────────────────────────┐
                  │         OpenShift Dedicated (OSD Prod)      │
                  ├────────────────────────────────────────────┤
                  │ - Runs 5 Microservices                     │
                  │ - Pulls images from Artifact Registry       │
                  │ - Uses secrets injected via GitLab CD       │
                  │ - Autoscaling + Rolling Updates             │
                  └────────────────────────────────────────────┘

---

## 15. Notes, authorship, related repos

**Author:** Mohamed Esmael — DevOps | Cloud | System Admin Engineer

---

© [Mohamed Esmael](https://www.linkedin.com/in/mohamedesmael)
