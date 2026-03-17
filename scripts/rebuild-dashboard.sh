#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/../offgas_dashboard_linked"
npm install
npm run build
