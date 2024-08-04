import yaml
import re
from unidecode import unidecode


def normalize_username(username):
    # Lowercase
    username = username.lower()
    # Remove spaces
    username = username.strip()
    # Replace spaces with underscores
    username = re.sub(r"\s+", "_", username)
    # Replace ? with _
    username = username.replace("?", "_")
    # Normalize Czech orthography
    username = unidecode(username)

    return username


def normalize_yaml(yaml_file):
    """Normalizes usernames in a YAML file."""
    with open(yaml_file, "r") as f:
        data = yaml.safe_load(f)

    # update ["credentials"]["usernames"]
    for username in list(data["credentials"]["usernames"].keys()):
        # user = data["credentials"]["usernames"][username]
        normalized_username = normalize_username(username)

        if normalized_username != username:
            data["credentials"]["usernames"][normalized_username] = data["credentials"][
                "usernames"
            ].pop(username)

    with open(yaml_file, "w") as f:
        yaml.dump(data, f, default_flow_style=False)


# Example usage
yaml_file = "accounts.yaml"
normalize_yaml(yaml_file)
