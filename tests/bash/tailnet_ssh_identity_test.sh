#!/bin/bash

# Render each host's managed Include and ask OpenSSH for the effective config.
# No connections or changes to the user's SSH configuration are made.

function set_up() {
  SSH_TEST_DIR="$(mktemp -d)"
}

function tear_down() {
  rm -rf "${SSH_TEST_DIR}"
}

function render_tailnet() {
  local host="$1"
  sed "s/\\.chezmoi\\.hostname/\"${host}\"/g" home/private_dot_ssh/private_tailnet.conf* |
    chezmoi execute-template >"${SSH_TEST_DIR}/tailnet.conf"
}

function write_existing_config() {
  local host="$1"
  printf 'Include %s/tailnet.conf\n' "${SSH_TEST_DIR}" >"${SSH_TEST_DIR}/config"
  if [[ "${host}" == "athena" ]]; then
    cat >>"${SSH_TEST_DIR}/config" <<'EOF'
Host github.com
  HostName ssh.github.com
  Port 443
  User git
  IdentityFile ~/.ssh/id_sase_service
  IdentitiesOnly yes
  ForwardAgent no
EOF
  fi
  cat >>"${SSH_TEST_DIR}/config" <<'EOF'
Host *
  ForwardAgent yes
EOF
}

function effective_config() {
  ssh -G -F "${SSH_TEST_DIR}/config" "$1" 2>/dev/null
}

function test_apollo_selects_its_own_github_identity() {
  render_tailnet apollo
  write_existing_config apollo
  local config
  config="$(effective_config github.com)"
  assert_contains "user git" "${config}"
  assert_contains "identitiesonly yes" "${config}"
  assert_contains "identityfile ~/.ssh/id_rsa" "${config}"
  assert_same "1" "$(printf '%s\n' "${config}" | grep -c '^identityfile ')"
}

function test_other_hosts_keep_their_github_settings() {
  local host before after
  for host in athena Kellys-MacBook-Pro apollo-other; do
    : >"${SSH_TEST_DIR}/tailnet.conf"
    write_existing_config "${host}"
    before="$(effective_config github.com)"
    render_tailnet "${host}"
    after="$(effective_config github.com)"
    assert_same "${before}" "${after}"
  done
}

function test_tailnet_forwarding_is_preserved() {
  local host target config
  for host in athena apollo Kellys-MacBook-Pro; do
    render_tailnet "${host}"
    write_existing_config "${host}"
    for target in athena apollo apollo-do mac; do
      config="$(effective_config "${target}")"
      assert_contains "forwardagent yes" "${config}"
    done
  done
}

function test_include_hook_hashes_the_template() {
  local rendered digest
  rendered="$(sed 's/\.chezmoi\.hostname/"athena"/g' home/.chezmoiscripts/run_onchange_after_ensure_ssh_tailnet_include.tmpl |
    chezmoi --source "${PWD}" execute-template)"
  digest="$(sha256sum home/private_dot_ssh/private_tailnet.conf* | cut -d ' ' -f 1)"
  assert_contains "# tailnet.conf: ${digest}" "${rendered}"
}
