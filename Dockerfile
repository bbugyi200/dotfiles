FROM bbugyi/neovim:2025.04.11-1

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG USER_ID
ARG GROUP_ID

### create new user account ('docker')
RUN groupadd --gid $GROUP_ID docker && \
    useradd --no-log-init --create-home --uid $USER_ID --gid docker docker;

### Install Python 3.12
RUN apt-get update && \
    apt-get install -y wget build-essential libssl-dev zlib1g-dev \
    libbz2-dev libreadline-dev libsqlite3-dev curl \
    libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev && \
    cd /tmp && \
    wget https://www.python.org/ftp/python/3.12.7/Python-3.12.7.tgz && \
    tar xzf Python-3.12.7.tgz && \
    cd Python-3.12.7 && \
    ./configure --enable-optimizations --with-ensurepip=install && \
    make -j $(nproc) && \
    make altinstall && \
    update-alternatives --install /usr/bin/python3 python3 /usr/local/bin/python3.12 1 && \
    cd / && \
    rm -rf /tmp/Python-3.12.7* && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*;

### Install bashunit
RUN cd / && \
    curl -s https://bashunit.typeddevs.com/install.sh | bash -s bin && \
    chown -R docker:docker /bin/bashunit;

USER docker
