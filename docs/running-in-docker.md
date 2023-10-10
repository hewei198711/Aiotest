## Running in Docker
### Docker Image
Use [Dockerfile](https://github.com/hewei198711/Aiotest/blob/main/Dockerfile) to create an aiotest image(assuming that the `Dockerfile` exists in the current working directory)

Dockerfile
```yml
FROM python:3.11-slim as base

FROM base as builder
RUN apt-get update && apt-get install -y git 
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt /build/requirements.txt
RUN python3 -m pip install -U pip && pip install -r /build/requirements.txt

FROM base
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
# turn off python output buffering
ENV PYTHONUNBUFFERED=1
USER root
WORKDIR /root/aiotest
EXPOSE 8089 5557
# ENTRYPOINT ["aiotest"]
```
```console
# Notice the dot at the end
docker build -t aiotest:latest .
```
### Docker Compose
Here's an example Docker Compose file that could be used to start both a master node, and worker nodes

**Distributed load test**
```yml
# docker-compose-master.yml
version: '3'
  
services:
  master:
    image: aiotest:latest
    ports:
     - "8089:8089"
     - "5557:5557"
    volumes:
      - ./:/root/aiotest
    command: aiotest -f aiotestfile.py --master --expect-workers 8 -d -u 8000 -r 400 -t 1800
```
```yml
# docker-compose-worker.yml
version: '3'
  
services:
  worker:
    image: aiotest:latest
    volumes:
      - ./:/root/aiotest
    command: aiotest -f aiotestfile.py --worker --master-host "192.168.0.10"
```
```console
# linux host:port 192.168.0.10:22, CPU:4
# Start master node
docker-compose -f docker-compose-master.yml up -d
```
```console
# linux host:port 192.168.0.11:22, CPU:4
# Start four worker node
docker-compose -f docker-compose-worker.yml up -d --scale worker=4
```
```console
# linux host:port 192.168.0.12:22, CPU:4
# Start four worker node
docker-compose -f docker-compose-worker.yml up -d --scale worker=4
```
**Stand-alone load test**
```yml
# docker-compose-local.yml
version: '3'
  
services:
  local:
    image: aiotest:latest
    ports:
     - "8089:8089"
     - "5557:5557"
    volumes:
      - ./:/root/aiotest
    command: aiotest -f aiotestfile.py -d -u 100 -r 10 -t 1800
```
```console
# linux host:port 192.168.0.12:22, CPU:4
# Start local node
docker-compose -f docker-compose-local.yml up
```