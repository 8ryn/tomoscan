##### runtime stage ############################################################

FROM ghcr.io/epics-containers/ioc-adsimdetector-runtime:2024.9.1 AS runtime

#copy config folder
COPY config ${IOC}/config

#User created to avoid writing files as root
RUN chmod a+w /epics
RUN useradd --shell /bin/bash ioc
USER ioc
