# GraphQLQeurier

A small Streamlit based frontend for querying the GraphQL API. By default it
targets `https://grasp.wtf` but you can override this using the `BASE_URL`
environment variable or by entering a different URL in the app.

## Usage

```bash
streamlit run graphql_frontend.py
```

You can specify a different server either by setting the `BASE_URL`
environment variable or by filling in the **Base URL** field in the form.

The app requires username and password for authentication. After logging in you can provide:

- **classDefinitionSystemName** – single value used to filter information objects
- **Systemnamen** – comma separated list of attribute system names to query

The GraphQL query is generated automatically from these inputs and the result is
rendered as a table.
