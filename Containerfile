FROM registry.hub.docker.com/library/python:3.12

RUN apt update && \
  apt install -y libvirt-dev iproute2 && \
  apt clean

COPY . /tmp/sushy-tools/
ENV PBR_VERSION=0.1.0
RUN pip3 install --no-cache-dir /tmp/sushy-tools/ libvirt-python && \
  cp -r /tmp/sushy-tools/sushy_tools/emulator/templates \
    $(python3 -c "import os,sushy_tools.emulator as e; print(os.path.dirname(e.__file__))")/templates && \
  rm -rf /tmp/sushy-tools/

COPY sushy-emulator.conf /etc/sushy/sushy-emulator.conf
CMD /usr/local/bin/sushy-emulator --config /etc/sushy/sushy-emulator.conf --debug
