# Dockerfile (OpenShift / Kubernetes / local friendly)
FROM python:3.12-slim AS builder
WORKDIR /app

COPY requirements.txt .
# create venv and install dependences into it
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim AS final
WORKDIR /app

# Copy venv created in builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY . .

# Ensure venv is usable by arbitrary non-root UIDs (OpenShift random UID)
# make group 0 own the venv and give group read/execute
RUN chown -R 0:0 /opt/venv \
 && chmod -R g+rwX /opt/venv \
 && mkdir -p /app/logs \
 && chown -R 0:0 /app \
 && chmod -R g+rwX /app

ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
EXPOSE 8080

# Use exec form
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
