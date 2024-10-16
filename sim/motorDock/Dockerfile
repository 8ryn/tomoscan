##### build stage ##############################################################
#Don't believe there is anything that currently requires building and so this step can be skipped
#FROM ghcr.io/epics-containers/ioc-pmac-linux-developer:23.5.1 AS developer


##### runtime stage ############################################################

FROM ghcr.io/epics-containers/ioc-pmac-runtime:2024.9.1 AS runtime

#copy config folder
COPY config ${IOC}/config
