#!/bin/bash

kubectl create secret tls lifemonitor-tls --key ../certs/lm.key --cert ../certs/lm.crt