#!/usr/bin/env python3
import os
import requests
from dotenv import load_dotenv

def get_payment_source(api_key, service_url):
    """
    Retrieves the payment source details from the /payment-source/ endpoint.
    Extracts the first payment source's smartContractAddress and sellerVkey.
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

def trigger_ray_job(cluster_url):
    """
    Triggers a job on the Ray cluster by calling /start_job.
    Returns both the payment_id and the job_id from the response.
    """
    job_url = f"{cluster_url.rstrip('/')}/start_job"
    payload = {"num_poems": 1}
    headers = {"Content-Type": "application/json"}
    response = requests.post(job_url, json=payload, headers=headers)
    response.raise_for_status()
    
    job_response = response.json()
    payment_id = job_response.get("payment_id")
    job_id = job_response.get("job_id")
    if not payment_id or not job_id:
        raise ValueError("Response from Ray cluster job did not contain 'payment_id' or 'job_id'")
    return payment_id, job_id

def get_payment_details(payment_id, smart_contract_address, api_key, service_url):
    """
    Retrieves a list of payments from the /payment/ endpoint and finds the payment
    where the blockchainIdentifier equals the given payment_id.
    Returns submitResultTime, unlockTime, and refundTime.
    """
    url = f"{service_url.rstrip('/')}/payment/"
    params = {
        "limit": "10",
        "network": "Preprod",
        "smartContractAddress": smart_contract_address,
        "includeHistory": "false"
    }
    headers = {
        "accept": "application/json",
        "token": api_key
    }
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    data = response.json()
    
    if data.get("status") != "success":
        raise ValueError("Payment API did not return a success status")
    
    payments = data.get("data", {}).get("payments", [])
    if not payments:
        raise ValueError("No payments returned from API")
    
    # Look for the payment entry matching the payment_id
    for payment in payments:
        if payment.get("blockchainIdentifier") == payment_id:
            submit_result_time = payment.get("submitResultTime")
            unlock_time = payment.get("unlockTime")
            refund_time = payment.get("refundTime")
            return submit_result_time, unlock_time, refund_time

    raise ValueError("No payment entry found matching the provided payment_id")

def make_purchase(payment_id, smart_contract_address, seller_vkey,
                  submit_result_time, unlock_time, refund_time,
                  agent_identifier, api_key, service_url):
    """
    Makes a purchase by calling the /purchase/ endpoint with the required data.
    """
    url = f"{service_url.rstrip('/')}/purchase/"
    payload = {
        "identifierFromPurchaser": "identifier1234567",
        "blockchainIdentifier": payment_id,
        "network": "Preprod",
        "sellerVkey": seller_vkey,
        "smartContractAddress": smart_contract_address,
        "amounts": [
            {"amount": "10000000", "unit": "lovelace"}
        ],
        "paymentType": "Web3CardanoV1",
        "submitResultTime": submit_result_time,
        "unlockTime": unlock_time,
        "refundTime": refund_time,
        "agentIdentifier": agent_identifier
    }
    headers = {
        "Content-Type": "application/json",
        "accept": "application/json",
        "token": api_key
    }
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()

def check_job_status(cluster_url, job_id):
    """
    Checks the status of the job on the Ray cluster by calling the /status endpoint
    with the job_id as a query parameter.
    """
    url = f"{cluster_url.rstrip('/')}/status"
    params = {"job_id": job_id}
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def main():
    # Load environment variables from .env file
    load_dotenv()
    
    # Retrieve the required environment variables
    PAYMENT_API_KEY = os.environ.get("PAYMENT_API_KEY")
    AGENT_IDENTIFIER = os.environ.get("AGENT_IDENTIFIER")
    PAYMENT_SERVICE_URL = os.environ.get("PAYMENT_SERVICE_URL")
    RAY_CLUSTER_URL = os.environ.get("RAY_CLUSTER_URL")
    
    if not all([PAYMENT_API_KEY, AGENT_IDENTIFIER, PAYMENT_SERVICE_URL]):
        raise EnvironmentError("Missing one or more required environment variables: PAYMENT_API_KEY, AGENT_IDENTIFIER, PAYMENT_SERVICE_URL")
    
    # Set the Ray cluster URL for job triggering and status checking
    ray_cluster_url = RAY_CLUSTER_URL
    
    # Step 1: Retrieve payment source details
    smart_contract_address, seller_vkey = get_payment_source(PAYMENT_API_KEY, PAYMENT_SERVICE_URL)
    print("Payment Source Data:")
    print(f"smartContractAddress: {smart_contract_address}")
    print(f"sellerVkey: {seller_vkey}")
    
    # Step 2: Trigger a job on the Ray cluster to get a payment_id and job_id
    payment_id, job_id = trigger_ray_job(ray_cluster_url)
    print("Triggered job on Ray cluster:")
    print(f"payment_id: {payment_id}")
    print(f"job_id: {job_id}")
    
    # Step 3: Retrieve payment details matching the payment_id
    submit_result_time, unlock_time, refund_time = get_payment_details(payment_id, smart_contract_address, PAYMENT_API_KEY, PAYMENT_SERVICE_URL)
    print("Payment Details:")
    print(f"submitResultTime: {submit_result_time}")
    print(f"unlockTime: {unlock_time}")
    print(f"refundTime: {refund_time}")
    
    # Step 4: Make the purchase by calling the /purchase/ endpoint
    purchase_response = make_purchase(
        payment_id,
        smart_contract_address,
        seller_vkey,
        submit_result_time,
        unlock_time,
        refund_time,
        AGENT_IDENTIFIER,
        PAYMENT_API_KEY,
        PAYMENT_SERVICE_URL
    )
    print("Purchase Response:")
    print(purchase_response)
    
    # Step 5: Check the status of the job on the Ray cluster using the job_id
    job_status = check_job_status(ray_cluster_url, job_id)
    print("Job Status Response:")
    print(job_status)

if __name__ == "__main__":
    main()