FROM python:3.11-slim

# System dependencies:
#   git                          -> gitpython repository cloning
#   nodejs/npm                   -> ESLint subprocess for JS/TS static analysis
#   libpango/libcairo/gdk-pixbuf -> weasyprint PDF rendering
#   curl                         -> healthchecks / make model-status from inside container
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        curl \
        nodejs \
        npm \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libffi-dev \
        shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# ESLint + TypeScript plugin, installed globally so static_analysis.py can invoke
# `eslint` via subprocess against any cloned JS/TS project without a per-repo install
# (spec forbids running npm install inside a submitted repository).
RUN npm install -g eslint@8 @typescript-eslint/parser@7 @typescript-eslint/eslint-plugin@7

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
