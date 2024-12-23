FROM python:3.8

ENV PROJECT_DIR .
WORKDIR ${PROJECT_DIR}
COPY . ${PROJECT_DIR}/
# Set the timezone to Los Angeles
RUN ln -sf /usr/share/zoneinfo/America/Los_Angeles /etc/localtime && \
    echo "America/Los_Angeles" > /etc/timezone
RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir -r requirements.txt
WORKDIR ${PROJECT_DIR}/src
CMD ["python", "-u", "twitchBot.py"]
