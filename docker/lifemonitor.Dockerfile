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
RUN pip3 install --no-cache-dir -r /lm/requirements.txt

# Update Environment
ENV PYTHONPATH=/lm:/usr/local/lib/python3.7/dist-packages:/usr/lib/python3/dist-packages:${PYTHONPATH} \
    FLASK_RUN_HOST=0.0.0.0 \
    GUNICORN_WORKERS=1 \
    GUNICORN_THREADS=2 \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# Set the final working directory
WORKDIR /lm

# Copy utility scripts
COPY --chown=root:root docker/wait-for-postgres.sh docker/lm_entrypoint.sh /usr/local/bin/

# Update permissions and install optional certificates
RUN chmod 755 /usr/local/bin/wait-for-postgres.sh /usr/local/bin/lm_entrypoint.sh \
    && certs=$(ls *.crt 2> /dev/null) \
    && mv *.crt /usr/local/share/ca-certificates/ \
    && update-ca-certificates || true

# Set the container entrypoint
ENTRYPOINT /usr/local/bin/lm_entrypoint.sh

# Set the default user
USER lm

# Copy lifemonitor app
COPY --chown=lm:lm app.py /lm/
COPY --chown=lm:lm specs /lm/specs
COPY --chown=lm:lm lifemonitor /lm/lifemonitor


##################################################################
## Node Stage
##################################################################
FROM node:14.16.0-alpine3.12 as node

RUN mkdir -p /static && apk add bash
COPY lifemonitor/static/src /static/src
WORKDIR /static/src
RUN npm install 
# separated run to use node_modules cache from the previous layer
RUN npm run production 


##################################################################
## Target Stage
##################################################################
FROM base as target

COPY --from=node --chown=lm:lm /static/dist /lm/lifemonitor/static/dist