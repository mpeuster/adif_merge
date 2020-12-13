FROM python:3.8-slim
ADD . /app
WORKDIR /app
RUN mkdir static
RUN pip install -r requirements.txt
RUN python setup.py develop
RUN adif_merge_svc -h

EXPOSE 8081
CMD ["adif_merge_svc", "--log-level", "DEBUG"]