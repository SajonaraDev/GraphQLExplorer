# GraphQLQeurier

A small Streamlit based frontend for querying the GraphQL API. By default it
targets `https://grasp.wtf` but you can override this using the `BASE_URL`
environment variable.

## Usage

```bash
streamlit run graphql_frontend.py
```

Set the optional `BASE_URL` environment variable if you want to target a
different host.

The app requires username and password for authentication. After logging in you can provide:

- **classDefinitionSystemName** – single value used to filter information objects
- **Systemnamen** – comma separated list of attribute system names to query

The GraphQL query is generated automatically from these inputs and the result is
rendered as a table.
