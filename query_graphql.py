import argparse
import csv
import json
import os
import sys
import requests


def load_query(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def get_attribute_value(attribute: dict):
    """Extract the actual value from a GraphQL attribute payload."""
    for key, value in attribute.items():
        if key in {"attributeDefinitionSystemName", "__typename"}:
            continue
        if isinstance(value, dict):
            # handle nested structures such as enumValue { value }
            if "value" in value:
                return value["value"]
        elif value is not None:
            return value
    return None


def parse_information_objects(payload: dict):
    objects = payload.get("data", {}).get("informationObjects", {}).get("data", [])
    rows = []
    attribute_names = set()
    for obj in objects:
        row = {"id": obj.get("id")}
        for attr in obj.get("attributes", []):
            name = attr.get("attributeDefinitionSystemName")
            value = get_attribute_value(attr)
            row[name] = value
            attribute_names.add(name)
        rows.append(row)
    ordered_names = ["id"] + sorted(attribute_names)
    return ordered_names, rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute a GraphQL query and output a table")
    parser.add_argument("endpoint", help="GraphQL endpoint URL")
    parser.add_argument("query_file", help="File containing the GraphQL query")
    parser.add_argument("-o", "--output", help="Path to output CSV file. Default: stdout")
    args = parser.parse_args()

    headers = {"Content-Type": "application/json"}
    token = os.environ.get("GRAPHQL_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    query = load_query(args.query_file)
    response = requests.post(args.endpoint, json={"query": query}, headers=headers)
    response.raise_for_status()
    result = response.json()

    headers_row, rows = parse_information_objects(result)

    if args.output:
        fh = open(args.output, "w", newline="", encoding="utf-8")
    else:
        fh = sys.stdout

    writer = csv.DictWriter(fh, fieldnames=headers_row)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in headers_row})

    if args.output:
        fh.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
