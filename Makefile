
SHELL := /bin/bash

all: images

images: lifemonitor

lifemonitor: docker/lifemonitor.Dockerfile
	docker build -f docker/lifemonitor.Dockerfile -t crs4/lifemonitor .

#docker-compose-dev.yml: docker/docker-compose-template.yml
#  sed -e "s^LOCAL_PATH^$${PWD}^" \
#      -e "s^USER_UID^$$(id -u)^" \
#      -e "s^USER_GID^$$(id -g)^" \
#      -e "s^DEV=false^DEV=true^" \
#      -e "s^#DEV ^^" \
#      < docker/docker-compose-template.yml > docker-compose-dev.yml


#docker-compose.yml: docker/docker-compose-template.yml
#  sed -e "s^LOCAL_PATH^$${PWD}^" \
#      -e "s^USER_UID^$$(id -u)^" \
#      -e "s^USER_GID^$$(id -g)^" \
#      < docker/docker-compose-template.yml > docker-compose.yml

startdev: docker/docker-compose-dev.yml
	docker-compose -f ./docker-compose-dev.yml up -d

stopdev:
	docker-compose -f ./docker-compose-dev.yml down

start: images docker-compose.yml
	docker-compose -f ./docker-compose.yml up -d

stop:
	docker-compose -f ./docker-compose.yml down

clean: stop

.PHONY: all images lifemonitor start stop startdev stopdev clean
