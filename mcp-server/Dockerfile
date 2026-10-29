FROM python:3.13-slim

WORKDIR /app
RUN pip install --no-cache-dir "mcp>=1.24,<2"
COPY server.py .

ENV PORT=8080 PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["python", "-u", "server.py"]
