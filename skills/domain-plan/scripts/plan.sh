#!/usr/bin/env bash
# domain-plan: the plan of a task in Upstream and its drift from the code. uv + PEP 723, stdlib only.
exec uv run --script "$(dirname "$0")/plan.py" "$@"
