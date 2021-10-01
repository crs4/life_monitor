FROM python:3.7-buster as base

# Install base requirements
RUN apt-get update -q \
 && apt-get install -y --no-install-recommends \
        bash \
        postgresql-client-11 \
 && apt-get clean -y && rm -rf /var/lib/apt/lists

# Create a user 'lm' with HOME at /lm
RUN useradd -d /lm -m lm

# Copy requirements and certificates
COPY --chown=lm:lm requirements.txt certs/*.crt /lm/

# Install requirements and install certificates
RUN pip3 install --no-cache-dir --upgrade pip
RUN pip3 install --no-cache-dir -r /lm/requirements.txt

# Update Environment
ENV PYTHONPATH=/lm:/usr/local/lib/python3.7/dist-packages:/usr/lib/python3/dist-packages:${PYTHONPATH} \
    FLASK_RUN_HOST=0.0.0.0 \
    GUNICORN_WORKERS=1 \
    GUNICORN_THREADS=2 \
    GUNICORN_CONF=/lm/gunicorn.conf.py \
    PROMETHEUS_METRICS_PORT=9090 \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# Set the final working directory
WORKDIR /lm

# Copy utility scripts
COPY --chown=root:root \
    docker/wait-for-postgres.sh docker/lm_entrypoint.sh docker/worker_entrypoint.sh \
    /usr/local/bin/

# Update permissions and install optional certificates
RUN chmod 755 \
      /usr/local/bin/wait-for-postgres.sh \
      /usr/local/bin/lm_entrypoint.sh \
      /usr/local/bin/worker_entrypoint.sh \
    && certs=$(ls *.crt 2> /dev/null) \
    && mv *.crt /usr/local/share/ca-certificates/ \
    && update-ca-certificates || true

# Set the container entrypoint
ENTRYPOINT /usr/local/bin/lm_entrypoint.sh

# Set the default user
USER lm

# Copy lifemonitor app
COPY --chown=lm:lm app.py gunicorn.conf.py /lm/
COPY --chown=lm:lm specs /lm/specs
COPY --chown=lm:lm lifemonitor /lm/lifemonitor
COPY --chown=lm:lm migrations /lm/migrations


##################################################################
## Node Stage
##################################################################
FROM node:14.16.0-alpine3.12 as node

RUN mkdir -p /static && apk add --no-cache bash
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

COPY --from=node --chown=lm:lm /static/dist /lm/lifemonitor/static/dist

# Set the build number
ARG SW_VERSION
ARG BUILD_NUMBER
ENV LM_SW_VERSION=${SW_VERSION}
ENV LM_BUILD_NUMBER=${BUILD_NUMBER}
