FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ src/
RUN useradd -r -u 1000 -s /bin/false app
USER app
CMD ["python", "src/ha-tower-discovery.py"]
