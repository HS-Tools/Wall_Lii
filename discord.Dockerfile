FROM python:3.8

RUN pip3 install pipenv

ENV PROJECT_DIR .
WORKDIR ${PROJECT_DIR}
COPY . ${PROJECT_DIR}/
WORKDIR ${PROJECT_DIR}/src
RUN pipenv install
CMD ["pipenv", "run", "python", "discordBot.py"]