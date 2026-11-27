FROM python:3.12-alpine
RUN pip install --no-cache-dir flask==3.1.3 waitress==3.0.2 pyyaml==6.0.2
COPY app /app
COPY config.yaml /config.yaml
WORKDIR /app
CMD ["python", "web.py"]
