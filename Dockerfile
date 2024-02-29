FROM python:3.10.6-slim

RUN pip install h5py bluesky ophyd ipython matplotlib databroker pyepics area-detector-handlers

RUN mkdir /code
COPY src/tomoscan/ophyd_clf_sim.py /code/ophyd_clf_sim.py
RUN mkdir -p ~/.config/databroker
COPY ./mongo.yml /root/.config/databroker/mongo.yml

WORKDIR /code

CMD ["ipython", "-i", "ophyd_clf_sim.py"]
