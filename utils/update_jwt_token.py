import requests
import json

# Bubble API key and headers
BUBBLE_API_KEY = "e1862aa5b08b6383a9f49f4adf206ea6"
HEADERS = {
    "Authorization": "Bearer f8b79ae6e1cb630c4cc7d4edd9d8242f",  # Bubble API key for access
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# Bubble API endpoints
BASE_URL = "https://tradersimpulse.com/api/1.1/obj/trading_accounts"
BUBBLE_API_ENDPOINT = "https://tradersimpulse.com/api/1.1/wf/get-jwt-tokens"


def fetch_trading_accounts():
    """Fetch all trading accounts from the Bubble database."""
    response = requests.get(BASE_URL, headers=HEADERS)
    if response.status_code == 200:
        return response.json().get("response", {}).get("results", [])
    else:
        print("Failed to fetch trading accounts:", response.status_code, response.text)
        return []


def get_jwt_token(email, password, server, env):
    """Function to retrieve a new JWT token using login credentials and environment."""
    # Construct the token URL with the environment value
    token_url = f"https://{env}.tradelocker.com/backend-api/auth/jwt/token"
    payload = {"email": email, "password": password, "server": server}
    response = requests.post(token_url, headers=HEADERS, data=json.dumps(payload))
    if response.status_code in [200, 201, 204]:  # Accept 200, 201, and 204 as success
        response_data = response.json()
        access_token = response_data.get("accessToken")
        refresh_token = response_data.get("refreshToken")
        return access_token, refresh_token
    else:
        print("Failed to fetch JWT token:", response.status_code, response.text)
        return None, None


def update_trading_account(unique_id, access_token, refresh_token):
    """Update a specific trading account in Bubble with new access and refresh tokens."""
    url = f"{BASE_URL}/{unique_id}"
    data = json.dumps({"access_token": access_token, "refresh_token": refresh_token})
    response = requests.patch(url, headers=HEADERS, data=data)
    if response.status_code in [200, 204]:  # Treat 200 and 204 as success
        print(f"Successfully updated trading account {unique_id}")
    else:
        print("Failed to update trading account:", response.status_code, response.text)


def send_data_to_bubble(unique_id, access_token, refresh_token):
    """Send new JWT data back to Bubble's workflow endpoint."""
    payload = {
        "unique_id": unique_id,
        "access_token": access_token,
        "refresh_token": refresh_token,
    }

    # Send a POST request with the payload
    response = requests.post(
        BUBBLE_API_ENDPOINT, headers=HEADERS, data=json.dumps(payload)
    )

    # Check response status
    if response.status_code == 200:
        print(f"Successfully sent data for account {unique_id}")
    else:
        print(
            f"Failed to send data for account {unique_id}: {response.status_code} {response.text}"
        )


def main():
    # Fetch all trading accounts
    accounts = fetch_trading_accounts()

    for account in accounts:
        unique_id = account["_id"]  # Ensure this matches your Bubble field name
        email = account.get("email")  # Adjust if Bubble field name differs
        password = account.get("password")  # Adjust if Bubble field name differs
        server = account.get("server")  # Adjust if Bubble field name differs
        env = account.get("env")  # Adjust if Bubble field name differs

        # Fetch a new JWT token using user credentials and environment
        if email and password and server and env:
            access_token, refresh_token = get_jwt_token(email, password, server, env)
            if access_token and refresh_token:
                # Update the trading account in Bubble
                update_trading_account(unique_id, access_token, refresh_token)

                # Send the new tokens back to Bubble’s workflow endpoint
                send_data_to_bubble(unique_id, access_token, refresh_token)


if __name__ == "__main__":
    main()
