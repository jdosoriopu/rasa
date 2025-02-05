FROM python:3.7-slim as base

RUN apt-get update -qq \
 && apt-get install -y --no-install-recommends \
    # required by psycopg2 at build and runtime
    libpq-dev \
     # required for health check
    curl \
 && apt-get autoremove -y

FROM base as builder

RUN apt-get update -qq && \
  apt-get install -y --no-install-recommends \
  build-essential \
  wget \
  openssh-client \
  graphviz-dev \
  pkg-config \
  git-core \
  openssl \
  libssl-dev \
  libffi6 \
  libffi-dev \
  libpng-dev

# install poetry
# keep this in sync with the version in pyproject.toml and Dockerfile
ENV POETRY_VERSION 1.0.5
RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python
ENV PATH "/root/.poetry/bin:/opt/venv/bin:${PATH}"


RUN git clone https://github.com/jdosoriopu/rasa.git

# copy files
COPY ./rasa /build/
COPY rasa/docker/configs/config_pretrained_embeddings_spacy_en_duckling.yml /build/config.yml

# download mitie model
RUN wget -P /build/data/ https://s3-eu-west-1.amazonaws.com/mitie/total_word_feature_extractor.dat

# change working directory
WORKDIR /build

# install dependencies
RUN python -m venv /opt/venv && \
  . /opt/venv/bin/activate && \
  pip install --no-cache-dir -U 'pip<20' && \
  poetry install --extras full --no-dev --no-root --no-interaction && \
  make install-mitie && \
  poetry build -f wheel -n && \
  pip install --no-deps dist/*.whl && \
  rm -rf dist *.egg-info

# make sure we use the virtualenv
ENV PATH="/opt/venv/bin:$PATH"

# spacy link
RUN python -m spacy download en_core_web_md && \
    python -m spacy download de_core_news_sm && \
    python -m spacy link en_core_web_md en && \
    python -m spacy link de_core_news_sm de

# Install and link spacy models
RUN python -m spacy download es_core_news_sm

RUN python -m spacy link es_core_news_sm es

# start a new build stage
FROM base as runner

# copy everything from /opt
COPY --from=builder /opt/venv /opt/venv

# make sure we use the virtualenv
ENV PATH="/opt/venv/bin:$PATH"

# update permissions & change user to not run as root
WORKDIR /app
RUN chgrp -R 0 /app && chmod -R g=u /app
USER 1001

# Create a volume for temporary data
VOLUME /tmp

# change shell
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# the entry point
EXPOSE 5005
ENTRYPOINT ["rasa"]
CMD ["--help"]