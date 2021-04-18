FROM python:3.7

# RUN apt-get update && apt-get install -y python3-pip
RUN pip3 install pipenv

ENV PROJECT_DIR .

WORKDIR ${PROJECT_DIR}}

COPY . ${PROJECT_DIR}/

RUN pipenv install

CMD ["pipenv", "run", "python", "discordBot.py"]