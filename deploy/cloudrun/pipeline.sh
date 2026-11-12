#!/usr/bin/env bash
# One H17 refit (research/PROTOCOL.md), run as a Cloud Run job inside a fresh clone (see bootstrap.sh) on
# 1 January, 1 April and 1 September. Prices are downloaded fresh, the models are refitted on sessions to the
# month end just passed, the parity tests must pass, and the result is pushed to a refit/<date> branch.
# Nothing is deployed and main is never touched: a person reviews the branch, merges it, runs
# research/refit_apply.py and deploys, and the refit is used from the session after that.
#
#   REFIT_DATE=2026-10-31 BRANCH_PREFIX=dryrun   # overrides for a manual test run
set -euo pipefail

git config user.name "cloud-run-refit[bot]"
git config user.email "cloud-run-refit@users.noreply.github.com"

T="${REFIT_DATE:-$(python3 -c 'import datetime as d; t = (d.datetime.now(d.timezone.utc) + d.timedelta(hours=2)).date(); print(t.replace(day=1) - d.timedelta(days=1))')}"
case "${T:5:5}" in
  03-31|08-31|12-31) KIND=scheduled ;;
  *) [ -n "${REFIT_DATE:-}" ] || { echo "no refit is due for the month ending $T" >&2; exit 1; }; KIND=test ;;
esac
BRANCH="${BRANCH_PREFIX:-refit}/$T"
if git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null; then
  echo "branch $BRANCH already exists; nothing to do" >&2; exit 1
fi

Rscript research/00_data.R
Rscript research/refit.R "$T"

# Python runs in an isolated venv (the base image is R-first).
python3 -m venv /tmp/parity
/tmp/parity/bin/pip install --no-cache-dir -q -r service/requirements.txt pytest
/tmp/parity/bin/python research/refit_export.py "$T" "$KIND"
# Has Yahoo changed the adjusted closes the frozen rules read? Reports only (PROTOCOL.md, amendment of 12 November 2026).
/tmp/parity/bin/python research/h15_data.py
/tmp/parity/bin/python research/yahoo_check.py "$T" || true

# Parity tests, including the new refit against its own reference sessions.
( cd service && PATH=/tmp/parity/bin:$PATH python -m pytest -q tests )

git checkout -b "$BRANCH"
git add data/refits.json "research/results/refit_$T.json" "research/results/yahoo_check_$T.json" 2>/dev/null || git add data/refits.json "research/results/refit_$T.json"
git commit -m "Refit to $T ($KIND), waiting for review and deploy"
git push origin "HEAD:refs/heads/$BRANCH"
echo "pushed $BRANCH; nothing deployed"
