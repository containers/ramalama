FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /work

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential git curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip
RUN pip install pytest

# Copy the repo into the image (optional; you can also mount the host workspace at run time)
COPY . /work

# Default: run pytest
CMD ["pytest", "-q"]
