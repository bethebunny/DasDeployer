FROM arm64v8/python:3.7

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt
RUN pip install mypy
