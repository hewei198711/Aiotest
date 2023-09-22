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