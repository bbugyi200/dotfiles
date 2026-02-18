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
    libbz2-dev libreadline-dev libsqlite3-dev curl ripgrep \
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

### Install Node.js (for prettier)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g prettier && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*;

### Install stylua (Lua formatter)
RUN curl -fsSL https://github.com/JohnnyMorganz/StyLua/releases/download/v2.0.2/stylua-linux-x86_64.zip -o /tmp/stylua.zip && \
    unzip /tmp/stylua.zip -d /usr/local/bin/ && \
    chmod +x /usr/local/bin/stylua && \
    rm /tmp/stylua.zip

### Install keep-sorted (build from source to avoid GLIBC issues)
RUN curl -fsSL https://go.dev/dl/go1.22.5.linux-amd64.tar.gz | tar -C /usr/local -xzf - && \
    /usr/local/go/bin/go install github.com/google/keep-sorted@v0.7.1 && \
    mv /root/go/bin/keep-sorted /usr/local/bin/ && \
    rm -rf /usr/local/go /root/go

### Install bashunit
RUN cd / && \
    curl -s https://bashunit.typeddevs.com/install.sh | bash -s bin && \
    chown -R docker:docker /bin/bashunit;

USER docker
