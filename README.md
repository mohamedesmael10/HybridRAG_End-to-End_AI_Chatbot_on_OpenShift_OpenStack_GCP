# Production-Grade HybridRAG CI/CD Pipeline on GCP, GitLab, and OpenShift

- This project delivers a fully production-ready CI/CD pipeline for the HybridRAG AI platform using GCP Cloud Build → Artifact Registry → Terraform → GitLab CD → OpenShift (OSD). It implements automated build → test → scan → analysis → infrastructure provisioning → deployment across five microservices, integrating Gemini AI, Pub/Sub, Vector DB, and GCS. The system follows strict DevOps and GitOps practices, with full image immutability, Helm-based deployments, infrastructure-as-code, and multi-layer secret management, providing a secure, scalable, and enterprise-grade deployment workflow.
---

## Architecture Diagram

![Screenshots](https://github.com/mohamedesmael10/HybridRAG_End-to-End_AI_Chatbot_on_OpenShift_OpenStack_GCP/blob/main/Screenshots/0.gif)

![Screenshots](https://github.com/mohamedesmael10/HybridRAG_End-to-End_AI_Chatbot_on_OpenShift_OpenStack_GCP/blob/main/Screenshots/00.svg)
---

## Two-repo strategy

- `hybridrag-osd` (this repo) — production deployment, Helm charts, `.gitlab-cd.yml` (CD), docs for OSD deployment and runbooks.
- `hybridrag-openstack` — development/testing deployment, dev CI/CD and any OpenStack-specific Terraform/helm differences.

**Why not a single repo?**
- Production (OSD) has stricter policies (immutable images, stricter scanning, protected branches). Keeping prod repo focused reduces accidental changes.
- Development repo can have experimental changes, dev-only dependencies, and faster iteration.

This repository focuses on HybridRAG production deployment on OpenShift (OSD).

### OSD (OpenShift) Repository:

 . [GitHub: HybridRAG – OSD Deployment](https://github.com/mohamedesmael10/HybridRAG_End-to-End_AI_Chatbot_on_OpenShift_OpenStack_GCP/tree/main)

 . [GitLab: HybridRAG – OSD Deployment](https://gitlab.com/mohamedesmael10/hybridrag_end-to-end_ai_chatbot_on_openshift_openstack_gcp)

The OpenStack version is maintained separately for development and testing:

### OpenStack (Development) Repository:

 . [GitHub: HybridRAG – OpenStack Deployment](https://github.com/mohamedesmael10/HybridRAG_End-to-End_AI_Chatbot_on_OpenShift_OpenStack_GCP/tree/develop)

 . [GitLab: HybridRAG – OpenStack Deployment](https://gitlab.com/mohamedesmael10/hybridrag_end-to-end_ai_chatbot_on_openshift_openstack_gcp/-/tree/develop?ref_type=heads)

---

## Table of Contents

| #  | Section                                              |
| -- | --------------------------------------------------   |
| 1  | Overview                                             |
| 2  | High-level architecture & flows                      |
| 3  | Components & responsibilities                        |
| 4  | CI — Cloud Build (detailed steps)                    |
| 5  | CD — GitLab (`deploy_to_osd`) and variable passing   |
| 6  | Helm / OpenShift deployment details                  |
| 7  | Repo layout & file tree                              | 
| 8  | Terraform: `terraform-bootstrap` vs `terraform-infra`|     
| 9  | System Architecture Overview                         |
| 10 | Environment variables & secrets                      |
| 11 | Prerequisites                                        |
| 12 | How to run locally (developer)                       |
| 13 | Secrets Management Strategy                          |
| 14 | Troubleshooting                                      |
| 15 | HybridRAG – End-to-End CI/CD Architecture Diagram    |
| 16 | Notes, authorship, related repos                     |

---

## 1. Overview

| Feature         | Description                                    |
| --------------- | ---------------------------------------------- |
| CI              | GCP Cloud Build (build, scan, push, Terraform) |
| CD              | GitLab (deploy to OSD)                         |
| Runtime         | OpenShift (OSD)                                |
| AI Services     | Vertex AI (embeddings + LLM + matching engine) |
| Caching         | Redis Memory Store                             |
| Admin Ingestion | Pub/Sub + GCS + Firestore                      |
| Infra           | Terraform                                      |
| Security        | Trivy + SonarCloud                             |

| Repo           | Purpose                                 |
| -------------- | --------------------------------------- |
| OSD repo       | Helm charts, OSD CD, docs (this repo)   |
| OpenStack repo | Separate development/testing repository |

This repo is the **OSD/production** deployment for the HybridRAG AI Chatbot. CI runs on **Google Cloud Build** (build, scan, push, terraform); after `terraform-infra` completes the CI triggers a **GitLab** pipeline that performs the CD to **OpenShift (OSD)** using `oc` + `helm`.

The system uses **Vertex AI** (embeddings + LLM + matching engine), **Redis Memory Store**, **GCS / Pub/Sub** for ingestion, and **Firestore** for metadata.

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
**High-level pipeline (order):**
1. Trivy filesystem scan (per folder) — fail on HIGH/CRITICAL unless you intentionally `allow_failure`.
2. Unit tests: Python (`pytest`) and Node (`npm test`) when detected.
3. Build Docker images + `docker save` → tar outputs (for offline/trivy scanning).
4. Trivy image scan on tars.
5. Push images to Artifact Registry (`${_ARTIFACT_REG_HOST}/${_PROJECT_ID}/${_REPO}` with `${SHORT_SHA}` and `latest`).
6. SonarCloud analysis (use `-Dsonar.login` or `-Dsonar.token=<value>` correctly).
7. Terraform (terraform-infra) `init` → `plan` → `apply`.
8. `terraform output -json > /workspace/tf_outputs.json`.
9. Notify/trigger GitLab CD with curl and pass all necessary variables.

![Screenshots](https://github.com/mohamedesmael10/HybridRAG_End-to-End_AI_Chatbot_on_OpenShift_OpenStack_GCP/blob/main/Screenshots/(1).png)

![Screenshots](https://github.com/mohamedesmael10/HybridRAG_End-to-End_AI_Chatbot_on_OpenShift_OpenStack_GCP/blob/main/Screenshots/(3).png)


![Screenshots](https://github.com/mohamedesmael10/HybridRAG_End-to-End_AI_Chatbot_on_OpenShift_OpenStack_GCP/blob/main/Screenshots/(4).png)


---

## 5. CD — GitLab `deploy_to_osd` (detailed)

**What GitLab CD must do**:
- Receive variables from Cloud Build (via GitLab trigger) and map them to `$PROJECT_ID`, `$REGION`, `$EMBEDDING_ENDPOINT`, `$CHUNK_URL`, `$VECTOR_DB_ENDPOINT`, `$CHUNK_IMAGE_FULL`, `$IMAGE_TAG` and Pub/Sub `SUBSCRIPTION_PATH` etc.
- `oc login` into OSD (using `$OC_TOKEN` & `$OC_SERVER`).
- Create/update `service-account.json` secret from `$GCP_SA_KEY` (supports raw JSON or base64).
- Resolve image names (fallbacks included) and run `helm upgrade --install` on the 4–5 charts.

**Ensure**:
- Helm is installed and the version is compatible with your charts (`3.12+` recommended).
- App charts accept `--set env.*` values for the runtime environment.
- Provide both `SUBSCRIPTION_ID` and `SUBSCRIPTION_PATH` — application should use `SUBSCRIPTION_PATH` if present.

![Screenshots](https://github.com/mohamedesmael10/HybridRAG_End-to-End_AI_Chatbot_on_OpenShift_OpenStack_GCP/blob/main/Screenshots/(12).png)


![Screenshots](https://github.com/mohamedesmael10/HybridRAG_End-to-End_AI_Chatbot_on_OpenShift_OpenStack_GCP/blob/main/Screenshots/(13).png)


---

## 6. Helm / OpenShift deployment details

The GitLab `deploy_to_osd` job should:
- Install Helm binary.
- `oc login` to OSD using `$OC_TOKEN` / `$OC_SERVER`.
- Create/update `service-account.json` secret from `$GCP_SA_KEY` (supports base64 or raw JSON input).
- Compute image repo+tag for each microservice (fallback logic provided in the job script).
- Run `helm upgrade --install` for each chart with `--set env.*` values.

Your Helm charts should have `values.yaml` entries for everything you pass via `--set` so they remain visible: e.g.

```yaml
image:
  repository: ""
  tag: ""
env:
  EMBEDDING_ENDPOINT: ""
  CHUNK_URL: ""
  VECTOR_DB_ENDPOINT: ""
  DEPLOYED_INDEX_ID: ""
  GOOGLE_APPLICATION_CREDENTIALS: "/app/keys/service-account.json"
```

![Screenshots](https://github.com/mohamedesmael10/HybridRAG_End-to-End_AI_Chatbot_on_OpenShift_OpenStack_GCP/blob/main/Screenshots/(16).png)

---

## 7. Repo layout & file tree

```
Admin_Backend/
Admin_Frontend/
Chunk_Function/
helm/
Terraform/
User_Backend/
User_Frontend/
.gitlab-cd.yml
cloudbuild.yaml
README-OSD.md
```

Make sure each Helm chart is under `helm/<chart_name>` and `values.yaml` contains keys that can be populated by the `--set env.*` flags.

---

## 8. Terraform: `terraform-bootstrap` vs `terraform-infra`

**Bootstrap** (`terraform-bootstrap`): creates Cloud Build triggers, service accounts used by CI, and infrastructure needed to run the CI pipeline (artifact registry IAM, service account for Cloud Build, Secret Manager secrets).

**Infra** (`terraform-infra`): creates runtime resources — Vertex AI indexes and endpoints, Pub/Sub topics & subscriptions, GCS buckets, Redis instance, Cloud Run or GKE / Cloud Functions for the chunk function, and outputs required by CD.

**Outputs**: ensure `terraform-infra/outputs.tf` exposes all variables the CD needs (see below). After `apply` the CI step should run:

```bash
terraform output -json > /workspace/tf_outputs.json
```

And `notify-gitlab` extracts values using `jq`.

Example outputs to expose:

```hcl
output "embedding_endpoint" { value = google_vertex_ai_endpoint.embedding.endpoint }
output "chunk_url" { value = google_cloud_run_service.chunk.status[0].url }
output "chunk_image_full" { value = "${var.artifact_registry_host}/${var.project_id}/${var.repo}/chunk-image:${var.chunk_image_tag}" }
output "deployed_index_id" { value = google_vertex_ai_index.deployed_index_id }
output "event_subscription_path" { value = google_pubsub_subscription.event_sub.id }
output "dlt_subscription_path" { value = google_pubsub_subscription.dlt_sub.id }
```

---

# 9. System Architecture Overview

## 1. User — RAG + Redis + LLM + Vector DB Service

This is the core intelligence layer of the platform. It handles query understanding → retrieval → LLM response generation → caching.

###  Features

* **Full RAG Pipeline**

  * Cleans and normalizes user input
  * Generates embeddings via Google Vertex AI
  * Searches vector DB for top-k similar chunks
  * Produces final LLM responses using Gemini models
* **Redis Caching Layer**

  * Each query hashed using SHA-256
  * Responses cached with TTL
  * Cache stored and returned as JSON
* **Chunk + Embedding Workflow**

  * Text sent to Chunk Service
  * Chunks embedded
  * Context merged
* **LLM Orchestration**

  * Supports full or streamed responses (LLM_STREAM=true)
  * Enhanced model defaults
* **Automatic Retries & Fault Tolerance**

  * Exponential backoff for Chunk API, Embedding API, Vector Search, Redis
* **Google Auth Initialization**

  * Auto-detects ADC or service account
* **CORS Enabled**

###  Typical Use Cases

* User asks a question → system retrieves relevant documents → LLM generates response → cached

![Screenshots](https://github.com/mohamedesmael10/HybridRAG_End-to-End_AI_Chatbot_on_OpenShift_OpenStack_GCP/blob/main/Screenshots/(11).png)

![Screenshots](https://github.com/mohamedesmael10/HybridRAG_End-to-End_AI_Chatbot_on_OpenShift_OpenStack_GCP/blob/main/Screenshots/(9).png)

---

## 2. Admin — Document Management & Pipeline Controller Service

This service handles system management and document ingestion workflows.

###  Features

* **Document Ingestion**

  * Upload PDFs, text files, bulk documents
  * Store metadata, categories, ownership
* **Pipeline Triggering**

  * Send documents to Chunk Service
  * Send chunks to User Backend for embedding
  * Register vectors into Vertex AI
* **Admin Authentication**
* **Monitoring & Ops**

  * Redis stats
  * Indexing status
  * Re-index, re-chunk, refresh operations
* **Audit Logs**

###  Typical Use Cases

* Admin uploads dataset → backend chunks → embeds → indexes → User Backend RAG updated


![Screenshots](https://github.com/mohamedesmael10/HybridRAG_End-to-End_AI_Chatbot_on_OpenShift_OpenStack_GCP/blob/main/Screenshots/(8).png)

---

## 3. Chunk Service — File/Text Chunking API (FastAPI)

A lightweight preprocessing API.

###  Features

* Convert files to text (.txt, .csv, .pdf)
* Split text into chunks
* Return chunks_count + list
* Supports POST /chunk with UploadFile or raw text
* Used by Admin + User Backend

###  Typical Use Cases

* Admin uploads PDF → Chunk Service extracts text → embedding → vector storage

---

## 11. Environment variables & secrets

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

## 12. Prerequisites

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

## 13. How to run locally (developer)

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

## 14. Secrets Management Strategy
- The HybridRAG system uses a multi-layer secured secrets management design, combining:

**1. Google Cloud Secrets Manager (GCP) — CI Pipeline**

- Used by the Cloud Build CI pipeline, Terraform, and microservices that need runtime secrets during image build or deployment.

**2. HashiCorp Vault — Runtime Secrets**

- Vault is used mainly for runtime secrets inside OpenShift (OSD) using Vault Agent Injector or External Secrets Operator.

**3. GitLab Protected CI/CD Variables — CD Pipeline**

- Used only by GitLab CD (OpenShift deployment), not for CI.

![Screenshots](https://github.com/mohamedesmael10/HybridRAG_End-to-End_AI_Chatbot_on_OpenShift_OpenStack_GCP/blob/main/Screenshots/(5).png)

---

## 15. Troubleshooting

- **Missing tf_outputs.json** – verify `terraform apply` succeeded and outputs are defined in `outputs.tf`.
- **GitLab trigger fails** – check `GITLAB_TRIGGER_TOKEN`, `_GITLAB_PROJ_ID` and check `/workspace/gitlab_trigger_response.txt` in Cloud Build logs.
- **OpenShift secret creation fails** – validate `GCP_SA_KEY` format and JSON validity.
- **Pub/Sub subscription not reachable** – confirm IAM: subscription/pull requires `roles/pubsub.subscriber` and correct network access.
- **ImagePullBackOff** – ensure OpenShift has a Docker registry secret for Artifact Registry.

---

## 16. HybridRAG – End-to-End CI/CD Architecture Diagram

                    ┌───────────────────────────────────────┐
                    │               Developer               │
                    │            (Push to GitHub)           │
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
                  │         OpenShift Dedicated (OSD Prod)     │
                  ├────────────────────────────────────────────┤
                  │ - Runs 5 Microservices                     │
                  │ - Pulls images from Artifact Registry      │
                  │ - Uses secrets injected via GitLab CD      │
                  │ - Autoscaling + Rolling Updates            │
                  └────────────────────────────────────────────┘


---
## Additional Shots

![Screenshots](https://github.com/mohamedesmael10/HybridRAG_End-to-End_AI_Chatbot_on_OpenShift_OpenStack_GCP/blob/main/Screenshots/(2).png)

![Screenshots](https://github.com/mohamedesmael10/HybridRAG_End-to-End_AI_Chatbot_on_OpenShift_OpenStack_GCP/blob/main/Screenshots/(14).png)

![Screenshots](https://github.com/mohamedesmael10/HybridRAG_End-to-End_AI_Chatbot_on_OpenShift_OpenStack_GCP/blob/main/Screenshots/(17).png)

![Screenshots](https://github.com/mohamedesmael10/HybridRAG_End-to-End_AI_Chatbot_on_OpenShift_OpenStack_GCP/blob/main/Screenshots/(18).png)

![Screenshots](https://github.com/mohamedesmael10/HybridRAG_End-to-End_AI_Chatbot_on_OpenShift_OpenStack_GCP/blob/main/Screenshots/(19).png)

![Screenshots](https://github.com/mohamedesmael10/HybridRAG_End-to-End_AI_Chatbot_on_OpenShift_OpenStack_GCP/blob/main/Screenshots/(20).png)

![Screenshots](https://github.com/mohamedesmael10/HybridRAG_End-to-End_AI_Chatbot_on_OpenShift_OpenStack_GCP/blob/main/Screenshots/(7).png)

![Screenshots](https://github.com/mohamedesmael10/HybridRAG_End-to-End_AI_Chatbot_on_OpenShift_OpenStack_GCP/blob/main/Screenshots/(10).png)

![Screenshots](https://github.com/mohamedesmael10/HybridRAG_End-to-End_AI_Chatbot_on_OpenShift_OpenStack_GCP/blob/main/Screenshots/(6).png)

![Screenshots](https://github.com/mohamedesmael10/HybridRAG_End-to-End_AI_Chatbot_on_OpenShift_OpenStack_GCP/blob/main/Screenshots/(15).png)

---

**Author:** Mohamed Esmael — DevOps | Cloud | System Admin Engineer

© 2025 Mohamed Esmael · [LinkedIn](https://www.linkedin.com/in/mohamedesmael/) · [GitHub](https://github.com/mohamedesmael10/)
