import json
import os
from google_auth_oauthlib.flow import InstalledAppFlow

# Blogger APIへのアクセスに必要なスコープ
SCOPES = ['https://www.googleapis.com/auth/blogger']

def main():
    client_secrets_file = 'client_secret.json'
    
    if os.path.exists(client_secrets_file):
        print(f"Found {client_secrets_file}. Starting authorization flow...")
        flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
    else:
        print(f"{client_secrets_file} not found.")
        print("Please enter your Client ID and Client Secret manually.")
        client_id = input("Client ID: ").strip()
        client_secret = input("Client Secret: ").strip()
        
        client_config = {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs"
            }
        }
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    
    # ローカルサーバーを起動してブラウザ経由で認証を行います
    # access_type='offline' を指定することで refresh_token が発行されます
    # prompt='consent' で強制的に同意画面を出すことで、リフレッシュトークンを確実に取得します
    credentials = flow.run_local_server(
        port=0,
        authorization_prompt_message='Please visit this URL to authorize this application: {url}',
        success_message='The authorization flow is complete. You may close this window.',
        access_type='offline',
        prompt='consent'
    )
    
    print("\n" + "="*50)
    print("Authorization Successful!")
    print("="*50)
    print(f"BLOGGER_CLIENT_ID    : {credentials.client_id}")
    print(f"BLOGGER_CLIENT_SECRET: {credentials.client_secret}")
    print(f"BLOGGER_REFRESH_TOKEN: {credentials.refresh_token}")
    print("="*50)
    print("Please save BLOGGER_REFRESH_TOKEN to your GitHub Repository Secrets.")

if __name__ == '__main__':
    main()
