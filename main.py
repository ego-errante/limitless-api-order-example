#!/usr/bin/env python3
"""
Limitless Exchange Trading Script
WARNING: This is a demo script. Use at your own risk.
Limitless Labs is not responsible for any losses or mistakes.
"""

import requests
import json
import time
import os
from eth_account import Account
from eth_account.messages import encode_defunct
from dotenv import load_dotenv

load_dotenv()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")


def sign_message(self, message: str) -> str:
    """Sign a message using the private key."""
    if not self.account:
        raise Exception("Private key not provided. Cannot sign message.")

    print(f"🖊️  Signing message for account: {self.account.address}")

    message_hash = encode_defunct(text=message)
    signed_message = self.account.sign_message(message_hash)
    signature_hex = signed_message.signature.hex()

    print(
        f"   Generated signature: {signature_hex[:10]}... (length: {len(signature_hex)})"
    )

    return signature_hex


#### ============================================================================
#### DISCLAIMER AND WARNING
#### ============================================================================
print("⚠️  WARNING: This is an example trading script for educational purposes.")
print("⚠️  Limitless Labs is not responsible for any losses or mistakes.")
print("⚠️  Always test with small amounts first and understand the code.")
print("⚠️  USE AT YOUR OWN RISK.\n")

#### ============================================================================
#### Import Compatibility Layer
#### ============================================================================

try:
    from eth_account.messages import encode_typed_data

    print("✅ Successfully imported encode_typed_data from eth_account.messages")
except ImportError:
    try:
        from eth_account.messages import encode_structured_data as encode_typed_data

        print("✅ Using encode_structured_data (fallback)")
    except ImportError as e:
        print(f"❌ Import error: {e}")

#### ============================================================================
#### Configuration
#### ============================================================================

#### Contract addresses - Update these with current addresses from environment
CLOB_ADDRESS = os.getenv("CLOB_CFT_ADDR", "0xa4409D988CA2218d956BeEFD3874100F444f0DC3")
NEGRISK_ADDRESS = os.getenv(
    "NEGRISK_CFT_ADDR", "0x5a38afc17F7E97ad8d6C547ddb837E40B4aEDfC6"
)
API_BASE_URL = os.getenv("API_URL", "https://api.limitless.exchange")

#### EIP-712 Type Definitions
ORDER_TYPES = {
    "Order": [
        {"name": "salt", "type": "uint256"},
        {"name": "maker", "type": "address"},
        {"name": "signer", "type": "address"},
        {"name": "taker", "type": "address"},
        {"name": "tokenId", "type": "uint256"},
        {"name": "makerAmount", "type": "uint256"},
        {"name": "takerAmount", "type": "uint256"},
        {"name": "expiration", "type": "uint256"},
        {"name": "nonce", "type": "uint256"},
        {"name": "feeRateBps", "type": "uint256"},
        {"name": "side", "type": "uint8"},
        {"name": "signatureType", "type": "uint8"},
    ]
}

#### ============================================================================
#### Utility Functions
#### ============================================================================


def string_to_hex(text):
    """Convert string to hex representation with 0x prefix."""
    return "0x" + text.encode("utf-8").hex()


#### ============================================================================
#### Authentication Functions
#### ============================================================================


def get_signing_message():
    """
    Fetch the signing message from the API.

    Returns:
        str: The signing message to be signed
    """
    response = requests.get(f"{API_BASE_URL}/auth/signing-message")
    if response.status_code == 200:
        return response.text
    else:
        raise Exception(f"Failed to get signing message: {response.status_code}")


def authenticate(private_key, signing_message):
    """
    Authenticate with the Limitless Exchange API.

    Args:
        private_key: Your wallet's private key
        signing_message: The message to sign for authentication

    Returns:
        tuple: (session_cookie, user_data)
    """
    hex_message = "0x" + signing_message.encode("utf-8").hex()

    # Get the Ethereum address from the private key
    if not private_key.startswith("0x"):
        private_key = "0x" + private_key
    account = Account.from_key(private_key)
    ethereum_address = account.address

    print(f"Using address: {ethereum_address}")
    print(f"Signing message: {repr(signing_message)}")

    # Sign the message
    message = encode_defunct(text=signing_message)
    signature = account.sign_message(message)
    sig_hex = signature.signature.hex()
    if not sig_hex.startswith("0x"):
        sig_hex = "0x" + sig_hex

    headers = {
        "x-account": ethereum_address,
        "x-signing-message": hex_message,
        "x-signature": sig_hex,
        "Content-Type": "application/json",
    }

    response = requests.post(
        f"{API_BASE_URL}/auth/login", headers=headers, json={"client": "eoa"}
    )

    if response.status_code == 200:
        session_cookie = response.cookies.get("limitless_session")
        return session_cookie, response.json()
    else:
        raise Exception(
            f"Authentication failed: {response.status_code} - {response.text}"
        )


#### ============================================================================
#### Order Creation Functions
#### ============================================================================


def create_order_payload_without_signature(
    maker_address, token_id, maker_amount, taker_amount, fee_rate_bps
):
    """
    Create the base order payload without signature.

    Args:
        maker_address: The maker's wallet address
        token_id: The token ID to trade (YES or NO token)
        maker_amount: Amount the maker is offering (scaled)
        taker_amount: Amount the maker wants in return (scaled)
        fee_rate_bps: Fee rate in basis points

    Returns:
        dict: Order payload ready for signing
    """
    salt = int(time.time() * 1000) + (24 * 60 * 60 * 1000)  # Current time + 24h in ms

    return {
        "salt": salt,
        "maker": maker_address,
        "signer": maker_address,
        "taker": "0x0000000000000000000000000000000000000000",  # Open to any taker
        "tokenId": str(token_id),  # Keep as string for API
        "makerAmount": maker_amount,
        "takerAmount": taker_amount,
        "expiration": "0",  # No expiration
        "nonce": 0,
        "feeRateBps": fee_rate_bps,
        "side": 0,  # 0 = BUY
        "signatureType": 0,  # 0 = EOA signature
    }


def get_eip712_domain(market_type="CLOB"):
    """
    Get the EIP-712 domain for signing.

    Args:
        market_type: 'CLOB' or 'NEGRISK'

    Returns:
        dict: EIP-712 domain object
    """
    contract_address = CLOB_ADDRESS if market_type == "CLOB" else NEGRISK_ADDRESS
    return {
        "name": "Limitless CTF Exchange",
        "version": "1",
        "chainId": 8453,  # Base chain ID
        "verifyingContract": contract_address,
    }


def create_signature_for_order_payload(market_type, order_payload, private_key):
    """
    Sign an order payload using EIP-712.

    Args:
        market_type: 'CLOB' or 'NEGRISK'
        order_payload: The order data to sign
        private_key: Private key for signing

    Returns:
        str: Hex-encoded signature
    """
    # Remove '0x' prefix if present
    if private_key.startswith("0x"):
        private_key = private_key[2:]

    # Create account
    account = Account.from_key("0x" + private_key)

    # Get domain data
    domain_data = get_eip712_domain(market_type)

    # Convert string fields to int for signing
    message_data = {
        "salt": order_payload["salt"],
        "maker": order_payload["maker"],
        "signer": order_payload["signer"],
        "taker": order_payload["taker"],
        "tokenId": int(order_payload["tokenId"]),
        "makerAmount": order_payload["makerAmount"],
        "takerAmount": order_payload["takerAmount"],
        "expiration": int(order_payload["expiration"])
        if order_payload["expiration"]
        else 0,
        "nonce": order_payload["nonce"],
        "feeRateBps": order_payload["feeRateBps"],
        "side": order_payload["side"],
        "signatureType": order_payload["signatureType"],
    }

    print(f"Domain: {json.dumps(domain_data, indent=2)}")
    print(f"Types: {json.dumps(ORDER_TYPES, indent=2)}")
    print(f"Message: {json.dumps(message_data, indent=2)}")

    # Sign using eth_account's implementation of EIP-712
    encoded_message = encode_typed_data(domain_data, ORDER_TYPES, message_data)
    signed_message = account.sign_message(encoded_message)

    # Extract signature
    signature = signed_message.signature.hex()

    # Ensure single 0x prefix regardless of how .hex() behaves
    if not signature.startswith("0x"):
        signature = "0x" + signature

    print(f"Successfully generated EIP-712 Signature: {signature}")
    return signature


def create_order_api(order_payload, session_cookie):
    """
    Submit an order to the API.

    Args:
        order_payload: Complete order payload with signature
        session_cookie: Authentication session cookie

    Returns:
        dict: API response with order details
    """
    api_url = f"{API_BASE_URL}/orders"

    headers = {
        "cookie": f"limitless_session={session_cookie}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    print(f"Order payload: {json.dumps(order_payload, indent=2)}")

    try:
        response = requests.post(
            api_url, headers=headers, json=order_payload, timeout=35
        )

        if response.status_code != 201:
            print(f"Failed to create order. Status: {response.status_code}")
            print(f"Response: {response.text}")
            raise Exception(f"API Error {response.status_code}: {response.text}")

        result = response.json()
        print(f"Order created successfully: {json.dumps(result, indent=2)}")
        return result

    except Exception as error:
        print(f"Error creating order: {error}")
        raise error


#### ============================================================================
#### Main Trading Function
#### ============================================================================


def execute_trade(trading_params, market_data, private_key):
    """
    Main function to execute a trade on Limitless Exchange.

    Args:
        trading_params: Dictionary containing:
            - sharePrice: price in cents (e.g., 65 for 65¢)
            - amount: amount in shares (e.g., 100)
            - firstType: "YES" or "NO"

        market_data: Dictionary containing:
            - tokens: {"yes": "token_id_yes", "no": "token_id_no"}
            - slug: "market-slug"

        private_key: Your wallet's private key

    Returns:
        dict: Order execution result
    """

    # Step 1: Authenticate
    signing_message = get_signing_message()
    session_cookie, user_data = authenticate(private_key, signing_message)
    print(f"Authenticated as: {user_data['account']}")

    # Step 2: Calculate amounts
    price_in_cents = trading_params["sharePrice"]
    amount = trading_params["amount"]
    trade_type = "GTC"  # Good Till Cancelled
    scaling_factor = 1000000  # 1e6 for USDC (6 decimals)

    # Select token based on YES/NO choice
    first_user_token = (
        market_data["tokens"]["yes"]
        if trading_params["firstType"] == "YES"
        else market_data["tokens"]["no"]
    )

    # Calculate amounts
    price_in_dollars = price_in_cents / 100  # Convert cents to dollars
    total_cost = price_in_dollars * amount  # Total cost in dollars
    maker_amount = round(total_cost * scaling_factor)
    taker_amount = round(amount * scaling_factor)

    print(
        f"Trading: {amount} shares at {price_in_cents} cents ({price_in_dollars} dollars) each"
    )
    print(f"Total cost: {total_cost} dollars")
    print(f"Maker amount: {maker_amount}")
    print(f"Taker amount: {taker_amount}")

    # Step 3: Create order payload without signature
    order_payload_without_signature = create_order_payload_without_signature(
        user_data["account"],
        first_user_token,
        maker_amount,
        taker_amount,
        user_data.get("rank", {}).get("feeRateBps", 0),
    )

    # Step 4: Sign the order
    signature = create_signature_for_order_payload(
        "CLOB", order_payload_without_signature, private_key
    )

    # Step 5: Create final order payload
    final_order_payload = {
        "order": {
            **order_payload_without_signature,
            "price": price_in_dollars,  # Send as decimal
            "signature": signature,
        },
        "ownerId": user_data["id"],
        "orderType": trade_type,
        "marketSlug": market_data["slug"],
    }

    print(
        f"Order placed for ${price_in_cents} cents, amount: {amount}, share type: {trading_params['firstType']}"
    )

    # Step 6: Submit to API
    result = create_order_api(final_order_payload, session_cookie)
    return result


#### ============================================================================
#### Example Usage
#### ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("LIMITLESS EXCHANGE TRADING SCRIPT - DEMO")
    print("=" * 80)
    print("\n⚠️  This is a demonstration script. Please modify for your needs.")
    print("⚠️  Never share your private key with anyone.")
    print("⚠️  Always test with small amounts first.\n")
    print("=" * 80)

    # Example parameters - REPLACE THESE WITH YOUR ACTUAL VALUES
    trading_params = {
        "sharePrice": 50,  # Price in cents (65¢)
        "amount": 2,  # Number of shares
        "firstType": "YES",  # 'YES' or 'NO'
    }

    market_data = {
        "tokens": {
            "yes": "8061359972377607121112731360810354047161833942228070377419827567830682046669",  # Replace with actual YES token ID,
            "no": "113876989897984064661588619997755543057265865813597895942283460033473589862040",  # Replace with actual NO token ID
        },
        "slug": "dollarsui-above-dollar15370-on-dec-12-0400-utc-1765425606505",  # Replace with actual market slug
    }

    # SECURITY WARNING: Never hardcode your private key!
    # Use environment variables or secure key management
    private_key = os.getenv("PRIVATE_KEY", "<FALLBACK_VALUE_FOR_P_KEY>")

    if private_key == "<FALLBACK_VALUE_FOR_P_KEY>":
        print(
            "❌ ERROR: Please set your private key in the environment variable PRIVATE_KEY"
        )
        print("Example: export PRIVATE_KEY='0x...'")
        exit(1)

    print("🚀 Starting trading script...")
    print(f"Trading parameters: {trading_params}")
    print(f"Market: {market_data['slug']}")

    try:
        # Execute the trade
        result = execute_trade(trading_params, market_data, private_key)
        print("\n✅ Trade executed successfully!")
        print(f"Result: {json.dumps(result, indent=2)}")

    except Exception as e:
        print(f"\n❌ Error executing trade: {e}")
        import traceback

        traceback.print_exc()
