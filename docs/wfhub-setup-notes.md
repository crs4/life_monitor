
# Bringing up WorkflowHub with HTTPS configuration

In this example we're going to use the same self-signed certificates generated
by our Makefile, which we're going to mount on `/nginx/certs` on the
WorkflowHub Docker container.

Apply the following modifications to the WorkflowHub `nginx.conf` file:


```diff
@@ -63,7 +63,10 @@ http {
         # gzip_http_version 1.1;
 
         server {
-               listen 3000;
+               listen 3000 ssl default_server;
+               ssl_certificate /nginx/certs/lm.crt;
+               ssl_certificate_key /nginx/certs/lm.key;
                root /seek/public;
                client_max_body_size 2G;
                location / {
@@ -72,6 +75,7 @@ http {
                     proxy_set_header   X-Real-IP $remote_addr;
                     proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
                     proxy_set_header   X-Forwarded-Host $server_name;
+                    proxy_set_header   X-Forwarded-Proto $scheme;
                }
                 location ^~ /(assets)/  {
                                gzip_static on;
```

You can change `docker/nginx.conf` on the WorkflowHub git repo (currently on
the "workflow" branch of https://github.com/seek4science/seek) and rebuild the
image locally, or overwrite the `/etc/nginx` dir on the WorkflowHub container
with a bind mount. For instance, suppose you have copied the contents of
`/etc/nginx` from the WorkflowHub container to `/tmp/etc_nginx`. Also suppose
our certificates are on `/tmp/certs`. Finally, we're going to map `lm.org` (the
hostname in the self-signed certificates) to the physical host's (internal) IP
address (you can get it with `ifconfig` on Linux): suppose this is
`192.168.1.167`. We're going to run WorkflowHub on a single Docker container,
and put it on a network called `seek_default`.

```
docker network create seek_default
docker run -d --network seek_default -p 3000:3000 \
  -v /tmp/etc_nginx:/etc/nginx:ro -v /tmp/certs:/nginx/certs:ro \
  --add-host lm.org:192.168.1.167 --name wfhub fairdom/seek:workflow
```

Also add a `192.168.1.167 lm.org` entry to the physical host's `/etc/hosts`.
