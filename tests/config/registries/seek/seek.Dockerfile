FROM fairdom/seek:workflow

USER root

COPY data.tar.gz /tmp/
COPY entrypoint.sh /usr/local/bin

RUN cd /tmp && tar xzvf data.tar.gz \
    && chown -R www-data:www-data data \
    && mv data /seek/ \
    && rm -rf data.tar.gz \
    && chmod 755 /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

USER www-data
