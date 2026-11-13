FROM python:3.12-alpine
RUN pip install --no-cache-dir flask==3.1.3 waitress==3.0.2 tzdata
COPY app /app
COPY config.yaml /config.yaml
COPY pakete /pakete
WORKDIR /app
CMD ["python", "web.py"]
