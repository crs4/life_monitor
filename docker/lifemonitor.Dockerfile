
FROM python:3.8-buster

RUN apt-get update -q \
 && apt-get install -y --no-install-recommends \
        bash \
        python3-sqlalchemy \
 && apt-get clean -y && rm -rf /var/lib/apt/lists

# Create a user 'lm' with HOME at /lm
RUN useradd -d /lm -m lm

COPY --chown=root:root docker/wait-for-postgres.sh /usr/local/bin
RUN chmod 755 /usr/local/bin/wait-for-postgres.sh

COPY --chown=lm:lm requirements.txt /lm
COPY --chown=lm:lm lifemonitor /lm/lifemonitor

RUN pip3 install --no-cache-dir -r /lm/requirements.txt

WORKDIR /lm
ENV FLASK_DEBUG=1
ENV FLASK_RUN_HOST 0.0.0.0
ENTRYPOINT [ "python3", "lifemonitor/api.py" ]

USER lm
