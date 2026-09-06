FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends default-jdk-headless procps && \
    rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/default-java
ENV PYSPARK_PYTHON=python3

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN sed -i 's/\r$//' run_pipeline.sh

CMD ["bash", "run_pipeline.sh"]