FROM bbugyi/neovim:2025.03.10-2 # See https://github.com/bbugyi200/docker-neovim

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG USER_ID
ARG GROUP_ID

### create new user account ('docker')
RUN groupadd --gid $GROUP_ID docker && \
        useradd --no-log-init --create-home --uid $USER_ID --gid docker docker
USER docker
