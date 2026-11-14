#!/bin/bash

#################################################################################
# Regression tests for the host-agnostic whisper_run wrapper.                   #
#################################################################################

WRAPPER="${PWD}/home/bin/executable_whisper_run"

function set_up() {
  test_tmp="$(mktemp -d)"
  test_home="${test_tmp}/home"
  fake_bin="${test_tmp}/bin"
  sys_bin="${test_tmp}/sysbin"
  calls_file="${test_tmp}/calls.txt"
  stdout_file="${test_tmp}/stdout.txt"
  stderr_file="${test_tmp}/stderr.txt"
  fake_tool_dir="${test_home}/.local/share/uv/tools"

  mkdir -p "${fake_bin}" "${sys_bin}" "${test_home}"
  touch "${calls_file}"
  write_host_stubs
  write_uv_stub
  write_nvidia_smi_stub 0
  write_nproc_stub 8
  write_whisper_stub
}

function tear_down() {
  rm -rf "${test_tmp}"
}

function write_host_stubs() {
  local tool
  for tool in bash mkdir rm nice; do
    ln -s "$(command -v "${tool}")" "${sys_bin}/${tool}"
  done
}

function write_uv_stub() {
  cat >"${fake_bin}/uv" <<'EOF'
#!/bin/bash
printf 'uv %s\n' "$*" >>"${CALLS_FILE}"
if [[ "$1" == "tool" && "$2" == "dir" ]]; then
  printf '%s\n' "${FAKE_TOOL_DIR}"
  exit 0
fi
printf 'unexpected uv arguments: %s\n' "$*" >&2
exit 64
EOF
  chmod +x "${fake_bin}/uv"
}

function write_nvidia_smi_stub() {
  local rc="${1:-0}"
  cat >"${fake_bin}/nvidia-smi" <<EOF
#!/bin/bash
printf 'nvidia-smi %s\n' "\$*" >>"\${CALLS_FILE}"
exit ${rc}
EOF
  chmod +x "${fake_bin}/nvidia-smi"
}

function write_nproc_stub() {
  local count="${1:-8}"
  cat >"${fake_bin}/nproc" <<EOF
#!/bin/bash
printf 'nproc %s\n' "\$*" >>"\${CALLS_FILE}"
printf '%s\n' "\${FAKE_NPROC:-${count}}"
EOF
  chmod +x "${fake_bin}/nproc"
}

function write_whisper_stub() {
  cat >"${fake_bin}/whisper-ctranslate2" <<'EOF'
#!/bin/bash
printf 'whisper-ctranslate2 %s\n' "$*" >>"${CALLS_FILE}"
printf 'LD_LIBRARY_PATH=%s\n' "${LD_LIBRARY_PATH:-}" >>"${CALLS_FILE}"
exit 0
EOF
  chmod +x "${fake_bin}/whisper-ctranslate2"
}

function write_nvidia_libs() {
  mkdir -p "${fake_tool_dir}/whisper-ctranslate2/lib/python3.12/site-packages/nvidia/cublas/lib"
  mkdir -p "${fake_tool_dir}/whisper-ctranslate2/lib/python3.12/site-packages/nvidia/cudnn/lib"
}

function run_wrapper() {
  PATH="${fake_bin}:${sys_bin}:/usr/bin:/bin" \
    HOME="${test_home}" \
    CALLS_FILE="${calls_file}" \
    FAKE_TOOL_DIR="${fake_tool_dir}" \
    FAKE_NPROC="${FAKE_NPROC:-8}" \
    WHISPER_DEVICE="${WHISPER_DEVICE:-}" \
    WHISPER_MODEL="${WHISPER_MODEL:-}" \
    bash "${WRAPPER}" "$@" >"${stdout_file}" 2>"${stderr_file}"
}

function stderr_text() {
  cat "${stderr_file}"
}

function calls_text() {
  cat "${calls_file}"
}

function test_auto_with_gpu_chooses_cuda() {
  write_nvidia_libs
  write_nvidia_smi_stub 0

  WHISPER_DEVICE="" FAKE_NPROC=8 run_wrapper in.mp4 --output_format srt >/dev/null 2>&1 || true

  assert_contains "whisper_run: device=cuda compute=float16 model=large-v3-turbo" "$(stderr_text)"
  assert_contains "--device cuda" "$(calls_text)"
  assert_contains "--compute_type float16" "$(calls_text)"
  assert_contains "--model large-v3-turbo" "$(calls_text)"
  assert_contains "/cublas/lib" "$(calls_text)"
  assert_contains "/cudnn/lib" "$(calls_text)"
}

function test_auto_where_smi_fails_chooses_cpu() {
  write_nvidia_libs
  write_nvidia_smi_stub 1

  WHISPER_DEVICE="" FAKE_NPROC=8 run_wrapper in.mp4 >/dev/null 2>&1 || true

  assert_contains "whisper_run: device=cpu compute=int8" "$(stderr_text)"
  assert_contains "--device cpu" "$(calls_text)"
  assert_contains "--compute_type int8" "$(calls_text)"
  assert_contains "--threads 4" "$(calls_text)"
}

function test_auto_without_nvidia_dir_chooses_cpu() {
  write_nvidia_smi_stub 0

  WHISPER_DEVICE="" FAKE_NPROC=8 run_wrapper in.mp4 >/dev/null 2>&1 || true

  assert_contains "whisper_run: device=cpu compute=int8" "$(stderr_text)"
  assert_contains "--device cpu" "$(calls_text)"
}

function test_device_cpu_forces_cpu() {
  write_nvidia_libs
  write_nvidia_smi_stub 0

  WHISPER_DEVICE=cpu FAKE_NPROC=8 run_wrapper in.mp4 >/dev/null 2>&1 || true

  assert_contains "whisper_run: device=cpu" "$(stderr_text)"
  assert_contains "--device cpu" "$(calls_text)"
}

function test_device_cuda_without_libs_fails() {
  write_nvidia_smi_stub 0

  local rc
  if WHISPER_DEVICE=cuda FAKE_NPROC=8 run_wrapper in.mp4 >/dev/null 2>&1; then rc=0; else rc=$?; fi

  assert_same "1" "${rc}"
  assert_contains "CUDA requested" "$(stderr_text)"
}

function test_model_override() {
  write_nvidia_smi_stub 1

  WHISPER_DEVICE="" WHISPER_MODEL="small" FAKE_NPROC=8 run_wrapper in.mp4 >/dev/null 2>&1 || true

  assert_contains "model=small" "$(stderr_text)"
  assert_contains "--model small" "$(calls_text)"
}

function test_user_args_pass_through_after_defaults() {
  write_nvidia_smi_stub 1

  WHISPER_DEVICE="" FAKE_NPROC=8 run_wrapper in.mp4 --language en --model tiny >/dev/null 2>&1 || true

  assert_contains "--model large-v3-turbo" "$(calls_text)"
  assert_contains "--language en --model tiny" "$(calls_text)"
}

function test_cpu_thread_count_is_half_nproc() {
  write_nvidia_smi_stub 1

  WHISPER_DEVICE="" FAKE_NPROC=8 run_wrapper in.mp4 >/dev/null 2>&1 || true
  assert_contains "--threads 4" "$(calls_text)"

  : >"${calls_file}"
  WHISPER_DEVICE="" FAKE_NPROC=1 run_wrapper in.mp4 >/dev/null 2>&1 || true
  assert_contains "--threads 1" "$(calls_text)"
}
