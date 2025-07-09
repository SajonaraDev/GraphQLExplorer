import streamlit as st
import requests
import pandas as pd

# === CONFIG ===
AUTH_URL = "https://grasp.wtf/auth/realms/platform/protocol/openid-connect/token"
GRAPHQL_ENDPOINT = "https://grasp.wtf/dynamicdb/v1/graphql"
CLIENT_ID = "frontend"

# === AUTHENTICATION ===
def get_bearer_token(username, password):
    payload = {
        'grant_type': 'password',
        'client_id': CLIENT_ID,
        'username': username,
        'password': password,
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post(AUTH_URL, data=payload, headers=headers)

    if response.status_code != 200:
        raise Exception("Login fehlgeschlagen")

    return response.json().get("access_token")

# === GRAPHQL QUERY ===
def query_graphql(token, query):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    response = requests.post(GRAPHQL_ENDPOINT, headers=headers, json={"query": query})

    if response.status_code != 200:
        raise Exception("GraphQL-Fehler:\n" + response.text)

    return response.json()

# === RESULT TO TABLE ===
def extract_table(data):
    """Create a pandas DataFrame from the GraphQL response."""
    try:
        raw_items = data.get("data", {}).get("informationObjects", {}).get("data", [])
        rows = []

        for item in raw_items:
            row = {}
            for key, value in item.items():
                if key == "attributes" and isinstance(value, list):
                    for attr in value:
                        name = attr.get("attributeDefinitionSystemName")
                        attr_value = None
                        for k, v in attr.items():
                            if k == "attributeDefinitionSystemName":
                                continue
                            if v is None:
                                continue
                            if isinstance(v, dict) and "value" in v:
                                attr_value = v.get("value")
                                break
                            attr_value = v
                            break
                        row[name] = attr_value
                else:
                    row[key] = value
            rows.append(row)

        return pd.DataFrame(rows)
    except Exception as e:
        st.error(f"Fehler beim Parsen der Antwort: {e}")
        return pd.DataFrame()

# === STREAMLIT UI ===
st.title("GraphQL Explorer (grasp.wtf)")

with st.form("login_form"):
    username = st.text_input("Benutzername")
    password = st.text_input("Passwort", type="password")
    query = st.text_area("GraphQL Query", height=200, value="""
    query {
      informationObjects {
        data {
          id
          attributes {
            attributeDefinitionSystemName
            stringValue
          }
        }
      }
    }
    """)
    submitted = st.form_submit_button("Absenden")
    print(submitted)
if submitted:
    try:
        st.info("Authentifiziere...")
        token = get_bearer_token(username, password)
        st.success("Token erhalten!")

        st.info("Sende GraphQL-Query...")
        result = query_graphql(token, query)
        st.success("Antwort erhalten!")
        st.json(result)
        df = extract_table(result)
        st.dataframe(df)

    except Exception as e:
        st.error(f"Fehler: {e}")
