### Adobe License Monitor Script
# This script monitors Adobe licenses by retrieving the number of used licenses
# and comparing them to the total licenses allocated. It then sends a summary
# alert to a configured Slack channel via an Incoming Webhook.
#
# The script uses Adobe's User Management API to fetch user data and calculate
# license usage. Total licenses are mapped manually in the script.
#
# Required Environment Variables:
#   ADOBE_ACCESS_TOKEN       - Bearer token for Adobe API access.
#   ADOBE_CLIENT_ID          - Client ID for Adobe API access.
#   ADOBE_ORG_ID             - Organization ID for Adobe API access.
#   SLACK_WEBHOOK_URL  - Webhook URL to send Slack alerts.
#
# Author: Chad Ramey
# Last Updated: January 2, 2025

import json
import requests
from time import sleep
from random import randint
import os

def get_access_token():
    """Retrieve the Adobe access token from environment variables."""
    return os.getenv('ADOBE_ACCESS_TOKEN')

def get_users_in_org():
    """Retrieve all users in the organization with pagination."""
    page_index = 0
    url = f"https://usermanagement.adobe.io/v2/usermanagement/users/{os.getenv('ADOBE_ORG_ID')}/{page_index}"
    method = 'GET'
    done = False
    users_list = []

    while not done:
        r = make_call(method, url)
        if r:
            users_list.extend(r['users'])
            if r['lastPage']:
                done = True
            else:
                page_index += 1
                url = f"https://usermanagement.adobe.io/v2/usermanagement/users/{os.getenv('ADOBE_ORG_ID')}/{page_index}"
        else:
            print("Failed to retrieve user data.")
            break

    return users_list

def make_call(method, url, body=None):
    """Make an API call with retries."""
    retry_wait = 0
    headers = {
        'Accept': 'application/json',
        'x-api-key': os.getenv('ADOBE_CLIENT_ID'),
        'Authorization': f"Bearer {get_access_token()}"
    }
    if body:
        headers['Content-type'] = 'application/json'
        body = json.dumps(body)

    for attempt in range(1, 5):  # Maximum retries: 4
        try:
            print(f'Calling {method} {url}')
            response = requests.request(method, url, data=body, headers=headers, timeout=120)

            if response.status_code == 200:
                return response.json()
            elif response.status_code in [429, 502, 503, 504]:
                print(f'Rate limited or timeout (code {response.status_code}) on attempt {attempt}')
                retry_wait = int(response.headers.get('Retry-After', (2 ** attempt) + randint(0, 5)))
            else:
                print(f"Unexpected HTTP Status: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            print(f"Exception during API call: {e}")
            return None

        if attempt < 4:
            print(f"Retrying in {retry_wait} seconds...")
            sleep(retry_wait)

    print("Maximum retries reached. Exiting.")
    return None

def summarize_licenses(users):
    """Summarize licenses associated with users."""
    license_counts = {}

    # Mapping of cleaned license names to their total counts
    license_mapping = {
        "Acrobat Pro": 316,
        "All Apps plan": 268,
        "Photoshop": 14,
        "Audition": 2,
        "Premiere Pro": 22,
        "Illustrator": 7,
        "Lightroom": 1,
        "Substance": 4
    }

    for user in users:
        for group in user.get('groups', []):
            # Clean up license name
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
        total = license_mapping.get(license_name, "Unknown")
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
    users = get_users_in_org()
    if users:
        summary = summarize_licenses(users)
        print("License Summary:\n" + summary)
        send_slack_alert(f":adobe: *Adobe License Report* :adobe:\n{summary}")
    else:
        print("No user data retrieved.")
