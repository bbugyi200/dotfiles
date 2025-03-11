FROM bbugyi/neovim:2025.03.11-4

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG USER_ID
ARG GROUP_ID

### create new user account ('docker')
RUN groupadd --gid $GROUP_ID docker && \
    useradd --no-log-init --create-home --uid $USER_ID --gid docker docker && \
    cp /bashrc /home/docker/.bashrc;

USER docker
