#!/bin/bash

CA_NAME="ca"
LOCALIP=$(ifconfig | sed -En 's/127.0.0.1//;s/.*inet (addr:)?(([0-9]*\.){3}[0-9]*).*/\2/p;' | sed -e ':a;N;$!ba;s/\n/,/g')
DOMAINS="lm,lm.local,lifemonitor,lifemonitor.local,lmtests,localhost,seek,nginx,wfhub"
IPADDRESSES="${LOCALIP}"
IMAGE_NAME="crs4/minica"

# script path
current_path="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# gen cmd
cmd="minica -ca-cert \"${CA_NAME}.pem\" -ca-key \"${CA_NAME}.key\" -domains \"${DOMAINS}\" -ip-addresses \"${IPADDRESSES}\""

# generate the image
docker build -f ${current_path}/Dockerfile -t ${IMAGE_NAME} ${current_path}

# generate certs
rm -rf "${current_path}/data"
mkdir -p "${current_path}/data"
docker run --rm \
    --user $(id -u):$(id -g) \
    -v "${current_path}/data:/certs" ${IMAGE_NAME} \
    /bin/bash -c "${cmd}"
