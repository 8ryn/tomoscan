FROM python:3.10

RUN pip install softioc==4.4.0 cothread==2.18.3

COPY simPulse.py SimPulse.py

ENTRYPOINT ["python3", "SimPulse.py"]
