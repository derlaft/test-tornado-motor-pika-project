FROM alpine

RUN apk update && apk upgrade && apk add python3 py3-pip && rm -rf /var/cache/apk

RUN pip3 install motor pika tornado

RUN mkdir /services

COPY ./common /services/common
COPY ./webapp /services/webapp
COPY ./data_repository /services/data_repository

ENV PYTHONPATH=/services
