FROM bbugyi/neovim:2025.04.11-1

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG USER_ID
ARG GROUP_ID

### create new user account ('docker')
RUN groupadd --gid $GROUP_ID docker && \
    useradd --no-log-init --create-home --uid $USER_ID --gid docker docker;

### Install Python 3.12
RUN apt-get update && \
    apt-get install -y software-properties-common && \
    add-apt-repository -y ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y python3.12 python3.12-venv python3.12-dev && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*;

### Install bashunit
RUN cd / && \
    curl -s https://bashunit.typeddevs.com/install.sh | bash -s bin && \
    chown -R docker:docker /bin/bashunit;

USER docker
