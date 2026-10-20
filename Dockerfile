FROM python:3.12-slim
WORKDIR /app
COPY bridge ./bridge
CMD ["python", "-m", "bridge", "demo", "/tmp/out"]
