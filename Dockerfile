FROM bbugyi/neovim:2025.03.15-11

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG USER_ID
ARG GROUP_ID

### create new user account ('docker')
RUN groupadd --gid $GROUP_ID docker && \
    useradd --no-log-init --create-home --uid $USER_ID --gid docker docker;

### Install bashunit
RUN cd / && \
    curl -s https://bashunit.typeddevs.com/install.sh | bash -s bin && \
    chown -R docker:docker /bin/bashunit;

USER docker
