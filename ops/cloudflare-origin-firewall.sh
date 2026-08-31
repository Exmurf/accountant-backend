#!/usr/bin/env bash

set -euo pipefail

readonly V4_CHAIN="ACCOUNTANT_CF"
readonly V6_CHAIN="ACCOUNTANT_CF6"

# Published by Cloudflare at https://www.cloudflare.com/ips-v4 and /ips-v6.
# Keep these ranges in source control so a transient network failure cannot
# leave the production firewall half-configured during boot.
readonly CLOUDFLARE_V4=(
  "173.245.48.0/20"
  "103.21.244.0/22"
  "103.22.200.0/22"
  "103.31.4.0/22"
  "141.101.64.0/18"
  "108.162.192.0/18"
  "190.93.240.0/20"
  "188.114.96.0/20"
  "197.234.240.0/22"
  "198.41.128.0/17"
  "162.158.0.0/15"
  "104.16.0.0/13"
  "104.24.0.0/14"
  "172.64.0.0/13"
  "131.0.72.0/22"
)

readonly CLOUDFLARE_V6=(
  "2400:cb00::/32"
  "2606:4700::/32"
  "2803:f800::/32"
  "2405:b500::/32"
  "2405:8100::/32"
  "2a06:98c0::/29"
  "2c0f:f248::/32"
)

require_docker_chain() {
  local command="$1"
  if ! "$command" -n -L DOCKER-USER >/dev/null 2>&1; then
    echo "DOCKER-USER is unavailable; start Docker before applying the firewall." >&2
    exit 1
  fi
}

remove_jump() {
  local command="$1"
  local chain="$2"
  while "$command" -C DOCKER-USER -j "$chain" >/dev/null 2>&1; do
    "$command" -D DOCKER-USER -j "$chain"
  done
}

remove_chain() {
  local command="$1"
  local chain="$2"
  remove_jump "$command" "$chain"
  if "$command" -n -L "$chain" >/dev/null 2>&1; then
    "$command" -F "$chain"
    "$command" -X "$chain"
  fi
}

build_chain() {
  local command="$1"
  local chain="$2"
  shift 2
  local ranges=("$@")

  require_docker_chain "$command"
  "$command" -n -L "$chain" >/dev/null 2>&1 || "$command" -N "$chain"
  "$command" -F "$chain"
  "$command" -A "$chain" -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN

  local range
  for range in "${ranges[@]}"; do
    "$command" -A "$chain" -p tcp -s "$range" \
      -m multiport --dports 80,443 -j RETURN
  done

  "$command" -A "$chain" -p tcp -m multiport --dports 80,443 -j DROP
  "$command" -A "$chain" -j RETURN

  remove_jump "$command" "$chain"
  "$command" -I DOCKER-USER 1 -j "$chain"
}

apply() {
  build_chain iptables "$V4_CHAIN" "${CLOUDFLARE_V4[@]}"
  build_chain ip6tables "$V6_CHAIN" "${CLOUDFLARE_V6[@]}"
}

remove() {
  remove_chain iptables "$V4_CHAIN"
  remove_chain ip6tables "$V6_CHAIN"
}

status() {
  iptables -n -L "$V4_CHAIN" -v
  ip6tables -n -L "$V6_CHAIN" -v
}

case "${1:-}" in
  apply)
    apply
    ;;
  remove)
    remove
    ;;
  status)
    status
    ;;
  *)
    echo "Usage: $0 {apply|remove|status}" >&2
    exit 2
    ;;
esac
