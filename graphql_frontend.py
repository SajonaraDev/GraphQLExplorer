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

ATTRIBUTE_FRAGMENT = """
                    attributeDefinitionSystemName
                    ... on InformationDateAttribute {
                        dateValue
                    }
                    ... on InformationStringAttribute {
                        stringValue
                    }
                    ... on InformationEnumAttribute {
                        enumValue {
                            value
                        }
                        enumValueId
                    }
                    ... on InformationNumberAttribute {
                        numberValue
                    }
                     ... on InformationReferenceAttribute {
                        informationObjectReferenceValueIds
                        informationObjectReferenceValues {
                            id
                            classDefinitionSystemName
                            attributes {
                                attributeDefinitionSystemName
                                ... on InformationStringAttribute {
                                    stringValue
                                }
                                ... on InformationNumberAttribute {
                                    numberValue
                                }
                                ... on InformationDateAttribute {
                                    dateValue
                                }
                                ... on InformationEnumAttribute {
                                    enumValue {
                                        value
                                    }
                                }
                            }
                            keyAttribute {
                                stringValue
                            }
                        }
                    }
"""


def build_query(class_name: str, system_names: list[str]) -> str:
    """Create GraphQL query string from user inputs."""
    names = ",".join(f'"{name.strip()}"' for name in system_names if name.strip())
    attr_clause = f"(systemNames: [{names}])" if names else ""
    return f"""
    query informationObjects {{
        informationObjects(
            options: {{ filterBy: {{ classDefinitionSystemName: {{ value: \"{class_name}\" }} }} }}
        )  {{
            data {{
                id
                clientSystemName
                attributes{attr_clause} {{
{ATTRIBUTE_FRAGMENT}
                }}
            }}
        }}
    }}
    """

def build_relationship_query(
    from_class: str,
    from_id: str,
    to_class: str,
    to_id: str,
    rel_attrs: list[str],
    from_attrs: list[str],
    to_attrs: list[str],
    include_from: bool,
    include_to: bool,
) -> str:
    """Create GraphQL query string for information relationships."""

    rel_names = ",".join(f'"{n.strip()}"' for n in rel_attrs if n.strip())
    from_names = ",".join(f'"{n.strip()}"' for n in from_attrs if n.strip())
    to_names = ",".join(f'"{n.strip()}"' for n in to_attrs if n.strip())

    rel_attr_clause = f"(systemNames: [{rel_names}])" if rel_names else ""
    from_attr_clause = f"(systemNames: [{from_names}])" if from_names else ""
    to_attr_clause = f"(systemNames: [{to_names}])" if to_names else ""

    filter_parts = []
    from_filter = []
    if from_class:
        from_filter.append(
            f'classDefinitionSystemName: {{ value: "{from_class}" }}'
        )
    if from_id:
        from_filter.append(f'ids: ["{from_id}"]')
    if from_filter:
        filter_parts.append(f'relationshipFrom: [{{ {" , ".join(from_filter)} }}]')

    to_filter = []
    if to_class:
        to_filter.append(f'classDefinitionSystemName: {{ value: "{to_class}" }}')
    if to_id:
        to_filter.append(f'ids: ["{to_id}"]')
    if to_filter:
        filter_parts.append(f'relationshipTo: [{{ {" , ".join(to_filter)} }}]')

    filter_clause = (
        f"options: {{ filterBy: {{ {' , '.join(filter_parts)} }} }}" if filter_parts else ""
    )

    query = """
    query informationRelationships {
        informationRelationships(
            %s
        )  {
            data {
                id
                attributes%s {
%s
                }
                relationshipFromId
                relationshipToId
    """ % (filter_clause, rel_attr_clause, ATTRIBUTE_FRAGMENT)

    if include_from:
        query += (
            "\n                relationshipFrom {\n                    id\n     clientSystemName\n          attributes" + from_attr_clause + " {\n" + ATTRIBUTE_FRAGMENT + "                }\n                }"
        )
    if include_to:
        query += (
            "\n                relationshipTo {\n                    id\n    clientSystemName\n         attributes" + to_attr_clause + " {\n" + ATTRIBUTE_FRAGMENT + "                }\n                }"
        )

    query += "\n            }\n        }\n    }\n    "
    return query

# === RESULT TO TABLE ===

def _parse_attributes(attrs: list, prefix: str = "") -> dict:
    """Convert list of attribute objects to flat dict."""
    result: dict = {}
    for attr in attrs or []:
        name = attr.get("attributeDefinitionSystemName")
        if not name:
            continue

        ref_values = attr.get("informationObjectReferenceValues")
        if isinstance(ref_values, list) and ref_values:
            result[f"{prefix}{name}"] = ",".join(
                str(i) for i in attr.get("informationObjectReferenceValueIds", [])
            )
            for ref in ref_values:
                ref_prefix = ref.get("classDefinitionSystemName", "")
                for ref_attr in ref.get("attributes", []):
                    ref_attr_name = ref_attr.get("attributeDefinitionSystemName")
                    if not ref_attr_name:
                        continue
                    value = None
                    for rk, rv in ref_attr.items():
                        if rk == "attributeDefinitionSystemName":
                            continue
                        if rv is None:
                            continue
                        if isinstance(rv, dict) and "value" in rv:
                            value = rv.get("value")
                            break
                        value = rv
                        break
                    col = f"{prefix}{ref_prefix}_{ref_attr_name}" if ref_prefix else f"{prefix}{ref_attr_name}"
                    result[col] = value
        else:
            value = None
            for k, v in attr.items():
                if k == "attributeDefinitionSystemName":
                    continue
                if v is None:
                    continue
                if isinstance(v, dict) and "value" in v:
                    value = v.get("value")
                    break
                value = v
                break
            result[f"{prefix}{name}"] = value
    return result


def extract_table(data):
    """Create a pandas DataFrame from the GraphQL response."""
    try:
        raw_items = data.get("data", {}).get("informationObjects", {}).get("data", [])
        rows = []

        for item in raw_items:
            row = {}
            for key, value in item.items():
                if key == "attributes" and isinstance(value, list):
                    row.update(_parse_attributes(value))
                else:
                    row[key] = value
            rows.append(row)

        return pd.DataFrame(rows)
    except Exception as e:
        st.error(f"Fehler beim Parsen der Antwort: {e}")
        return pd.DataFrame()

def extract_relationship_table(data):
    """Create a pandas DataFrame from relationship query response."""
    try:
        raw_items = (
            data.get("data", {})
            .get("informationRelationships", {})
            .get("data", [])
        )
        rows = []
        for item in raw_items:
            row = {
                "id": item.get("id"),
                "relationshipFromId": item.get("relationshipFromId"),
                "relationshipToId": item.get("relationshipToId"),
            }

            row.update(_parse_attributes(item.get("attributes", [])))

            rel_from = item.get("relationshipFrom") or {}
            row["relationshipFrom_id"] = rel_from.get("id")
            row.update(
                _parse_attributes(rel_from.get("attributes", []), prefix="relationshipFrom_")
            )

            rel_from = item.get("relationshipFrom") or {}
            row["relationshipFrom_client"] = rel_from.get("clientSystemName")
            row.update(
                _parse_attributes(rel_from.get("attributes", []), prefix="relationshipFrom_")
            )

            rel_to = item.get("relationshipTo") or {}
            row["relationshipTo_id"] = rel_to.get("id")
            row.update(
                _parse_attributes(rel_to.get("attributes", []), prefix="relationshipTo_")
            )
            rel_from = item.get("relationshipTo") or {}
            row["relationshipTo_client"] = rel_from.get("clientSystemName")
            row.update(
                _parse_attributes(rel_from.get("attributes", []), prefix="relationshipTo_")
            )

            rows.append(row)

        return pd.DataFrame(rows)
    except Exception as e:
        st.error(f"Fehler beim Parsen der Antwort: {e}")
        return pd.DataFrame()

# === STREAMLIT UI ===
st.title("GraphQL Explorer")

tabs = st.tabs(["Information Objects", "Relationships"])

with tabs[0]:
    with st.form("object_form"):
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

with tabs[1]:
    with st.form("relationship_form"):
        base_url_r = st.text_input("Base URL", value=DEFAULT_BASE_URL)
        username_r = st.text_input("Benutzername")
        password_r = st.text_input("Passwort", type="password")
        from_class = st.text_input("From classDefinitionSystemName")
        from_id = st.text_input("From ID")
        to_class = st.text_input("To classDefinitionSystemName")
        to_id = st.text_input("To ID")
        rel_attr_input = st.text_input("Relationship Attribute Systemnamen (kommagetrennt)")
        from_attr_input = st.text_input("From Object Attribute Systemnamen (kommagetrennt)")
        to_attr_input = st.text_input("To Object Attribute Systemnamen (kommagetrennt)")
        include_from = st.checkbox("Include from object", value=True)
        include_to = st.checkbox("Include to object", value=True)
        submitted_rel = st.form_submit_button("Absenden")

    if submitted_rel:
        try:
            base_url_r = base_url_r.rstrip("/")
            st.info("Authentifiziere...")
            token = get_bearer_token(base_url_r, username_r, password_r)
            st.success("Token erhalten!")

            rel_names = [n.strip() for n in rel_attr_input.split(",") if n.strip()]
            from_names = [n.strip() for n in from_attr_input.split(",") if n.strip()]
            to_names = [n.strip() for n in to_attr_input.split(",") if n.strip()]
            query = build_relationship_query(
                from_class,
                from_id,
                to_class,
                to_id,
                rel_names,
                from_names,
                to_names,
                include_from,
                include_to,
            )
            with st.expander("GraphQL Query"):
                st.code(query, language="graphql")
            st.info("Sende GraphQL-Query...")
            result = query_graphql(base_url_r, token, query)
            st.success("Antwort erhalten!")
            st.json(result)
            df = extract_relationship_table(result)
            st.dataframe(df)

        except Exception as e:
            st.error(f"Fehler: {e}")
