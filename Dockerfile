FROM debian:12-slim

# Install apt dependencies
RUN --mount=target=/var/lib/apt/lists,type=cache,sharing=locked \
    --mount=target=/var/cache/apt,type=cache,sharing=locked \
<<EOF
set -xe
rm /etc/apt/apt.conf.d/docker-clean

# install python
apt-get update
apt-get install -y python3 python3-pip python3-venv
# install git dependency for app
apt-get install -y git
EOF

# Setup venv
RUN python3 -m venv /venv && /venv/bin/pip install --upgrade pip setuptools wheel

# Install python modules dependencies
COPY requirements.txt requirements.txt
RUN /venv/bin/pip install -r requirements.txt

# Change user at this point, because we do not want to run it as root
USER nobody

# Copy app
WORKDIR /app
COPY --chown=nobody:nobody . /app

EXPOSE 80
ENTRYPOINT ["/venv/bin/uwsgi", "--http", ":80", "--master", "-w", "wsgi:app"]
