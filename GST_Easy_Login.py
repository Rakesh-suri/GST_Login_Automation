import os
import sys # Import sys for PyInstaller path handling
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re # Import regex for parsing .env keys

# --- Determine the base directory for resources ---
# This ensures paths work whether running as .py or .exe
if getattr(sys, 'frozen', False):
    # If running in a PyInstaller bundle, sys._MEIPASS is the path to the temp folder
    base_dir = sys._MEIPASS
    # For chromedriver, it will be directly in _MEIPASS/chromedriver-win64/chromedriver.exe
    chromedriver_folder_in_bundle = "chromedriver-win64"
    chromedriver_executable = "chromedriver.exe"
    # Construct the path directly within the bundled environment
    chromedriver_path = os.path.join(base_dir, chromedriver_folder_in_bundle, chromedriver_executable)
    # The .env file will also be directly in _MEIPASS
    dotenv_path = os.path.join(base_dir, '.env')

else:
    # If running as a normal Python script, it's the directory of the script itself
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # For chromedriver, it's relative to the script
    chromedriver_folder = "chromedriver-win64"
    chromedriver_executable = "chromedriver.exe"
    chromedriver_path = os.path.join(base_dir, chromedriver_folder, chromedriver_executable)
    # The .env file is relative to the script
    dotenv_path = os.path.join(base_dir, '.env')


url = "https://services.gst.gov.in/services/login"

# --- Define the naming convention for .env variables ---
TRADE_NAME_PREFIX = "Trade_Name_"
USER_ID_PREFIX = "GST_UserID_"
PASSWORD_PREFIX = "GST_PSSWD_"

# --- Ensure .env file exists and load it ---
if not os.path.exists(dotenv_path):
    with open(dotenv_path, 'w') as f:
        pass # Create empty file
    print(f"Created new .env file at {dotenv_path}")

# IMPORTANT: Load dotenv AFTER chromedriver_path and dotenv_path are correctly set
load_dotenv(dotenv_path=dotenv_path)

# --- Helper Functions ---

def update_env_variable(key, new_value, env_path=dotenv_path):
    """
    Updates or adds a key-value pair in a .env file.
    Args:
        key (str): The environment variable key to update.
        new_value (str): The new value for the environment variable.
        env_path (str): The path to the .env file.
    """
    lines = []
    updated = False

    with open(env_path, 'r') as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f"{key}=\"{new_value}\"\n")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        new_lines.append(f"{key}=\"{new_value}\"\n")

    with open(env_path, 'w') as f:
        f.writelines(new_lines)

    print(f"Successfully updated/added '{key}' in '{env_path}'")
    # Immediately update os.environ for current script session
    os.environ[key] = new_value


def get_account_mapping(env_path=dotenv_path):
    """
    Scans the .env file for Trade_Name_X variables and builds a mapping
    from Trade Name (UPPERCASE, NO SPACES) to its numeric index (X).
    Also determines the next available index.
    Returns:
        tuple: (dict_mapping, next_index)
    """
    trade_name_to_index = {}
    highest_index = 0

    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                match = re.match(rf"^{TRADE_NAME_PREFIX}(\d+)=(.*)$", line)
                if match:
                    index = int(match.group(1))
                    # Ensure trade_name read from .env also has spaces removed if they exist
                    trade_name = match.group(2).strip().strip('"').replace(" ", "").upper()
                    trade_name_to_index[trade_name] = str(index) # Store index as string for consistency
                    if index > highest_index:
                        highest_index = index
    return trade_name_to_index, highest_index + 1


# --- Credentials Management Functions ---

def add_new_account():
    print("\n--- Add New Account ---")
    trade_name_mapping, next_available_index = get_account_mapping()

    new_trade_name = input("Enter a NEW unique Trade Name for the account: ").strip()
    if not new_trade_name:
        print("Trade Name cannot be empty. Aborting.")
        return

    # Normalize the new trade name for lookup: remove spaces and uppercase
    normalized_trade_name = new_trade_name.replace(" ", "").upper()

    if normalized_trade_name in trade_name_mapping:
        print(f"Warning: Trade Name '{new_trade_name}' (normalized to '{normalized_trade_name}') already exists with index {trade_name_mapping[normalized_trade_name]}.")
        overwrite = input("Do you want to OVERWRITE its existing credentials? (yes/no): ").strip().lower()
        if overwrite != 'yes':
            print("Aborting add operation.")
            return
        # If overwriting, use the existing index
        index_to_use = trade_name_mapping[normalized_trade_name]
    else:
        # If new, use the next available index
        index_to_use = str(next_available_index)

    username_key = f"{USER_ID_PREFIX}{index_to_use}"
    password_key = f"{PASSWORD_PREFIX}{index_to_use}"
    trade_name_key = f"{TRADE_NAME_PREFIX}{index_to_use}"

    new_username = input(f"Enter the username for '{new_trade_name}': ").strip()
    new_password = input(f"Enter the password for '{new_trade_name}': ").strip()

    if not new_username or not new_password:
        print("Username and password cannot be empty. Aborting.")
        return

    update_env_variable(trade_name_key, new_trade_name) # Store the original case trade name
    update_env_variable(username_key, new_username)
    update_env_variable(password_key, new_password)

    print(f"Account '{new_trade_name}' added/updated successfully with index {index_to_use}.")
    load_dotenv(dotenv_path=dotenv_path, override=True) # Reload to reflect changes


def update_existing_account():
    print("\n--- Update Existing Account ---")
    trade_name_mapping, _ = get_account_mapping()
    available_trade_names = sorted(trade_name_mapping.keys()) # These are already normalized (uppercased, no spaces)

    if not available_trade_names:
        print("No accounts found in .env file to update. Please add a new account first.")
        return

    # Display the original trade names for better user experience
    print("\nExisting accounts (Trade Names):")
    for name_upper_key in available_trade_names:
        # Get the original index for this normalized name
        index = trade_name_mapping[name_upper_key]
        # Fetch the original case trade name from .env using its key
        original_trade_name_for_display = os.getenv(f"{TRADE_NAME_PREFIX}{index}", name_upper_key)
        print(f"- {original_trade_name_for_display}")


    account_to_update_name_input = input("Enter the Trade Name of the account to update: ").strip()
    # Normalize input for lookup
    normalized_account_name = account_to_update_name_input.replace(" ", "").upper()

    if normalized_account_name not in trade_name_mapping:
        print(f"Trade Name '{account_to_update_name_input}' not found. Please choose from the existing accounts.")
        return

    index_to_update = trade_name_mapping[normalized_account_name]
    username_key = f"{USER_ID_PREFIX}{index_to_update}"
    password_key = f"{PASSWORD_PREFIX}{index_to_update}"

    # Fetch original trade name for display after successful lookup
    original_trade_name_found = os.getenv(f"{TRADE_NAME_PREFIX}{index_to_update}", account_to_update_name_input)

    print(f"\nUpdating credentials for '{original_trade_name_found}' (index: {index_to_update})")
    print(f"(Current username: {os.getenv(username_key, 'Not set')})")
    print(f"(Current password: {'***' if os.getenv(password_key) else 'Not set'})")

    new_username = input("Enter NEW username (leave blank to keep current): ").strip()
    new_password = input("Enter NEW password (leave blank to keep current): ").strip()

    updated = False
    if new_username:
        update_env_variable(username_key, new_username)
        updated = True
    if new_password:
        update_env_variable(password_key, new_password)
        updated = True

    if updated:
        print(f"Credentials for '{original_trade_name_found}' updated successfully.")
        load_dotenv(dotenv_path=dotenv_path, override=True) # Reload
    else:
        print("No changes made.")


def list_all_accounts():
    print("\n--- List All Accounts ---")
    trade_name_mapping, _ = get_account_mapping()
    available_trade_names_sorted_by_index = sorted(
        trade_name_mapping.items(), key=lambda item: int(item[1])
    ) # Sort by the numeric index

    if not available_trade_names_sorted_by_index:
        print("No accounts found following the defined naming convention (Trade_Name_X, GST_UserID_X, GST_PSSWD_X).")
    else:
        # Loop through the sorted items (trade_name_upper, index)
        for name_upper, index in available_trade_names_sorted_by_index:
            # Retrieve the original casing of the trade name from .env using its specific key
            original_trade_name = os.getenv(f"{TRADE_NAME_PREFIX}{index}", name_upper)
            username_val = os.getenv(f"{USER_ID_PREFIX}{index}", "N/A")
            password_val = os.getenv(f"{PASSWORD_PREFIX}{index}", "N/A")

            print(f"Trade Name: {original_trade_name} (Index: {index})")
            print(f"  Username: {username_val}")
            print(f"  Password: {'***' if password_val else 'Not Set'}")
            print("-" * 20)
    load_dotenv(dotenv_path=dotenv_path, override=True) # Reload


def manage_credentials_menu():
    while True:
        print("\n--- Credential Management Menu ---")
        print("1. Add a NEW account")
        print("2. Update an EXISTING account")
        print("3. List all accounts")
        print("4. Go back to Main Menu")

        choice = input("Enter your choice (1-4): ").strip()

        if choice == '1':
            add_new_account()
        elif choice == '2':
            update_existing_account()
        elif choice == '3':
            list_all_accounts()
        elif choice == '4':
            break
        else:
            print("Invalid choice. Please enter a number between 1 and 4.")


# --- GST Login Automation Logic ---
def perform_gst_login():
    print("\n--- Perform GST Login Automation ---")

    # Check if chromedriver exists
    if not os.path.exists(chromedriver_path):
        print(f"Error: Chromedriver not found at {chromedriver_path}.")
        print("Please ensure the 'chromedriver-win64' folder containing 'chromedriver.exe' is in the same directory as this script/executable.")
        input("Press Enter to return to main menu...")
        return # Go back to main menu

    trade_name_mapping, _ = get_account_mapping()
    # When displaying, we use the raw keys from trade_name_mapping for listing.
    # The actual names for display come from the .env directly.
    available_trade_names_for_display = []
    # Sort by original index for a consistent list order for the user
    for name_upper_key, index in sorted(trade_name_mapping.items(), key=lambda item: int(item[1])):
        original_name = os.getenv(f"{TRADE_NAME_PREFIX}{index}", name_upper_key)
        available_trade_names_for_display.append(original_name)


    if not available_trade_names_for_display:
        print("No accounts found in .env file. Please add an account using 'Manage Credentials' first.")
        input("Press Enter to return to main menu...")
        return # Go back to main menu

    print("\nAvailable accounts (Trade Names):")
    for name in available_trade_names_for_display:
        print(f"- {name}")

    driver = None # Initialize driver to None

    while True:
        account_name_input = input("\nEnter the Trade Name of the account to log in with,\n or type 'list' to see options,\n or 'back' to return to main menu: ").strip()

        if account_name_input.lower() == 'back':
            print("Returning to main menu.")
            break # Exit this loop and go back to main menu
        elif account_name_input.lower() == 'list':
            print("\nAvailable accounts (Trade Names):")
            if not available_trade_names_for_display:
                print("No accounts found.")
            for name in available_trade_names_for_display:
                print(f"- {name}")
            continue

        # --- THE KEY FIX HERE ---
        # Normalize the input name by removing all spaces and converting to uppercase
        normalized_account_name = account_name_input.replace(" ", "").upper()

        if normalized_account_name not in trade_name_mapping:
            print(f"Trade Name '{account_name_input}' (normalized to '{normalized_account_name}') not found. Please choose from the available accounts or ensure it's entered without internal spaces.")
            continue # Ask for input again

        index = trade_name_mapping[normalized_account_name]
        username = os.getenv(f"{USER_ID_PREFIX}{index}")
        password = os.getenv(f"{PASSWORD_PREFIX}{index}")

        # Fetch original trade name for display after successful lookup
        original_trade_name_found = os.getenv(f"{TRADE_NAME_PREFIX}{index}", account_name_input)


        if username and password:
            print(f"Attempting to log in with account: {original_trade_name_found}")
            service = Service(chromedriver_path)
            driver = webdriver.Chrome(service=service)
            driver.get(url)

            try:
                username_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "username"))
                )
                username_input.send_keys(username)

                password_input = driver.find_element(By.ID, "user_pass")
                password_input.send_keys(password)

                captcha_input = WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.ID, "captcha"))
                )

                captcha_solution = input(f"Enter CAPTCHA from browser for '{original_trade_name_found}': ").strip()
                captcha_input.send_keys(captcha_solution)

                # --- IMPORTANT: Click the Login Button ---
                # You MUST inspect the GST login page to find the correct ID or other locator
                # for the actual login button. Replace "login_button_id" below.
                login_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "login_button_id")) # <--- REPLACE "login_button_id"
                )
                login_button.click()

                time.sleep(5) # Give some time for the page to load/redirect

                if "dashboard" in driver.current_url or "home" in driver.current_url or "loggedin" in driver.current_url:
                    print(f"Successfully logged in with account: {original_trade_name_found}")
                    input("Press Enter to keep the browser open (or close it manually)...")
                    break # Exit login loop after successful login
                else:
                    print(f"Login failed for account: {original_trade_name_found}.")
                    try:
                        error_message_element = driver.find_element(By.CLASS_NAME, "error-message-class") # Adjust this locator
                        print(f"Error message: {error_message_element.text}")
                    except:
                        pass
                    print("Please check the credentials, CAPTCHA, or the GST portal's status and try again.")

            except Exception as e:
                print(f"An error occurred during login for account {original_trade_name_found}: {e}")

            finally:
                if driver:
                    driver.quit()
                    driver = None

        else:
            print(f"Credentials (username or password) for account '{original_trade_name_found}' (index {index}) not found in .env file. "
                  f"Expected variables: {USER_ID_PREFIX}{index} and {PASSWORD_PREFIX}{index}")
            print("Please ensure your .env file is correctly configured for this account, or add/update it via 'Manage Credentials'.")

# --- Main Application Menu ---
if __name__ == "__main__":
    print("--- Welcome to GST Automation Tool ---")

    while True:
        print("\nMain Menu:")
        print("1. Manage Credentials (Add/Update/List)")
        print("2. Perform GST Login")
        print("3. Exit")

        main_choice = input("Enter your choice (1-3): ").strip()

        if main_choice == '1':
            manage_credentials_menu()
        elif main_choice == '2':
            perform_gst_login()
        elif main_choice == '3':
            print("Exiting GST Automation Tool. Goodbye!")
            break
        else:
            print("Invalid choice. Please enter a number between 1 and 3.")
            

