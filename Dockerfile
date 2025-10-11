FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install "uv>=0.1.18"
RUN uv pip compile pyproject.toml --output-file=requirements.txt
RUN uv pip install --system -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
