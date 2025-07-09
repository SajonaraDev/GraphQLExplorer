# GraphQLQeurier

This repository contains a small Python utility for executing GraphQL queries and exporting the results as CSV. The tool is designed to handle dynamic attribute selections so the resulting table adapts to the columns requested in the query.

## Requirements

- Python 3.12 or newer
- `requests` library (install via `pip install requests`)

## Usage

1. Write your GraphQL query to a file, for example `sample_query.graphql`.
2. Run the script with the GraphQL endpoint URL and the query file:

```bash
python3 query_graphql.py https://example.com/graphql sample_query.graphql -o result.csv
```

The optional `GRAPHQL_TOKEN` environment variable can be set if the endpoint requires bearer-token authentication.

The generated CSV contains a header row with dynamic column names. Each column corresponds to the attributes requested in the GraphQL query.
