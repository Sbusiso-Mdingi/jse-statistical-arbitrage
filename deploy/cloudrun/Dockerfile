# Runtime for the monthly refit on Cloud Run. R with the heavy GARCH/copula
# packages baked in (compiling them at run time would be far too slow), plus
# Python, git and the Azure CLI. The application code comes from the GitHub
# clone at run time, so this image only rebuilds when the runtime or the R
# dependency set changes.
FROM rocker/r-ver:4.4.2

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      git openssh-client curl jq ca-certificates \
      python3 python3-venv python3-pip \
      libxml2-dev libssl-dev libcurl4-openssl-dev \
 && curl -sL https://aka.ms/InstallAzureCLIDeb | bash \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

# Mirrors the packages installed by r-lib/actions/setup-r-dependencies in CI.
RUN install2.r --error --skipinstalled \
      rugarch VineCopula jsonlite quantmod xts

COPY deploy/cloudrun/bootstrap.sh /usr/local/bin/bootstrap.sh
RUN chmod +x /usr/local/bin/bootstrap.sh

ENTRYPOINT ["/usr/local/bin/bootstrap.sh"]
