
FROM python:3.7-buster

RUN apt-get update -q \
 && apt-get install -y --no-install-recommends \
        bash \
        postgresql-client-11 \
        python3-psycopg2 \
        python3-sqlalchemy \
 && apt-get clean -y && rm -rf /var/lib/apt/lists

ENV PYTHONPATH=/usr/local/lib/python3.7/dist-packages:/usr/lib/python3/dist-packages

# Create a user 'lm' with HOME at /lm
RUN useradd -d /lm -m lm

COPY --chown=lm:lm requirements.txt /lm
RUN pip3 install --no-cache-dir -r /lm/requirements.txt

WORKDIR /lm
ENV FLASK_DEBUG=1 \
    FLASK_RUN_HOST=0.0.0.0 \
    GUNICORN_WORKERS=1 \
    GUNICORN_THREADS=2

ENTRYPOINT /usr/local/bin/lm_entrypoint.sh

ENV PYTHONPATH=/lm:${PYTHONPATH}
COPY --chown=root:root docker/wait-for-postgres.sh docker/lm_entrypoint.sh /usr/local/bin/
RUN chmod 755 /usr/local/bin/wait-for-postgres.sh /usr/local/bin/lm_entrypoint.sh

USER lm
COPY --chown=lm:lm app.py /lm/
COPY --chown=lm:lm specs /lm/specs
COPY --chown=lm:lm lifemonitor /lm/lifemonitor

