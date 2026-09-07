"""Summarise the per-domain side file that Web Data Commons ships with a subset.

`GeoCoordinates_domain_stats.csv` covers every domain in the whole subset, not a
sample of it, so it answers corpus-wide questions cheaply: how the subset's
quads are spread over domains, and which GeoCoordinates properties domains
actually publish. Run it as:

    python scripts/domain_stats.py GeoCoordinates_domain_stats.csv
"""

import ast
import csv
import json
import sys
from collections import Counter

FIELDS = ("Domain", "#Quads of Subset", "#Entities of class", "Properties and Density")


def summarise(rows):
    """Return corpus-wide figures over the rows of the domain stats file."""
    domains = quads = entities = 0
    properties = Counter()
    density = Counter()
    combinations = Counter()
    quads_per_domain = []
    for row in rows:
        domains += 1
        quads += int(row[FIELDS[1]])
        entities += int(row[FIELDS[2]])
        published = ast.literal_eval(row[FIELDS[3]])
        properties.update(published.keys())
        density.update(published)
        combinations[",".join(sorted(published))] += 1
        quads_per_domain.append(int(row[FIELDS[1]]))
    quads_per_domain.sort()
    return {
        "domains": domains,
        "quads": quads,
        "entities_of_class": entities,
        "quads_per_domain": {
            "median": quads_per_domain[domains // 2],
            "p90": quads_per_domain[int(domains * 0.9)],
            "p99": quads_per_domain[int(domains * 0.99)],
            "max": quads_per_domain[-1],
        },
        "domains_publishing_property": dict(properties.most_common(20)),
        "mean_density_where_published": {
            name: round(density[name] / properties[name], 3) for name, _ in properties.most_common(20)
        },
        "top_property_combinations": dict(combinations.most_common(12)),
    }


def main():
    """Print the summary of the file named on the command line."""
    with open(sys.argv[1], encoding="utf-8", newline="") as handle:
        summary = summarise(csv.DictReader(handle, delimiter="\t"))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
