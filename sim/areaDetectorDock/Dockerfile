##### runtime stage ############################################################

FROM ghcr.io/epics-containers/ioc-adsimdetector-linux-runtime:2023.11.2 AS runtime

#copy config folder
COPY config ${IOC}/config

#User created to avoid writing files as root
RUN chmod a+w /epics
RUN useradd --shell /bin/bash ioc
USER ioc
