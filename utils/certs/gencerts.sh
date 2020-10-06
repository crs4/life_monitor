#!/bin/bash

CA_NAME="ca"
LOCALIP=$(ifconfig | sed -En 's/127.0.0.1//;s/.*inet (addr:)?(([0-9]*\.){3}[0-9]*).*/\2/p;' | sed -e ':a;N;$!ba;s/\n/,/g')
DOMAINS="lm,lm.local,lifemonitor,lifemonitor.local,localhost,seek,nginx,wfhub"
IPADDRESSES="${LOCALIP}"

# script path
current_path="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# gen cmd
cmd="minica -ca-cert \"${CA_NAME}.pem\" -ca-key \"${CA_NAME}.key\" -domains \"${DOMAINS}\" -ip-addresses \"${IPADDRESSES}\""
echo $cmd
# generate the image
docker build -t crs4/minica .

# generate certs
mkdir -p data
docker run -it --rm \
    --user $(id -u):$(id -g) \
    -v "${current_path}/data:/certs" crs4/minica \
    /bin/bash -c "${cmd}"
