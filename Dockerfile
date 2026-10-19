# CLI image. bcftools is only needed by 'clinvar-history fetch gnomad' (remote tabix reads).
FROM python@sha256:b685a4fa58bb19d1814d78a1ec0f0208f351452724f78b20212c984d6e124a34

RUN apt-get update \
    && apt-get install -y --no-install-recommends bcftools curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY migrations ./migrations
COPY sql ./sql
COPY config ./config
COPY workflow/schemas ./workflow/schemas
COPY tests ./tests
# Editable install keeps migrations/ and sql/ at the paths the package reads them from.
RUN pip install --no-cache-dir -e ".[postgres,dev]"

ENV CLINVAR_HISTORY_DATA_DIR=/data
VOLUME ["/data"]
ENTRYPOINT ["clinvar_history"]
CMD ["--help"]
