#!/bin/sh

for i in $(docker ps -q --filter ancestor=aiotest:0.5.7)
do
docker stop $i
done

sleep 10

for i in $(docker ps -a -q --filter ancestor=aiotest:0.5.7)
do
docker rm $i
done