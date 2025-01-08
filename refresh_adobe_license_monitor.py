import json
import requests
import os
from authlib.integrations.requests_client import OAuth2Session

# Adobe API endpoints
TOKEN_URL = "https://ims-na1.adobelogin.com/ims/token/v3"
USER_API_BASE_URL = "https://usermanagement.adobe.io/v2/usermanagement/users"

# Excluded groups
EXCLUDED_GROUPS = [
    "Default Acrobat Pro DC configuration_B90DF18-provisioning",
    "Default All Apps plan - 100 GB configuration_C9431CF-provisioning",
    "Default Photoshop - 100 GB configuration_0A61F1F-provisioning",
    "Default Audition - 1024 GB configuration_4A18C28-provisioning",
    "_product_admin_Custom fonts (VIP,VIPMP - A1406BFDEA1D8CDBEDEA)",
    "_admin_Default Custom fonts configuration",
    "Default Premiere Pro - 1024 GB configuration_E71BE78-provisioning",
    "Default Illustrator - 100 GB configuration_A69B937-provisioning",
    "Default Lightroom Single App plan with 1TB configuration_6FBBDC1-provisioning",
    "Acrobat Users",
    "Default Custom fonts configuration"
]

# License mappings
LICENSE_MAPPING = {
    "Acrobat Pro": 316,
    "All Apps plan": 268,
    "Photoshop": 14,
    "Audition": 2,
    "Premiere Pro": 22,
    "Illustrator": 7,
    "Lightroom": 1,
    "Substance": 4
}

def get_access_token():
    """Retrieve or generate a new Adobe access token using client credentials."""
    print("Access token expired or missing. Generating a new one...")

    client_id = os.getenv('ADOBE_CLIENT_ID')
    client_secret = os.getenv('ADOBE_CLIENT_SECRET')

    session = OAuth2Session(client_id, client_secret)
    token = session.fetch_token(
        TOKEN_URL,
        grant_type='client_credentials',
        scope='openid,AdobeID,user_management_sdk'
    )

    new_access_token = token.get('access_token')
    print("Access token generated successfully.")
    return new_access_token

def get_users_in_org(access_token):
    """Retrieve all users in the Adobe organization with pagination."""
    page_index = 0
    url = f"{USER_API_BASE_URL}/{os.getenv('ADOBE_ORG_ID')}/{page_index}"
    users_list = []

    headers = {
        'Accept': 'application/json',
        'x-api-key': os.getenv('ADOBE_CLIENT_ID'),
        'Authorization': f"Bearer {access_token}"
    }

    while True:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            users_list.extend(data['users'])
            if data['lastPage']:
                break
            page_index += 1
            url = f"{USER_API_BASE_URL}/{os.getenv('ADOBE_ORG_ID')}/{page_index}"
        else:
            print(f"Failed to retrieve user data: {response.status_code} - {response.text}")
            break

    return users_list

def summarize_licenses(users):
    """Summarize licenses associated with users."""
    license_counts = {}

    for user in users:
        for group in user.get('groups', []):
            if group in EXCLUDED_GROUPS:
                continue  # Skip excluded groups

            cleaned_group = (
                group.replace("Default ", "")
                .replace("configuration", "")
                .replace(" plan with 1TB", "")
                .replace(" - 100 GB", "")
                .replace(" - 1024 GB", "")
                .replace("Single App", "")
                .replace(" DC", "")
                .replace(" 3D Collection Configuration", "")
                .strip()
            )
            license_counts[cleaned_group] = license_counts.get(cleaned_group, 0) + 1

    summary = []
    for license_name, used in license_counts.items():
        total = LICENSE_MAPPING.get(license_name, "Unknown")
        unit = "License" if license_name != "Adobe Stock Credits" else "Credits"
        unit += "s" if used > 1 else ""
        summary.append(f"{license_name}: {used} of {total} {unit}")

    return "\n".join(summary)

def send_slack_alert(message):
    """Send the license summary to Slack."""
    webhook_url = os.getenv('SLACK_WEBHOOK_URL')
    payload = {"text": message}
    response = requests.post(webhook_url, json=payload)
    if response.status_code == 200:
        print("Slack alert sent!")
    else:
        print(f"Failed to send Slack alert: {response.status_code} - {response.text}")

if __name__ == '__main__':
    # Generate a new token
    token = get_access_token()

    if token:
        # Fetch users
        users = get_users_in_org(token)

        if users:
            # Summarize licenses
            summary = summarize_licenses(users)
            print("License Summary:\n" + summary)

            # Send Slack alert
            send_slack_alert(f":adobe: *Adobe License Report* :adobe:\n{summary}")
        else:
            print("No user data retrieved.")
    else:
        print("Failed to retrieve access token.")
