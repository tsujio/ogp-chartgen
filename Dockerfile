FROM python:3.11-slim

COPY requirements.txt /

RUN pip install -r /requirements.txt && rm /requirements.txt

WORKDIR /app

COPY src .

ENV PYTHONPATH=$PYTHONPATH:/app

ENTRYPOINT ["uvicorn", "main:app", "--host", "0.0.0.0"]
