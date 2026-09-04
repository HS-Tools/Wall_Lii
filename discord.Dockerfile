# syntax=docker/dockerfile:1
FROM python:3.10

ENV PROJECT_DIR=/app
WORKDIR ${PROJECT_DIR}
# Set the timezone to Los Angeles
RUN ln -sf /usr/share/zoneinfo/America/Los_Angeles /etc/localtime && \
    echo "America/Los_Angeles" > /etc/timezone
COPY requirements.txt ./requirements.txt
RUN apt-get update \
  && apt-get install -y --no-install-recommends gcc libpq-dev libpq5 \
  && rm -rf /var/lib/apt/lists/*
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --disable-pip-version-check --upgrade pip setuptools wheel \
  && python -m pip install --disable-pip-version-check --retries 5 --timeout 60 --no-build-isolation -r requirements.txt
RUN apt-get purge -y gcc libpq-dev \
  && apt-get autoremove -y \
  && rm -rf /var/lib/apt/lists/*
COPY . ${PROJECT_DIR}/
WORKDIR ${PROJECT_DIR}/src
CMD ["python", "-u", "discordBot.py"]
