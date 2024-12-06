import json
import os
from datetime import datetime
from pft_collector import PFTMemoCollector
from credibility_analyzer import CredibilityAnalyzer

def load_config():
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: config.json not found. Please create it with your API keys.")
        return None

def main():
    # Load configuration
    config = load_config()
    if not config:
        return
    
    # Step 1: Collect memos
    print("\n=== Collecting PFT Memos ===")
    collector = PFTMemoCollector()
    
    # PFT token configuration
    CURRENCY = "PFT"
    ISSUER = "rnQUEEg8yyjrwk9FhyXpKavHyCRJM9BDMW"
    
    # Collect memos
    user_memos = collector.collect_user_memos(
        currency=CURRENCY,
        issuer=ISSUER,
        batch_size=1000000
    )
    
    # Save collected memos
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    memo_file = f"pft_memos_{timestamp}.json"
    collector.save_results(user_memos, memo_file)
    
    # Step 2: Analyze credibility
    print("\n=== Analyzing Credibility ===")
    analyzer = CredibilityAnalyzer(
        config['openrouter_key'],
        config['google_creds_path']
    )
    
    # Analyze each user's memos
    analysis_results = {}
    for user_address, memos in user_memos.items():
        print(f"\nAnalyzing user {user_address}...")
        analysis = analyzer.analyze_user_memos(memos, "PFT")
        if analysis:
            analysis_results[user_address] = analysis
    
    # Save analysis results
    analysis_file = f"credibility_analysis_{timestamp}.json"
    with open(analysis_file, 'w') as f:
        json.dump(analysis_results, f, indent=2)
    
    print(f"\nAnalysis complete!")
    print(f"Memo data saved to: {memo_file}")
    print(f"Analysis results saved to: {analysis_file}")

if __name__ == "__main__":
    main()
