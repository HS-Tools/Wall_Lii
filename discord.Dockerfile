FROM python:3.8

RUN pip3 install pipenv

ENV PROJECT_DIR .
WORKDIR ${PROJECT_DIR}
COPY . ${PROJECT_DIR}/
RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir -r requirements.txt
WORKDIR ${PROJECT_DIR}/src
CMD ["python", "-u", "discordBot.py"]
