FROM python:3.12-slim
WORKDIR /app
COPY scanner.py .
VOLUME ["/data"]
ENV STATE_FILE=/data/state.json
CMD ["python3", "scanner.py", "--loop"]
