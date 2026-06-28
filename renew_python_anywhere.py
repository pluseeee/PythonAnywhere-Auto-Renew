import os
import sys
import requests
from bs4 import BeautifulSoup
import time
from dotenv import load_dotenv

# Load environment variables from .env file (for local testing)
load_dotenv()

LOGIN_URL = "https://www.pythonanywhere.com/login/"

def renew(username, password):
    dashboard_url = f"https://www.pythonanywhere.com/user/{username}/webapps/"

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })

    try:
        # 1. Get login page
        print(f"🔐 Logging in as {username}...")
        login_page = session.get(LOGIN_URL, timeout=10)
        login_page.raise_for_status()

        soup = BeautifulSoup(login_page.content, 'html.parser')
        csrf_token = soup.find('input', {'name': 'csrfmiddlewaretoken'})

        if not csrf_token:
            print("❌ Could not find CSRF token on login page")
            return False

        csrf_token = csrf_token['value']

        # 2. Submit login
        payload = {
            'csrfmiddlewaretoken': csrf_token,
            'auth-username': username,
            'auth-password': password,
            'login_view-current_step': 'auth'
        }

        response = session.post(
            LOGIN_URL,
            data=payload,
            headers={'Referer': LOGIN_URL},
            timeout=10,
            allow_redirects=True
        )
        response.raise_for_status()
        
        # Check multiple indicators of successful login
        if "Log out" not in response.text and "logout" not in response.text.lower():
            print("❌ Login failed - 'Log out' not found in response")
            print(f"Response URL: {response.url}")
            return False
            
        if "login" in response.url.lower():
            print("❌ Login failed - still on login page")
            return False
        
        print("✅ Login successful")
        
        # 3. Access dashboard
        print("📊 Checking dashboard...")
        time.sleep(1)  # Be polite to the server
        
        dashboard = session.get(dashboard_url, timeout=10)
        dashboard.raise_for_status()
        soup = BeautifulSoup(dashboard.content, 'html.parser')
        
        # 4. Find extend button/form
        forms = soup.find_all('form', action=True)
        extend_action = None
        
        for form in forms:
            action = form.get('action', '')
            if "/extend" in action.lower():
                extend_action = action
                print(f"🔍 Found extend action: {action}")
                break
        
        if not extend_action:
            print("ℹ️  No extend button found.")
            print("   This usually means your app doesn't need renewal yet.")
            return True  # Not an error - just nothing to extend
        
        # 5. Get CSRF token from dashboard
        dashboard_csrf = soup.find('input', {'name': 'csrfmiddlewaretoken'})
        if not dashboard_csrf:
            print("❌ Could not find CSRF token on dashboard")
            return False
        
        # 6. Submit extend request
        extend_url = f"https://www.pythonanywhere.com{extend_action}"
        print(f"⏰ Extending web app at {extend_url}...")
        
        result = session.post(
            extend_url,
            data={'csrfmiddlewaretoken': dashboard_csrf['value']},
            headers={'Referer': dashboard_url},
            timeout=10
        )
        result.raise_for_status()
        
        # Verify extension was successful
        if result.status_code == 200:
            # Check if we're back on the dashboard
            if "webapps" in result.url.lower():
                print("✅ Web app extended successfully!")
                return True
            else:
                print(f"⚠️  Unexpected redirect to: {result.url}")
                return False
        else:
            print(f"❌ Extension failed with status: {result.status_code}")
            return False
            
    except requests.Timeout:
        print("❌ Request timed out")
        return False
    except requests.RequestException as e:
        print(f"❌ Network error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def collect_accounts():
    """Read account credentials from env vars.

    Supports both legacy single-account vars (PA_USERNAME/PA_PASSWORD) and
    numbered vars (PA_USERNAME_1/PA_PASSWORD_1, PA_USERNAME_2/...).
    """
    accounts = []

    legacy_user = os.environ.get('PA_USERNAME')
    legacy_pass = os.environ.get('PA_PASSWORD')
    if legacy_user and legacy_pass:
        accounts.append((legacy_user, legacy_pass))

    i = 1
    while True:
        user = os.environ.get(f'PA_USERNAME_{i}')
        pwd = os.environ.get(f'PA_PASSWORD_{i}')
        if not user or not pwd:
            break
        accounts.append((user, pwd))
        i += 1

    return accounts

if __name__ == "__main__":
    accounts = collect_accounts()
    if not accounts:
        print("❌ Error: set PA_USERNAME/PA_PASSWORD or PA_USERNAME_1/PA_PASSWORD_1, ...")
        sys.exit(1)

    print(f"🚀 Renewing {len(accounts)} account(s)")
    results = []
    for idx, (user, pwd) in enumerate(accounts, start=1):
        print(f"\n--- Account {idx}/{len(accounts)} ---")
        results.append(renew(user, pwd))

    failed = sum(1 for ok in results if not ok)
    print(f"\n📋 Summary: {len(results) - failed} succeeded, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
