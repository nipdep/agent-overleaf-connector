# Same toolchain as CI, for local and agent use:
#   docker build -f docker/Dockerfile -t paper-review .
#   docker run --rm -v "$PWD":/work paper-review build
FROM texlive/texlive:latest
RUN apt-get update && apt-get install -y --no-install-recommends python3-venv git \
    && rm -rf /var/lib/apt/lists/*
COPY . /src
RUN python3 -m venv /opt/pr && /opt/pr/bin/pip install /src
ENV PATH=/opt/pr/bin:$PATH
WORKDIR /work
RUN git config --system --add safe.directory /work
ENTRYPOINT ["paper-review"]
