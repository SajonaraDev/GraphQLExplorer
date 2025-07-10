import os
import streamlit as st
import requests
import pandas as pd

# Configure page and layout
st.set_page_config(page_title="GraphQL Explorer", layout="wide")

# Make the main container a bit wider (80% of the page width)
st.markdown(
    """
    <style>
        .main .block-container {
            max-width: 80%;
            padding-top: 1rem;
            padding-right: 1rem;
            padding-left: 1rem;
            margin: auto;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# === CONFIG ===
DEFAULT_BASE_URL = os.getenv("BASE_URL", "https://grasp.wtf").rstrip("/")
CLIENT_ID = "frontend"

# === AUTHENTICATION ===
def get_bearer_token(base_url: str, username: str, password: str):
    payload = {
        'grant_type': 'password',
        'client_id': CLIENT_ID,
        'username': username,
        'password': password,
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    auth_url = f"{base_url}/auth/realms/platform/protocol/openid-connect/token"
    response = requests.post(auth_url, data=payload, headers=headers)

    if response.status_code != 200:
        raise Exception("Login fehlgeschlagen")

    return response.json().get("access_token")

# === GRAPHQL QUERY ===
def query_graphql(base_url: str, token: str, query: str):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    graphql_endpoint = f"{base_url}/dynamicdb/v1/graphql"
    response = requests.post(graphql_endpoint, headers=headers, json={"query": query})

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
        )  {{
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
                        informationObjectReferenceValues {{
                            id
                            classDefinitionSystemName
                            attributes {{
                                attributeDefinitionSystemName
                                ... on InformationStringAttribute {{
                                    stringValue
                                }}
                                ... on InformationNumberAttribute {{
                                    numberValue
                                }}
                                ... on InformationDateAttribute {{
                                    dateValue
                                }}
                                ... on InformationEnumAttribute {{
                                    enumValue {{
                                        value
                                    }}
                                }}
                            }}
                            keyAttribute {{
                                stringValue
                            }}
                        }}
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
                        if not name:
                            continue

                        # Handle reference attributes separately so that
                        # attributes of the referenced object become their own
                        # columns. They are prefixed with the referenced
                        # classDefinitionSystemName.
                        ref_values = attr.get("informationObjectReferenceValues")
                        if isinstance(ref_values, list) and ref_values:
                            # Store ids as the main column value
                            row[name] = ",".join(
                                str(i) for i in attr.get("informationObjectReferenceValueIds", [])
                            )

                            for ref in ref_values:
                                prefix = ref.get("classDefinitionSystemName", "")
                                for ref_attr in ref.get("attributes", []):
                                    ref_attr_name = ref_attr.get("attributeDefinitionSystemName")
                                    if not ref_attr_name:
                                        continue
                                    ref_value = None
                                    for rk, rv in ref_attr.items():
                                        if rk == "attributeDefinitionSystemName":
                                            continue
                                        if rv is None:
                                            continue
                                        if isinstance(rv, dict) and "value" in rv:
                                            ref_value = rv.get("value")
                                            break
                                        ref_value = rv
                                        break
                                    col_name = f"{prefix}_{ref_attr_name}" if prefix else ref_attr_name
                                    row[col_name] = ref_value
                        else:
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
st.title("GraphQL Explorer")

with st.form("login_form"):
    base_url = st.text_input("Base URL", value=DEFAULT_BASE_URL)
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
        base_url = base_url.rstrip("/")
        st.info("Authentifiziere...")
        token = get_bearer_token(base_url, username, password)
        st.success("Token erhalten!")

        system_names = [name.strip() for name in system_names_input.split(",") if name.strip()]
        query = build_query(class_name, system_names)
        with st.expander("GraphQL Query"):
            st.code(query, language="graphql")
        st.info("Sende GraphQL-Query...")
        result = query_graphql(base_url, token, query)
        st.success("Antwort erhalten!")
        st.json(result)
        df = extract_table(result)
        st.dataframe(df)

    except Exception as e:
        st.error(f"Fehler: {e}")
