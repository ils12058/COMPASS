#!/usr/bin/env bash
set -euo pipefail

# Disposable Ubuntu GitHub runners only. FAC-5 observed a 21-minute apt update stall
# on the Azure mirror before Playwright or any test could start. Keep the runner's
# suites, components, signing keys and mirror metadata; replace only that mirror URI.
if [[ "${GITHUB_ACTIONS:-}" != "true" || "${RUNNER_OS:-}" != "Linux" ]]; then
  echo "Browser APT configuration requires a Linux GitHub Actions runner." >&2
  exit 1
fi

if [[ -f /etc/apt/apt-mirrors.txt ]]; then
  sudo sed -i -E 's|https?://azure\.archive\.ubuntu\.com/ubuntu|https://archive.ubuntu.com/ubuntu|g' /etc/apt/apt-mirrors.txt
fi

# Bound both connection and stalled-data waits. Failures still fail installation;
# package signatures, TLS verification and the full browser/test matrix stay intact.
sudo tee /etc/apt/apt.conf.d/80compass-browser-network >/dev/null <<'APT'
Acquire::Retries "2";
Acquire::http::Timeout "30";
Acquire::https::Timeout "30";
APT
