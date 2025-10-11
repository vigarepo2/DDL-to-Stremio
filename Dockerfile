FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .

RUN pip install "uv>=0.1.18"

# --- MODIFIED SECTION ---
# 1. Compile pyproject.toml to a standard requirements.txt
RUN uv pip compile pyproject.toml --output-file=requirements.txt
# 2. Install dependencies from the requirements.txt file
RUN uv pip install --system -r requirements.txt
# --- END MODIFIED SECTION ---

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
