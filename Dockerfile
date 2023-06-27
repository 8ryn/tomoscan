FROM python:3.10.6-slim

RUN pip install bluesky ophyd ipython matplotlib databroker pyepics

RUN mkdir /code
COPY src/tomoscan/ophyd_inter_setup.py /code/ophyd_inter_setup.py
RUN mkdir -p ~/.config/databroker
COPY ./mongo.yml /root/.config/databroker/mongo.yml

WORKDIR /code

CMD ["ipython", "-i", "ophyd_inter_setup.py"]
