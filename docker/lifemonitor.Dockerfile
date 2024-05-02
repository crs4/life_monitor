FROM python:3.10-slim-buster as base

# Install base requirements
RUN apt-get update -q \
 && apt-get install -y --no-install-recommends \
        bash lftp curl rsync build-essential  \
        redis-tools git \
        postgresql-client-11 default-jre \
 && apt-get clean -y && rm -rf /var/lib/apt/lists

# Set the parametric USER ID
ARG USER_ID
ENV USER_ID=${USER_ID:-1000}

# Set the parametric GROUP ID
ARG GROUP_ID
ENV GROUP_ID=${GROUP_ID:-1000}

# Create a user 'lm' with HOME at /lm and set 'lm' as default git user
RUN groupadd -g ${GROUP_ID} lm && \
    useradd -u ${USER_ID} -g lm -d /lm -m lm

# Set the default user
ENV USER=lm

# Copy requirements and certificates
COPY --chown=lm:lm requirements.txt certs/*.crt /lm/

# Install requirements and install certificates
RUN pip3 install --no-cache-dir --upgrade pip
RUN pip3 install --no-cache-dir -r /lm/requirements.txt

# Update Environment
ENV PYTHONPATH=/lm:/usr/local/lib/python3.10/dist-packages:/usr/lib/python3/dist-packages:${PYTHONPATH} \
    FLASK_RUN_HOST=0.0.0.0 \
    GUNICORN_WORKERS=1 \
    GUNICORN_THREADS=2 \
    GUNICORN_CONF=/lm/gunicorn.conf.py \
    PROMETHEUS_METRICS_PORT=9090 \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# Install Nextflow
RUN curl -fsSL get.nextflow.io | bash

# Set the final working directory
WORKDIR /lm

# Copy utility scripts
COPY \
    docker/wait-for-postgres.sh \
    docker/wait-for-redis.sh \
    docker/wait-for-file.sh \
    docker/lm_entrypoint.sh \
    docker/worker_entrypoint.sh \
    docker/wss-entrypoint.sh \
    /usr/local/bin/

# Update permissions and install optional certificates
RUN chmod 755 \
    /usr/local/bin/wait-for-postgres.sh \
    /usr/local/bin/wait-for-redis.sh \
    /usr/local/bin/wait-for-file.sh \
    /usr/local/bin/lm_entrypoint.sh \
    /usr/local/bin/worker_entrypoint.sh \
    /usr/local/bin/wss-entrypoint.sh \
    /nextflow \
    && certs=$(ls *.crt 2> /dev/null) \
    && mv *.crt /usr/local/share/ca-certificates/ \
    && update-ca-certificates || true \
    && mv /nextflow /usr/local/bin

# Set the container entrypoint
ENTRYPOINT /usr/local/bin/lm_entrypoint.sh

# Prepare data folder
RUN mkdir -p /var/data/lm \
    && chown -R lm:lm /var/data/lm \
    && ln -s /var/data/lm /lm/data \
    && chown -R lm:lm /lm/data \
    && mkdir -p /var/log/lm && chown -R lm:lm /var/log/lm \
    && mkdir /lm/.nextflow && chmod -R 777 /lm/.nextflow

# Set the default user
USER lm

# Set default Git user
RUN git config --global user.name "LifeMonitor[bot]" \
    && git config --global user.email "noreply@lifemonitor.eu"

# Copy lifemonitor app
COPY --chown=lm:lm app.py ws.py lm-metrics-server lm-admin lm gunicorn.conf.py /lm/
COPY --chown=lm:lm specs /lm/specs
COPY --chown=lm:lm lifemonitor /lm/lifemonitor
COPY --chown=lm:lm migrations /lm/migrations
COPY --chown=lm:lm cli /lm/cli

# Ensure read access to source code to unprivileged users
RUN find /lm/lifemonitor/ -type d -exec chmod a+r {} \;

##################################################################
## Node Stage
##################################################################
FROM node:14.16.0-alpine3.12 as node


RUN mkdir -p /static && apk add --no-cache bash python3 make g++ \
    && addgroup -S lm && adduser -S lm -G lm \
    && chown -R lm:lm /static
WORKDIR /static/src
COPY lifemonitor/static/src/package.json package.json
RUN npm install
# Copy and build static files
# Use a separated run to take advantage
# of node_modules cache from the previous layer
COPY lifemonitor/static/src .
RUN npm run production


##################################################################
## Target Stage
##################################################################
FROM base as target

# Set software and build number
ARG SW_VERSION
ARG BUILD_NUMBER
ENV LM_SW_VERSION=$SW_VERSION
ENV LM_BUILD_NUMBER=$BUILD_NUMBER

COPY --from=node --chown=lm:lm /static/dist /lm/lifemonitor/static/dist
