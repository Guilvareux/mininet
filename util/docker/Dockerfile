FROM debian:stretch-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -yq
RUN apt-get install -yq \
    arping \
    git \
    hping3 \
    iputils-ping \
    net-tools \
    sudo \
    traceroute

ARG INSTALL_FLAGS="-fnv"
COPY . /root/mininet
RUN sh -c "/root/mininet/util/install.sh ${INSTALL_FLAGS}"

RUN apt-get clean

RUN chmod +x /root/mininet/util/docker/entrypoint.sh

ENV MN_FLAGS=""
ENV FILE_PATH=""

ENTRYPOINT [ "sh", "-c", "/root/mininet/util/docker/entrypoint.sh"]
