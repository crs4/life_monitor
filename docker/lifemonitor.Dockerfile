FROM python:3.7-buster

# Declare the default 'lifemonitor' user
ARG LM_USER=lm

# Install base requirements
RUN apt-get update -q \
 && apt-get install -y --no-install-recommends \
        bash \
        postgresql-client-11 \
        python3-psycopg2 \
        python3-sqlalchemy \
 && apt-get clean -y && rm -rf /var/lib/apt/lists

# Create a user 'lm' with HOME at /lm
RUN useradd -d /${LM_USER} -m ${LM_USER}

# Update Environment
ENV PYTHONPATH=/${LM_USER}:/usr/local/lib/python3.7/dist-packages:/usr/lib/python3/dist-packages:${PYTHONPATH} \
    FLASK_DEBUG=1 \
    FLASK_RUN_HOST=0.0.0.0 \
    GUNICORN_WORKERS=1 \
    GUNICORN_THREADS=2 \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# Copy requirements and certificates
COPY --chown=${LM_USER}:${LM_USER} requirements.txt certs/*.crt /${LM_USER}/

# Install requirements and install certificates
RUN pip3 install --no-cache-dir -r /${LM_USER}/requirements.txt

# Set the final working directory
WORKDIR /${LM_USER}

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
USER ${LM_USER}

# Copy lifemonitor app
COPY --chown=${LM_USER}:${LM_USER} app.py /${LM_USER}/
COPY --chown=${LM_USER}:${LM_USER} specs /${LM_USER}/specs
COPY --chown=${LM_USER}:${LM_USER} lifemonitor /${LM_USER}/lifemonitor

