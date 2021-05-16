FROM python:3.7

RUN pip3 install pipenv

ENV PROJECT_DIR .

WORKDIR ${PROJECT_DIR}

COPY . ${PROJECT_DIR}/

WORKDIR ${PROJECT_DIR}/code

RUN pipenv install

CMD ["pipenv", "run", "python", "twitch.py"]