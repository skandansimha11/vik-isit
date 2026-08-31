"""DEPRECATED - do not run.

This script used to overwrite KPISource.parse_config for the Tier-A KPIs and, in
doing so, stripped the tabular lookup keys the extraction pipeline needed. The
Tier-A KPIs are now computed by `python -m app.tier_a_pipeline` from the curated
`data/tier_a/` layer and do not use parse_config lookups at all.
"""

import sys

if __name__ == "__main__":
    sys.exit("Deprecated. Run `python -m app.tier_a_pipeline` instead.")
