import os
import json
import time
from datetime import datetime, date
from web3 import Web3
from eth_utils import to_checksum_address

# Override dari environment variable (GitHub Actions)
_env_keys = os.environ.get('PRIVATE_KEYS')
_env_rpc = os.environ.get('RPC_URL')

if _env_keys:
    PRIVATE_KEYS = json.loads(_env_keys)
if _env_rpc:
    RPC_URL = _env_rpc

# --- CONFIGURATION ---
CHAIN_ID = 204
RAW_CONTRACT_ADDRESS = "0x01f9Eb284F94b54CF0854ef3B6FeF69C10babe0C"

CONTRACT_ABI = [
    {
        "inputs": [],
        "name": "hiveCheckIn",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

STATE_FILE = "checkin_state.json"

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def process_wallet(w3, contract, private_key, state, today_str):
    account = w3.eth.account.from_key(private_key)
    sender = account.address

    log(f"--- Processing Wallet: {sender} ---")

    if state.get(sender) == today_str:
        log(f"[!] Wallet {sender[:10]}... already checked in today. Skipping.")
        return

    balance = w3.eth.get_balance(sender)
    if balance == 0:
        log(f"[!] Wallet {sender[:10]}... has 0 opBNB balance! Skipping.")
        return

    try:
        tx = contract.functions.hiveCheckIn().build_transaction({
            'from': sender,
            'nonce': w3.eth.get_transaction_count(sender),
            'gas': 250000,
            'gasPrice': w3.eth.gas_price,
            'chainId': CHAIN_ID
        })

        w3.eth.call(tx)

        signed_tx = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
        
        if receipt.status == 1:
            log(f"[+] SUCCESS! hiveCheckIn completed for {sender[:10]}... Tx: {w3.to_hex(tx_hash)}")
            state[sender] = today_str
            save_state(state)
        else:
            log(f"[!] Tx reverted for {sender[:10]}... (24h cooldown active).")
            state[sender] = today_str
            save_state(state)

    except Exception as e:
        err_msg = str(e).lower()
        if "out of gas" in err_msg or "execution reverted" in err_msg:
            log(f"[!] Wallet {sender[:10]}... already checked in today (Cooldown active).")
            state[sender] = today_str
            save_state(state)
        else:
            log(f"[!] Error for {sender[:10]}...: {e}")

def run_daily_checkin():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        log("[-] Unable to connect to opBNB RPC network.")
        return

    contract_address = to_checksum_address(RAW_CONTRACT_ADDRESS)
    contract = w3.eth.contract(address=contract_address, abi=CONTRACT_ABI)

    today_str = str(date.today())
    state = load_state()

    log("=== Starting hiveCheckIn Auto-Run ===")
    for idx, pk in enumerate(PRIVATE_KEYS, start=1):
        process_wallet(w3, contract, pk, state, today_str)
        if idx < len(PRIVATE_KEYS):
            time.sleep(3)

    log("=== Done! All wallets processed ===")

if __name__ == "__main__":
    run_daily_checkin()
