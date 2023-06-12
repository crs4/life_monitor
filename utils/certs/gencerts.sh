#!/bin/bash

set -o errexit
set -o nounset

CA_NAME="ca"
if type -P ifconfig > /dev/null 2>&1; then
    NETWORK_DATA="$(ifconfig)"
else
    NETWORK_DATA="$(ip -oneline addr)"
fi

# check if GNU sed is available
gsed=sed
if uname -a | grep -q Darwin; then
    if ! type -P gsed > /dev/null 2>&1; then
        echo "GNU sed is not available. Please install it with 'brew install gnu-sed'" >&2
        exit 1
    else
        gsed=gsed
    fi
fi

IPADDRESSES="$(echo "${NETWORK_DATA}" | "${gsed}" -En 's/127.0.0.1//;s/.*inet (addr:)?(([0-9]*\.){3}[0-9]*).*/\2/p;' | "${gsed}" -e ':a;N;$!ba;s/\n/,/g')"
DOMAINS="lm,lm.local,lifemonitor,lifemonitor.local,lmtests,localhost,seek,nginx,wfhub"
IMAGE_NAME="crs4/minica"

# script path
current_path="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# gen cmd
cmd="minica -ca-cert \"${CA_NAME}.pem\" -ca-key \"${CA_NAME}.key\" -domains \"${DOMAINS}\" -ip-addresses \"${IPADDRESSES}\""

# generate the image
docker build -f "${current_path}/Dockerfile" -t "${IMAGE_NAME}" "${current_path}"

# generate certs
rm -rf "${current_path}/data"
mkdir -p "${current_path}/data"

echo "Generating certificates: ${cmd}" >&2
docker run --rm \
    --user $(id -u):$(id -g) \
    -v "${current_path}/data:/certs" "${IMAGE_NAME}" \
    /bin/bash -c "${cmd}"
