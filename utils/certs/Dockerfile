FROM golang:1.15.2-alpine3.12

# install git
RUN apk update && apk upgrade && \
    apk add --no-cache bash git openssh

# install minica
RUN go get github.com/jsha/minica

# Declare an unprivileged user
ARG CA_USER=ca

# Create a user 'lm' with HOME at /lm
RUN addgroup -S ${CA_USER} && adduser -S ${CA_USER} -G ${CA_USER}

# create and set permissions
RUN mkdir /certs && chown -R ${CA_USER}:${CA_USER} /certs

# Set the user
USER ${CA_USER}

# set work dir
WORKDIR /certs
