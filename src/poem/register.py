#!/usr/bin/env python3
import os
import requests
import yaml
from dotenv import load_dotenv

def get_payment_source(api_key, service_url):
    """
    Retrieves the payment source details from the /payment-source/ endpoint.
    Returns smart_contract_address and seller_vkey.
    """
    url = f"{service_url.rstrip('/')}/payment-source/?take=10"
    headers = {
        "accept": "application/json",
        "token": api_key
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    
    if data.get("status") != "success":
        raise ValueError("API did not return a success status")
    
    payment_sources = data.get("data", {}).get("paymentSources", [])
    if not payment_sources:
        raise ValueError("No payment sources returned from API")
    
    first_source = payment_sources[0]
    smart_contract_address = first_source.get("smartContractAddress")
    selling_wallets = first_source.get("SellingWallets", [])
    if not smart_contract_address or not selling_wallets:
        raise ValueError("Missing 'smartContractAddress' or 'SellingWallets' in payment source data")
    
    seller_vkey = selling_wallets[0].get("walletVkey")
    if not seller_vkey:
        raise ValueError("Missing 'walletVkey' in first SellingWallet")
    
    return smart_contract_address, seller_vkey

def load_registration_config(config_path="registration.yaml"):
    """
    Loads the registration configuration from a YAML file.
    """
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def register_agent(api_key, service_url, registration_config, smart_contract_address, seller_vkey):
    """
    Registers the agent by POSTing to the registry endpoint. Overwrites the
    network, smartContractAddress, and sellingWalletVkey with auto-fetched values.
    Returns the registration response.
    """
    # Override fields with auto-fetched values.
    registration_config["network"] = "Preprod"
    registration_config["smartContractAddress"] = smart_contract_address
    registration_config["sellingWalletVkey"] = seller_vkey

    url = "https://payment.masumi.network/api/v1/registry/"
    headers = {
        "accept": "application/json",
        "token": api_key,
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, json=registration_config, headers=headers)
    response.raise_for_status()
    return response.json()

def update_env_file(key, value, file_path=".env"):
    """
    Updates or creates the .env file with the specified key and value.
    If the key already exists, its value is replaced. Otherwise, a new line is appended.
    """
    # Read existing env file lines if present.
    env_lines = []
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            env_lines = f.readlines()
    
    key_found = False
    for idx, line in enumerate(env_lines):
        if line.startswith(f"{key}="):
            env_lines[idx] = f"{key}={value}\n"
            key_found = True
            break

    if not key_found:
        env_lines.append(f"{key}={value}\n")
    
    with open(file_path, "w") as f:
        f.writelines(env_lines)
    print(f"Updated {file_path} with {key}={value}")

def main():
    # Load environment variables from .env file
    load_dotenv()
    
    PAYMENT_API_KEY = os.environ.get("PAYMENT_API_KEY")
    PAYMENT_SERVICE_URL = os.environ.get("PAYMENT_SERVICE_URL")
    
    if not PAYMENT_API_KEY or not PAYMENT_SERVICE_URL:
        raise EnvironmentError("Missing one or more required environment variables: PAYMENT_API_KEY, PAYMENT_SERVICE_URL")
    
    # Step 1: Load registration configuration from registration.yaml
    registration_config = load_registration_config()
    print("Loaded registration configuration:")
    print(registration_config)
    
    # Step 2: Get payment source details to override specific fields.
    smart_contract_address, seller_vkey = get_payment_source(PAYMENT_API_KEY, PAYMENT_SERVICE_URL)
    print("Fetched Payment Source Details:")
    print(f"smartContractAddress: {smart_contract_address}")
    print(f"sellerVkey: {seller_vkey}")
    
    # Step 3: Send registration request
    result = register_agent(PAYMENT_API_KEY, PAYMENT_SERVICE_URL, registration_config, smart_contract_address, seller_vkey)
    print("Registration Response:")
    print(result)
    
    # Step 4: Update .env file with the agent identifier from the registration response.
    agent_identifier = result.get("agentIdentifier")
    if agent_identifier:
        update_env_file("AGENT_IDENTIFIER", agent_identifier)
    else:
        print("Registration response did not include an agentIdentifier.")

if __name__ == "__main__":
    main()