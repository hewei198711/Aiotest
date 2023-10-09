#!/bin/sh

for i in $(docker ps -q --filter ancestor=aiotest:latest)
do
docker stop $i
done

sleep 10

for i in $(docker ps -a -q --filter ancestor=aiotest:latest)
do
docker rm $i
done