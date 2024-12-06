from xrpl.clients import JsonRpcClient
from xrpl.models import AccountTx, LedgerCurrent
import json
import binascii
from datetime import datetime
import time
from collections import defaultdict
import os

class PFTMemoCollector:
    def __init__(self, node_url="https://xrplcluster.com", start_ledger=83999999):
        self.client = JsonRpcClient(node_url)
        self.start_ledger = start_ledger
        
    def decode_memo(self, memo_hex):
        """Decode hex-encoded memo data to UTF-8 string"""
        try:
            memo_hex = memo_hex.replace('0x', '')
            return binascii.unhexlify(memo_hex).decode('utf-8')
        except Exception as e:
            print(f"Failed to decode memo: {e}")
            return None

    def collect_user_memos(self, currency, issuer, start_ledger=None, end_ledger=None, batch_size=1000000):
        """Collect all memos grouped by user"""
        user_memos = defaultdict(list)
        marker = None
        processed_txs = 0
        
        # Use instance start_ledger if none provided
        if start_ledger is None:
            start_ledger = self.start_ledger
            
        # Get current ledger if end_ledger not provided
        if end_ledger is None:
            end_ledger = self.client.request(LedgerCurrent()).result["ledger_current_index"]
        
        current_start = start_ledger  # Use the provided or instance start_ledger
        
        print(f"Starting collection from ledger {current_start} to {end_ledger}")
        
        while current_start < end_ledger:
            try:
                # Calculate batch end ledger
                batch_end = min(current_start + batch_size, end_ledger)
                
                print(f"\nProcessing ledger range: {current_start} to {batch_end}")
                
                # Prepare request - include marker in initial creation if it exists
                request_params = {
                    "account": issuer,
                    "ledger_index_min": current_start,
                    "ledger_index_max": batch_end,
                    "forward": True,
                    "limit": 400
                }
                if marker:
                    request_params["marker"] = marker
                    
                request = AccountTx(**request_params)
                
                # Make request
                response = self.client.request(request)
                result = response.result
                
                # Debug logging
                print(f"API Response keys: {result.keys()}")
                
                # Check if response contains transactions
                if 'transactions' not in result:
                    print(f"Warning: No transactions found in response. Response: {result}")
                    # Move to next batch
                    current_start = batch_end
                    marker = None
                    if current_start >= end_ledger and end_ledger != -1:
                        break
                    continue

                # Update marker for pagination
                marker = result.get('marker')
                
                # Process transactions
                for tx_info in result['transactions']:
                    tx = tx_info['tx']
                    processed_txs += 1
                    
                    # Skip if not a Payment
                    if tx['TransactionType'] != 'Payment':
                        continue
                        
                    # Check if it's a PFT payment
                    if isinstance(tx.get('Amount'), dict):
                        if tx['Amount'].get('currency') != currency:
                            continue
                    else:  # XRP payment
                        continue
                    
                    # Process memos if present
                    if 'Memos' in tx:
                        for memo_obj in tx['Memos']:
                            memo = memo_obj.get('Memo', {})
                            memo_data = self.decode_memo(memo.get('MemoData', ''))
                            
                            if memo_data:
                                memo_info = {
                                    'tx_hash': tx.get('hash'),
                                    'ledger_index': tx.get('ledger_index'),
                                    'timestamp': datetime.fromtimestamp(
                                        tx.get('date', 0) + 946684800
                                    ).isoformat(),
                                    'memo_data': memo_data,
                                    'sender': tx.get('Account'),
                                    'destination': tx.get('Destination'),
                                    'amount': tx.get('Amount')
                                }
                                user_memos[tx.get('Account')].append(memo_info)
                
                print(f"Processed {processed_txs} transactions")
                print(f"Users found with memos: {len(user_memos)}")
                
                # If no more transactions in this batch, move to next batch
                if not marker:
                    current_start = batch_end
                    if current_start >= end_ledger and end_ledger != -1:
                        break
                    marker = None
                
                # Rate limiting
                time.sleep(0.1)
                
            except Exception as e:
                print(f"Error processing transactions: {e}")
                # Save results on error
                self.save_results(user_memos, f"pft_user_memos_error_{current_start}.json")
                raise
        
        return user_memos

    def save_results(self, user_memos, filename):
        """Save results to a JSON file"""
        with open(filename, 'w') as f:
            json.dump(user_memos, f, indent=2)

    def get_earliest_ledger(self):
        """Get the earliest available ledger index"""
        try:
            response = self.client.request(AccountTx(
                account=self.issuer,
                ledger_index_min=-1,
                ledger_index_max=-1,
                limit=1,
                forward=True
            ))
            if 'transactions' in response.result and response.result['transactions']:
                return response.result['transactions'][0]['tx']['ledger_index']
        except Exception as e:
            print(f"Error getting earliest ledger: {e}")
        return 1

    def validate_ledger_range(self, start_ledger, end_ledger):
        """Validate and adjust ledger range if needed"""
        current_ledger = self.client.request(LedgerCurrent()).result["ledger_current_index"]
        earliest_ledger = self.get_earliest_ledger()
        
        start_ledger = max(earliest_ledger, start_ledger)
        end_ledger = min(current_ledger, end_ledger)
        
        return start_ledger, end_ledger

def main():
    # Initialize collector
    collector = PFTMemoCollector()
    
    # PFT token configuration
    CURRENCY = "PFT"
    ISSUER = "rnQUEEg8yyjrwk9FhyXpKavHyCRJM9BDMW"
    
    # Start from when PFT was created (around ledger 83999999)
    PFT_CREATION_LEDGER = 83999999
    current_ledger = collector.client.request(LedgerCurrent()).result["ledger_current_index"]
    
    print(f"Starting to collect memos for {CURRENCY} token...")
    print(f"Collecting from ledger {PFT_CREATION_LEDGER} to {current_ledger}")
    
    # Collect memos
    user_memos = collector.collect_user_memos(
        currency=CURRENCY,
        issuer=ISSUER,
        start_ledger=PFT_CREATION_LEDGER,
        end_ledger=current_ledger
    )
    
    # Save results
    collector.save_results(user_memos, "pft_user_memos.json")

if __name__ == "__main__":
    main()