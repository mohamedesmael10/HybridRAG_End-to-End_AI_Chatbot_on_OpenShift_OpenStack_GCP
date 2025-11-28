# Development & Testing-Grade HybridRAG CI/CD Pipeline on GitLab and OpenStack

- This project delivers a fully production-ready CI/CD pipeline for deploying the HybridRAG AI platform on OpenStack using GitLab CI → Terraform → OpenStack APIs → Helm/Kubernetes (if using Magnum) or native OpenStack compute services. It implements automated build → test → scan → infrastructure provisioning → application deployment across all microservices, integrating OpenStack services such as Nova (compute), Neutron (networking), Cinder (block storage), Keystone (auth), Glance (images), and Swift (object storage). The system follows strict DevOps and GitOps practices, ensuring image immutability, reproducible Terraform provisioning, declarative configurations, and secure multi-layer secret management. This pipeline enables reliable, scalable, cloud-agnostic deployment of AI workloads on private cloud infrastructure, delivering an enterprise-grade, fully automated, and OpenStack-native deployment workflow.

---

## Architecture Diagram


---

## Two-repo strategy

- `hybridrag-openstack` (this repo) — development/testing deployment, dev CI/CD and any OpenStack-specific Terraform/helm differences.

- `hybridrag-osd`  — production deployment, Helm charts, `.gitlab-cd.yml` (CD), docs for OSD deployment and runbooks.

**Why not a single repo?**
- Production (OSD) has stricter policies (immutable images, stricter scanning, protected branches). Keeping prod repo focused reduces accidental changes.
- Development repo can have experimental changes, dev-only dependencies, and faster iteration.

This repository focuses on HybridRAG production deployment on OpenShift (OSD).

### OpenStack (Development) Repository:

 * **[GitHub: HybridRAG – OpenStack Deployment](https://github.com/mohamedesmael10/HybridRAG_End-to-End_AI_Chatbot_on_OpenShift_OpenStack_GCP/tree/develop)**

 * **[GitLab: HybridRAG – OpenStack Deployment](https://gitlab.com/mohamedesmael10/hybridrag_end-to-end_ai_chatbot_on_openshift_openstack_gcp/-/tree/develop?ref_type=heads)**


### OSD (OpenShift) Repository:

 * **[GitHub: HybridRAG – OSD Deployment](https://github.com/mohamedesmael10/HybridRAG_End-to-End_AI_Chatbot_on_OpenShift_OpenStack_GCP/tree/main)**

 * **[GitLab: HybridRAG – OSD Deployment](https://gitlab.com/mohamedesmael10/hybridrag_end-to-end_ai_chatbot_on_openshift_openstack_gcp)**

The OpenStack version is maintained separately for development and testing:


---
## Table of contents
| #        | Section                                       |
| -------- | --------------------------------------------- |
| **1**    | Overview                                      |
| **2**    | Repo Layout (Short)                           |
| **3**    | High-Level CI/CD Flow                         |
| **4**    | `.gitlab-ci.yml` — Stages & Detailed Behavior |
| **5**    | Required CI Variables & Secrets               |
| **6**    | Host/Runner Requirements                      |
| **7**    | Vault / Kubeconfig Flow                       |
| **8**    | Security & Hardening Recommendations          |
| **9**    | Troubleshooting & Debugging Tips              |
| **10**   | Helpful Commands & Local Testing              |
| **11**   | System Architecture Overview                  |
| **12**   | Job-by-Job Notes                              |
| **13**   | Deployment Steps (Manual & Automated)         |
| **14**   | Example `.gitlab-ci.yml` Notes & Tweaks       |
| **15**   | Summary                                       |
| **16**   | License & Credits                             |

---
## 1. Overview

This repository contains an OpenStack-targeted deployment pipeline for the HybridRAG project. The pipeline's responsibilities are:

- Scan the repository for vulnerabilities and misconfiguration (Trivy filesystem scan).
- Build and test all services (Python backends, Node frontends, and chunk function).
- Perform static analysis with SonarCloud (SonarCloud token required).
- Build container images (Docker-in-Docker on GitLab runners).
- Run Trivy image vulnerability scans.
- Push validated images to Docker Hub (or other container registry).
- Run Terraform on a designated **host-runner** (your PC) to provision resources on OpenStack, fetch generated kubeconfig from Vault, and deploy Helm charts & Kubernetes manifests.

This README documents the pipeline, the required variables and secrets, how the Terraform stage runs on your host machine, and common troubleshooting steps.

---
## 2. Repo layout 
```
.
├── Admin_Backend/
├── Admin_Frontend/
├── Chunk_Function/
├── User_Backend/
├── User_Frontend/
├── Terraform/
│   └── terraform-openstack/            
├── helm/
│   ├── admin_backend/
│   ├── admin_frontend/
│   └── user_backend/
└── .gitlab-ci.yml

```

---
## 3. High-level CI/CD flow (what happens automatically)
1. Developer pushes to branches (typically `develop` / `test`).
2. `trivy-repo-scan` scans the repo filesystem for vulnerabilities and config issues; artifacts (JSON report) are stored for review.
3. `build-and-test` builds & runs tests for Python and Node services. Build artifacts for frontends are kept if present.
4. `sonarqube-scan` runs SonarCloud analysis and waits for the Quality Gate result; it fails the job if gate fails.
5. `build-images` builds images with Docker-in-Docker, scans them with Trivy, and (if credentials available) pushes to Docker Hub. Tagging uses `CI_PIPELINE_IID` by default.
6. `terraform-deploy` runs only on a runner tagged `host-runner`. It executes Terraform against your OpenStack environment (via credentials read from Vault), extracts kubeconfig and applies Helm/manifests to the target cluster. This step runs on your host (not in GitLab Cloud) so it can access local tools and credentials.

### 7. User flow (runtime)
1. User submits question via frontend.
2. User-backend checks Redis for cached answer.
   - If found: return cached answer.
   - Else: call chunk function to ensure context.
3. Generate embeddings (Vertex AI).
4. Query Vertex Matching Engine for top contexts.
5. Send context + question to Vertex LLM and return answer.
6. Store answer in Redis for caching.

### 8. Admin flow (ingestion)
1. Admin uploads file → stored in GCS.
2. GCS triggers Pub/Sub (OBJECT_FINALIZE) → `bucket-events-topic`.
3. Admin backend pulls subscription, downloads file.
4. Backend calls Chunk Function to slice file into chunks.
5. Generate embeddings for chunks.
6. Upsert embeddings into Vertex Matching Engine index.
7. Save metadata in Firestore.
8. Use Dead-Letter Topic (DLT) for failed processing and retries.


---
## 4. `.gitlab-ci.yml` — stages & important implementation details

> The pipeline is already long; below is a readable summary + behavior, plus the important config excerpts.

### `default-dind` anchor
- Uses `docker:27` image and `docker:27-dind` service so builds run inside GitLab runners using Docker-in-Docker.
- `DOCKER_TLS_CERTDIR: ""` is set to allow non-TLS DIND in many CI environments (common pattern).
- `before_script` installs small tools (curl, bash, jq) and calls `docker info` for diagnostics.

### `stages`
```
- trivy-repo-scan
- build-test
- sonarqube
- build-images
- trivy-image-scan  # (image stage has scanning embedded)
- push-images       # (push as part of build-images job in provided config)
- terraform-deploy
```


###  Stage 1 — Trivy Repository Scan

Scans the **filesystem** for vulnerabilities and misconfigurations:

- HIGH/CRITICAL alerts
- JSON report (artifact)
- Table output

```yaml
trivy-repo-scan:
  stage: trivy-repo-scan
  image: aquasec/trivy:latest
  script:
    - trivy fs --scanners vuln,config --severity HIGH,CRITICAL --format json -o trivy-report.json .
```

---

###  Stage 2 — Build & Test

Runs builds/tests for all 5 services:

### Python services
- Creates `venv`
- Installs dependencies
- Runs pytest (if available)

### Node services
- Installs dependencies (npm ci)
- Runs `npm run build`

Artifacts include:
- `/Admin_Frontend/dist`
- `/User_Frontend/dist`

---

###  Stage 3 — SonarCloud Code Analysis

- Downloads Sonar scanner
- Uploads source code for analysis
- Waits for **Quality Gate**
- Fails pipeline if gate fails

```yaml
sonarqube-scan:
  stage: sonarqube
  script:
    - sonar-scanner -Dsonar.projectKey="..." -Dsonar.organization="..."
```

---

###  Stage 4 — Build Docker Images

Each service produces two tags:

- `${service}-${IMAGE_TAG_SUFFIX}`
- `${service}-latest`

Uses a reusable Docker-in-Docker template.

---

###  Stage 5 — Trivy Image Scan

Scans each image for HIGH/CRITICAL CVEs:

- Does not stop the pipeline unless critical issues are found
- Ensures safe deployment artifacts

---

###  Stage 6 — Push to Docker Hub

If Docker credentials exist, images are pushed:

```
mohamedesmael/hybridrag_end-to-end_ai_chatbot_on_openshift_openstack_gcp:admin_backend-123
```

Tags:
- Versioned tag
- Latest tag

---

### Stage 7 — Terraform Deploy (Runs on Your PC)

GitLab **does NOT deploy to OpenStack automatically**.
You deploy manually from your host PC:

### 1. Pull latest Terraform from repo
```
git pull origin develop
```

### 2. Set OpenStack environment variables
```
source openrc.sh
```

### 3. Initialize Terraform
```
cd terraform/
terraform init
```

### 4. Apply the infrastructure
```
terraform apply -auto-approve
```

Terraform will:
- Create instances
- Configure networks
- Deploy Docker containers using your pushed images

---
##  GitLab CI Pipeline Workflow (Visual)
```
                ┌─────────────────────────┐
                │       GitLab CI/CD      │
                └────────────┬────────────┘
                             │
     ┌──────────────────────────────────────────────────┐
     │                CI Pipeline Stages                │
     │  1) Trivy Repo Scan                              │
     │  2) Build & Test                                 │
     │  3) SonarCloud Analysis                           │
     │  4) Build Docker Images                           │
     │  5) Trivy Image Scan                              │
     │  6) Push Images to DockerHub                      │
     └──────────────────────────────────────────────────┘
                             │
                             ▼
                 Docker Hub Registry (Images)
                             │
                             ▼
     ┌──────────────────────────────────────────────────┐
     │      Local Machine (Terraform Deploy)            │
     │  Uses latest image tag from GitLab pipeline      │
     │  Applies Terraform to OpenStack Infrastructure   │
     └──────────────────────────────────────────────────┘
```

---

## 5. Required CI variables & recommended values (set in GitLab > Settings > CI/CD > Variables)

**Minimum required for full pipeline**:
- `DOCKER_USERNAME` (masked, protected) — Docker Hub username.
- `DOCKER_PASSWORD` (masked, protected) — Docker Hub password or Personal Access Token.
- `SONAR_TOKEN` (masked, protected) — SonarCloud token.
- `VAULT_ADDR` (protected) — e.g. `https://your-vault.example.com` (already in variables in the config).
- `VAULT_TOKEN` (masked, protected) — token with read privileges for `kv/microstack` and `kv/k8s-config` and other secrets used by Terraform (or use approle).
- `PUBLIC_KEY` (optional) — public SSH key content for OpenStack keypair provisioning.
- `REPO_BASE` — repository base name used to tag images (default in config is "mohamedesmael/...").
- `IMAGE_TAG_SUFFIX` — usually automatic (CI_PIPELINE_IID) but can be overridden.
- `NAMESPACE_USER`, `NAMESPACE_ADMIN` (optional) — kubernetes namespaces used by deploy job.

**GitLab runner registration**:
- Register a runner on your host PC (see GitLab docs) and tag it `host-runner`. Ensure it has Docker and Terraform installed if you want `terraform-deploy` to run there (the job attempts to install/validate helm/kubectl too).


### Key GitLab concepts used

- **Shared runners** / runner tags: use `docker:27-dind` service for DinD steps and a **separate host-runner** (self-hosted) with tag `host-runner` to run Terraform against your local OpenStack.
- **Protected / masked variables**: store secrets like `DOCKER_USERNAME`, `DOCKER_PASSWORD`, `SONAR_TOKEN`, `VAULT_ADDR`, `VAULT_TOKEN`, `GCP_SA_KEY` in GitLab CI variables.
- **Artifacts**: `trivy-report.json`, `artifacts/` build outputs, and `kubeconfig` (written by Host runner) are saved as artifacts for troubleshooting.
- **Rules**: jobs use rules to run on `develop`/`test` branches and the `terraform-deploy` job is manual (or `when: manual`) by default.

---

## 6. Components & Responsibilities (OpenStack Dev/Test Edition)

* **User Backend (FastAPI)**: Handles RAG queries, performs LLM calls, manages Redis caching, and communicates with the vector index.

* **Admin Backend (FastAPI)**: Manages document ingestion workflows, triggers chunking tasks, processes background jobs, and updates vector metadata.

* **Chunk Function**: Extracts text from uploaded files, splits content into configurable chunks, and returns structured chunked payloads for indexing.

* **Local / Lightweight Embeddings & LLM (Dev/Test Mode)**: Uses local embedding models or lightweight inference endpoints instead of managed cloud AI services, enabling cost-efficient experimentation.

* **Redis (Containerized)**: Provides fast caching for answers, vector results, and temporary conversation memory.

* **OpenStack Services**:

  * **Nova**: Runs backend microservices and Redis inside VMs.
  * **Neutron**: Provides network routing, floating IPs, and security groups.
  * **Cinder / Swift**: Stores raw documents, processed chunks, and metadata.
  * **Glance**: Hosts custom VM images used for deployment.
  * **Heat (Optional)**: Can orchestrate VM provisioning and resource setup.

* **GitLab CI**: Builds Docker images, runs unit tests, performs security scans, and publishes artifacts for deployment.

* **GitLab CD**: Deploys updated services to OpenStack using automation (Ansible or shell scripts), applies environment configs, and restarts services.

* **Terraform (Optional)**: Can provision networks, VMs, security groups, and persistent volumes for OpenStack development environments.

---


---
## 7. Host/runner requirements (for the Terraform step)

If you run the `terraform-deploy` stage on your local machine (recommended), ensure the runner host has the following installed and reachable:

### 1) GitLab shared runners (CI stages except terraform-deploy)

- Must support Docker-in-Docker: use `docker:27` image and `docker:27-dind` service.
- The `.gitlab-ci.yml` already includes an anchor `default-dind` with `DOCKER_TLS_CERTDIR: ""` and installs small tools.
- No special network access to your OpenStack is required for CI stages.

### 2) Host-runner for Terraform (`terraform-deploy`) — **your PC or VM**

This runner must:
- Be a **GitLab Runner installed on your host PC** (register it as a shell or docker executor and tag it `host-runner`).
- Have Terraform installed (same version as `TF_VER`) and `kubectl`, `helm` if you want the runner to perform post-terraform helm deploys (your job already installs helm if needed).
- Have network access to your MicroStack/OpenStack API endpoint and to Vault (or have Vault accessible locally).
- Have Vault CLI or `curl` available (job uses `curl` to communicate with Vault).

Register runner example (on your host):
```bash
# install gitlab-runner (per distro), then
sudo gitlab-runner register
# When prompted: set tags -> host-runner
# executor -> shell (recommended for direct host access)
```

After registration, `terraform-deploy` job will be picked up by this runner.

- `terraform` (tested config references `TF_VER` = `1.5.7` in variables; install compatible version)
- `kubectl` (used to apply manifests after fetching kubeconfig)
- `helm` (for Helm charts deployment)
- `jq`, `curl`, `bash`, `coreutils`, `base64`, `envsubst` (job expects these tools)
- If you rely on `microk8s` for local cluster: have `microk8s` installed or ensure `kubectl` works against target cluster.
- Vault access from host: ensure the host can reach `VAULT_ADDR` and authorized with `VAULT_TOKEN` provided in CI variables.

**Runner configuration tips**:
- Use Docker executor or shell executor depending on your host setup. For Terraform, shell executor is convenient so Terraform runs directly on host and has access to host tools.
- Tag runner with `host-runner` so only the Terraform job runs there.
- Keep runner up-to-date and run it under an OS account with limited privileges.

After registration, `terraform-deploy` job will be picked up by this runner.

**Security note**: ensure `kv/k8s-config` access is tightly controlled (least privilege Vault policy). Rotate vault tokens and policies in production.

---
## 8. System Architecture Overview 

This repository represents the **development and testing environment** of the HybridRAG platform, deployed on **OpenStack** with GitLab CI/CD. It mirrors the production OSD repo but uses OpenStack VMs, networks, and security groups instead of managed Kubernetes.

Below is the architecture breakdown for this repo.

---

### 1. User Service — Local RAG + Redis + LLM Orchestration

This service provides the intelligent query-handling workflow used during development.

#### **Features**

* **RAG Pipeline (Dev Mode)**

  * Cleans user input
  * Generates embeddings via local model or GCP Vertex AI (optional)
  * Retrieves similar chunks from local vector storage
  * Produces LLM responses in dev mode

* **Redis Caching Layer**

  * SHA-256 query hashing
  * JSON response caching
  * Configurable TTL

* **Chunk + Embedding Flow (Dev)**

  * Communicates with Chunk Service for text splitting
  * Uses local or GCP embedding endpoints

* **LLM Controller (Test Mode)**

  * Supports full or streamed responses

* **Fault Tolerance**

  * Automatic retries for chunk requests, Redis lookups, and embeddings

#### **Typical Use Cases**

* Developer tests user queries
* Runs RAG pipeline locally before deploying to OSD

---

### 2. Admin Service — Document Management & Pipeline Controller

This backend handles document ingestion, dataset management, and orchestration.

#### **Features**

* **Document Upload (PDF / TXT / CSV)**

  * Stored on local storage or OpenStack Volumes

* **Chunk + Embed Pipeline Triggering**

  * Sends files to Chunk Service
  * Sends chunks to embedding layer
  * Updates local vector DB

* **Test Authentication Layer**

* **Admin Monitoring Tools**

  * Chunking logs
  * Embedding status
  * Re-index operations

* **Local Metadata Storage**

  * JSON / SQLite / Firestore-dev (configurable for OpenStack setup)

#### **Typical Use Cases**

* Admin uploads dataset during testing
* Tests full RAG ingestion pipeline before pushing to production

---

### 3. Chunk Service — Lightweight Chunking API (FastAPI)

This service standardizes preprocessing and is used by both User & Admin.

#### **Features**

* Converts files into text
* Splits text into chunks
* Returns chunk list + count
* Supports uploaded files and raw POST text

#### **Typical Use Cases**

* Dev uploads PDF → Chunk Service extracts content → embeddings generated locally

---

### 4. Environment Variables & Secrets (OpenStack Version)

#### **Minimum Required**

* `OPENSTACK_AUTH_URL`
* `PROJECT_ID`
* `REGION`
* `IMAGE_TAG`
* `FLAVOR`
* `NETWORK_ID`
* `SECURITY_GROUP_ID`
* `KEYPAIR_NAME`

#### **CI Secrets (GitLab)**

* `OPENSTACK_USERNAME`
* `OPENSTACK_PASSWORD`
* `OPENSTACK_PROJECT`
* `GITLAB_TRIGGER_TOKEN`

#### **Local Runtime Secrets**

* Redis password
* Vector DB endpoints (dev)

---

### 5. GitLab CI/CD — VM-Based Deployment to OpenStack

The GitLab CD pipeline for this repository performs the following:

* Builds Docker images
* Pushes images to GitLab Container Registry
* Connects to OpenStack via OpenStack CLI
* Provisions/updates VMs used for each microservice
* Deploys services using Docker Compose on VMs
* Syncs environment variables via .env files

#### **Deployment Workflow**

1. Build → Test → Scan (CI)
2. Upload images to registry
3. Boot/Update OpenStack VMs
4. SSH + Docker Compose pull + restart

This environment is ideal for testing and debugging before deploying to OSD.

---

### 6. Deployment Strategy on OpenStack

Each service runs on one or more VMs using **Docker Compose**.

#### **Core Components**

* User Service VM
* Admin Service VM
* Chunk Service VM
* Redis VM
* Optional: Local Vector DB VM


---
## 9. Security / hardening recommendations

- **Protect & mask** all tokens and credentials in GitLab CI variables: `VAULT_TOKEN`, `DOCKER_PASSWORD`, `SONAR_TOKEN`, etc.
- Consider requiring manual approval (protected branch/pipelines) for deployments to production.
- Make Trivy and SonarCloud results policy-enforced. If you want the pipeline to fail on high/critical vulnerabilities, exit with non-zero codes when such findings exist (parse Trivy JSON or use Trivy exit codes).
- Use short-lived tokens (Vault AppRole, ephemeral CI jobs) instead of long-lived static tokens where possible.
- Limit Vault token scopes to the minimal secrets required by the pipeline. Use Vault policies.
- Keep runners updated; do not run untrusted jobs on your `host-runner` with root privileges.

---

## Job-by-job notes and tips

### `trivy-repo-scan`
- Uses `trivy fs` to scan repository files for vuln/config issues. Produces `trivy-report.json` as artifact.
- Keep this job fast by excluding vendor/large directories if needed.

### `build-and-test`
- The job uses DinD and installs Python/Node per component in ephemeral venvs.
- Tests are run but failures are non-blocking in your current snippet (`|| true`). If you want to fail CI on test failure, remove `|| true`.
- Artifacts: `artifacts/` contains built frontend outputs.

### `sonarqube-scan`
- Runs sonar-scanner and polls SonarCloud quality gate (up to 6 attempts). If the gate fails, job fails.
- Make sure `SONAR_TOKEN` is valid and the SonarCloud project key matches.

### `build-scan-push-images`
- Builds Docker images for each component and tags with `IMAGE_TAG_SUFFIX` (pipeline IID) and `latest`.
- Installs Trivy in the job and scans images; if Trivy finds high/critical vulns with `--exit-code 1` the job will fail (current script does `|| true`, adjust to enforce failure if you want stricter enforcement).
- Pushes images to Docker Hub if `DOCKER_PASSWORD` is present (logs into Docker).

**Note about DinD security:** using DinD in shared CI environments can be risky—use private runners or authenticated environments.

### `terraform-deploy` (host-runner)
- Runs `terraform init/plan/apply` in `Terraform/terraform-openstack` directory.
- After Terraform creates compute nodes and `cloud-init` finishes, it expects Vault to contain base64-encoded kubeconfig at `kv/k8s-config`. The job decodes it and writes `kubeconfig` artifact.
- Job then uses `kubectl` and `helm` (installs helm if necessary) to deploy Helm charts and non-Helm chunk manifests to the cluster.

**Host-runner requirements**:
- `terraform` installed (TF_VER), `kubectl`, `helm`, `base64`, `curl`, `jq`, and network access to Vault and MicroStack.
- The runner must be able to run privileged host-level commands and write `kubeconfig` locally.

**Vault token validation**: The job checks `/v1/auth/token/lookup-self` to ensure `VAULT_TOKEN` is valid — useful to fail fast if token is invalid.

---

## Local testing checklist (before enabling pipeline on protected branches)

1. **Register host-runner** on your PC and tag it `host-runner`.
2. Verify `VAULT_ADDR` and `VAULT_TOKEN` in your CI variables by running a manual `curl` on your host runner:
   ```bash
   curl -s -H "X-Vault-Token: $VAULT_TOKEN" "$VAULT_ADDR/v1/auth/token/lookup-self" | jq .
   ```
3. Manually run Terraform from your host to ensure provider credentials retrieved from Vault work:
   ```bash
   cd Terraform/terraform-openstack
   export VAULT_ADDR=...
   export VAULT_TOKEN=...
   terraform init
   terraform plan
   terraform apply -auto-approve
   ```
4. Ensure kubeconfig is written to Vault and that `base64 --decode` yields a valid kubeconfig file.
5. Test `helm template` locally to validate Helm chart values.

---

## 10) Deploy steps (manual & automated)

### Automated (recommended)
1. Push feature branch to GitLab -> CI runs tests & image builds.
2. When branch `develop` or `test` is pushed, the pipeline will run all scanning and building stages.
3. `terraform-deploy` job is `manual` by default for `develop` branch (safe strategy). You can make it automatic if comfortable.

### Manual (one-off) — how to run Terraform locally
If you prefer to run Terraform locally instead of via GitLab:

```bash
cd Terraform/terraform-openstack
export VAULT_ADDR="https://..."
export VAULT_TOKEN="s.xxxxx"
terraform init
terraform apply -auto-approve
# then fetch kubeconfig from Vault as pipeline does
```

---

## 11) Artifacts, logs and debugging

- `trivy-report.json` is saved as artifact for the `trivy-repo-scan` job (expire in 1h).
- Build artifacts (frontend `dist`) are saved to `artifacts/` during the `build-and-test` job.
- Terraform writes `/workspace/tf_outputs.json` in the GCP repo flow; in OpenStack repo the host-runner writes `kubeconfig` and saves it as artifact.
- If a job fails, browse job logs in GitLab UI and inspect the last `stderr`/`stdout` lines; for Terraform failures, examine the plan output.
---

## Example `gitlab-ci.yml` tips / tweaks

- To require manual trigger for `terraform-deploy` keep `when: manual` or the `rules` you have. To allow Cloud Build or other system to trigger it automatically, allow an API trigger and a protected trigger variable such as `RUN_TF=true`.

- If you want `build-and-test` to fail the pipeline on unit test failure, remove `|| true` from `pytest` invocations.

- If you want image-scanning to fail the push, ensure Trivy `--exit-code 1` is not caught with `|| true`.

---

## 9. Troubleshooting & common fixes

- **Trivy JSON missing**: ensure Trivy had permission to read files, check `trivy-report.json` in job artifacts.
- **Docker build errors on DIND**: ensure `docker:dind` service is available and `DOCKER_TLS_CERTDIR=\"\"` is set. If using shared runners that don’t allow DIND, consider building with Kaniko or BuildKit on remote builder.
- **SonarCloud Quality Gate times out**: check SonarCloud project key and token; ensure SonarCloud organization settings accept your token and project key.
- **Terraform fails on host-runner**: check runner system has correct `terraform` version, OpenStack API reachability, and Vault token validity. Inspect job logs for `curl` Vault lookup output.
- **kubeconfig not found in Vault**: confirm Terraform module wrote the kubeconfig to the expected Vault path (`kv/k8s-config`) and field (`config`) as base64. Check Vault UI or `vault kv get` locally to verify.
- **`kubectl` or `helm` not found**: the job attempts to install Helm; still ensure your runner has `kubectl` installed or the job will fail when creating secrets / applying manifests.
- **Images not pushed**: if `docker push` fails, check `DOCKER_USERNAME`/`DOCKER_PASSWORD` are set and runner has network access to Docker Hub.

---
## 10. Helpful local commands & examples

- Register a GitLab runner on your host and tag it `host-runner`:
```bash
gitlab-runner register \
  --non-interactive \
  --url "https://gitlab.com/" \
  --registration-token "$REGISTRATION_TOKEN" \
  --executor "shell" \
  --description "Host Runner for Terraform" \
  --tag-list "host-runner" \
  --run-untagged="false"
```

- Test Vault token locally:
```bash
curl -s -H "X-Vault-Token: $VAULT_TOKEN" "$VAULT_ADDR/v1/auth/token/lookup-self" | jq .
```

- Decode kubeconfig locally (example if you have JSON from Vault):
```bash
echo "$KCFG_B64" | base64 -d > kubeconfig
export KUBECONFIG="$PWD/kubeconfig"
kubectl get nodes
```

- Run Terraform locally (same directory as pipeline):
```bash
cd Terraform/terraform-openstack
terraform init
terraform plan -out=tfplan
terraform apply -input=false tfplan
```

---
## 11. Example `.gitlab-ci.yml` snippets (already used in repo)

The repo already contains the pipeline implementation that performs the stages described above. If you want the pipeline to be stricter (e.g. fail on Trivy HIGH/CRITICAL findings), modify the Trivy steps to check `trivy-report.json` and `exit 1` on findings count > 0 or inspect Trivy exit codes.

---

## Summary / Flow Recap

- GitLab CI runs Trivy FS scan, unit tests, SonarCloud analysis, builds + scans images and pushes them to Docker Hub.
- The Terraform `apply` step runs on your **host-runner**, which has network access to MicroStack/OpenStack and Vault; it provisions VMs, writes kubeconfig into Vault, and the same host-runner pulls kubeconfig from Vault to run `kubectl` / `helm` to deploy the Helm charts and the Chunk Function manifests.
  
---
**Author:** Mohamed Esmael — DevOps | Cloud | System Admin Engineer 
© 2025 Mohamed Esmael · [LinkedIn](https://www.linkedin.com/in/mohamedesmael/) · [GitHub](https://github.com/mohamedesmael10/)
