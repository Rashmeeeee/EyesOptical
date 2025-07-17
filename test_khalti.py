#!/usr/bin/env python3
"""
Khalti Payment Integration Test Script
This script helps you test and debug Khalti payment integration
"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_khalti_credentials():
    """Test if Khalti credentials are working"""
    
    # Get credentials from environment or use defaults
    public_key = os.environ.get('KHALTI_PUBLIC_KEY', "test_public_key_dc74e0fd57cb46cd93832aee0a390234")
    secret_key = os.environ.get('KHALTI_SECRET_KEY', "test_secret_key_...")
    
    print("=== Khalti Credentials Test ===")
    print(f"Public Key: {public_key}")
    print(f"Secret Key: {secret_key[:10]}..." if len(secret_key) > 10 else f"Secret Key: {secret_key}")
    print()
    
    # Test payload
    payload = {
        "return_url": "http://localhost:5000/payment/success",
        "website_url": "http://localhost:5000",
        "amount": 1000,  # 10 NPR in paisa
        "purchase_order_id": "test_order_123",
        "purchase_order_name": "Test Product",
        "customer_info": {
            "name": "Test User",
            "email": "test@example.com",
            "phone": "9800000000"
        }
    }
    
    headers = {
        "Authorization": f"Key {secret_key}",
        "Content-Type": "application/json"
    }
    
    print("Testing Khalti API call...")
    print(f"URL: https://a.khalti.com/api/v2/epayment/initiate/")
    print(f"Headers: {headers}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print()
    
    try:
        response = requests.post(
            "https://a.khalti.com/api/v2/epayment/initiate/",
            json=payload,
            headers=headers,
            timeout=10
        )
        
        print(f"Response Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Body: {response.text}")
        
        if response.status_code == 200:
            print("\n✅ SUCCESS: Khalti API call successful!")
            data = response.json()
            if 'payment_url' in data:
                print(f"Payment URL: {data['payment_url']}")
        else:
            print(f"\n❌ ERROR: Khalti API call failed with status {response.status_code}")
            try:
                error_data = response.json()
                print(f"Error details: {error_data}")
            except:
                print(f"Error response: {response.text}")
                
    except requests.exceptions.RequestException as e:
        print(f"\n❌ NETWORK ERROR: {e}")
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")

def check_environment():
    """Check if environment variables are set"""
    print("=== Environment Check ===")
    
    env_vars = ['KHALTI_PUBLIC_KEY', 'KHALTI_SECRET_KEY']
    
    for var in env_vars:
        value = os.environ.get(var)
        if value:
            print(f"✅ {var}: Set")
        else:
            print(f"❌ {var}: Not set")
    
    print()
    print("To set environment variables, create a .env file with:")
    print("KHALTI_PUBLIC_KEY=your_public_key_here")
    print("KHALTI_SECRET_KEY=your_secret_key_here")

def main():
    print("Khalti Payment Integration Test")
    print("=" * 40)
    print()
    
    check_environment()
    print()
    test_khalti_credentials()
    
    print("\n" + "=" * 40)
    print("Next Steps:")
    print("1. Get real Khalti API credentials from https://khalti.com/merchant/account/apikey/")
    print("2. Create a .env file with your credentials")
    print("3. Run this script again to test")
    print("4. Restart your Flask application")

if __name__ == "__main__":
    main() 