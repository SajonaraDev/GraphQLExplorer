import os
import streamlit as st
import requests
import pandas as pd

# === CONFIG ===
BASE_URL = os.getenv("BASE_URL", "https://grasp.wtf").rstrip("/")
AUTH_URL = f"{BASE_URL}/auth/realms/platform/protocol/openid-connect/token"
GRAPHQL_ENDPOINT = f"{BASE_URL}/dynamicdb/v1/graphql"
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

# === QUERY BUILDER ===
def build_query(class_name: str, system_names: list[str]) -> str:
    """Create GraphQL query string from user inputs."""
    names = ",".join(f'"{name.strip()}"' for name in system_names if name.strip())
    return f"""
    query informationObjects {{
        informationObjects(
            options: {{ filterBy: {{ classDefinitionSystemName: {{ value: \"{class_name}\" }} }} }}
        ) {{
            data {{
                id
                attributes(systemNames: [{names}]) {{
                    attributeDefinitionSystemName
                    ... on InformationDateAttribute {{
                        dateValue
                    }}
                    ... on InformationStringAttribute {{
                        stringValue
                    }}
                    ... on InformationEnumAttribute {{
                        enumValue {{
                            value
                        }}
                        enumValueId
                    }}
                    ... on InformationNumberAttribute {{
                        numberValue
                    }}
                    ... on InformationReferenceAttribute {{
                        informationObjectReferenceValueIds
                    }}
                }}
            }}
        }}
    }}
    """

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
st.title(f"GraphQL Explorer ({BASE_URL})")

with st.form("login_form"):
    username = st.text_input("Benutzername")
    password = st.text_input("Passwort", type="password")
    class_name = st.text_input("classDefinitionSystemName", value="Gesch\u00e4ftsprozess")
    system_names_input = st.text_input(
        "Systemnamen (kommagetrennt)",
        value="BCM_RTO_min, Bezeichnung, Beschreibung",
    )
    submitted = st.form_submit_button("Absenden")

if submitted:
    try:
        st.info("Authentifiziere...")
        token = get_bearer_token(username, password)
        st.success("Token erhalten!")

        system_names = [name.strip() for name in system_names_input.split(",") if name.strip()]
        query = build_query(class_name, system_names)
        st.code(query, language="graphql")
        st.info("Sende GraphQL-Query...")
        result = query_graphql(token, query)
        st.success("Antwort erhalten!")
        st.json(result)
        df = extract_table(result)
        st.dataframe(df)

    except Exception as e:
        st.error(f"Fehler: {e}")
