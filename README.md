# GraphQLQeurier

A small Streamlit based frontend for querying the `grasp.wtf` GraphQL API.

## Usage

```bash
streamlit run graphql_frontend.py
```

The app requires username and password for authentication. After logging in you can provide:

- **classDefinitionSystemName** – single value used to filter information objects
- **Systemnamen** – comma separated list of attribute system names to query

The GraphQL query is generated automatically from these inputs and the result is
rendered as a table.
