import json
from datetime import datetime
from typing import List, Dict
import os
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
import re

class CredibilityAnalyzer:
    def __init__(self, api_key: str, google_creds_path: str):
        self.openrouter_key = api_key
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "http://localhost:8000",
            "Content-Type": "application/json"
        }
        
        # Setup Google Docs API
        try:
            self.credentials = service_account.Credentials.from_service_account_file(
                google_creds_path,
                scopes=['https://www.googleapis.com/auth/documents.readonly']
            )
            self.docs_service = build('docs', 'v1', credentials=self.credentials)
            print("Successfully initialized Google Docs API")
        except Exception as e:
            print(f"Error initializing Google Docs API: {e}")
            self.docs_service = None

    def _extract_doc_id(self, url: str) -> str:
        """Extract document ID from Google Doc URL"""
        try:
            return url.split('/d/')[1].split('/')[0]
        except:
            return None

    def _fetch_google_doc_content(self, url: str) -> str:
        """Fetch content from a Google Doc using the API"""
        try:
            if not self.docs_service:
                print("Google Docs API not initialized")
                return ""

            doc_id = self._extract_doc_id(url)
            if not doc_id:
                print(f"Could not extract document ID from URL: {url}")
                return ""
            
            document = self.docs_service.documents().get(documentId=doc_id).execute()
            
            # Extract text content
            content = []
            for element in document.get('body').get('content'):
                if 'paragraph' in element:
                    paragraph = element.get('paragraph')
                    for elem in paragraph.get('elements'):
                        if 'textRun' in elem:
                            content.append(elem.get('textRun').get('content'))

            full_content = ''.join(content)
            
            return full_content
            
        except Exception as e:
            print(f"Error fetching Google Doc content from {url}: {e}")
            return ""

    def _process_memo_data(self, memo_data: str) -> str:
        """Process memo data, including fetching Google Doc content if needed"""
        urls = re.findall(r'https://docs\.google\.com/document/[^\s\n]+', memo_data)
        
        if urls:
            processed_content = memo_data
            for url in urls:
                doc_content = self._fetch_google_doc_content(url)
                if doc_content:
                    processed_content = processed_content.replace(url, f"\n--- Google Doc Content ---\n{doc_content}\n---")
            return processed_content
        return memo_data

    def analyze_user_memos(self, memos: List[Dict], stock_symbol: str) -> Dict:
        """Analyze a user's memos to determine their credibility regarding a specific stock"""
        
        print(f"\nAnalyzing {len(memos)} memos...")
        processed_memos = []
        for memo in memos:
            processed_memo = self._process_memo_data(memo['memo_data'])
            processed_memos.append(processed_memo)
        
        combined_context = "\n---\n".join(processed_memos)
        
        prompt = f"""Based on the following set of memos from a single user, assess their credibility 
        regarding {stock_symbol}. Consider factors like:
        - Quality and depth of analysis
        - Consistency in their views
        - Professional knowledge demonstrated
        - Objectivity and lack of bias
        
        Please provide:
        1. A credibility score from 0-100
        2. A brief explanation of the score

        Recognize that what they are saying is very likely not directly related to the stock.
        
        User's memos:
        {combined_context}"""

        try:
            payload = {
                "model": "anthropic/claude-3.5-haiku-20241022",
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            return {
                'score': self._extract_score(content),
                'explanation': content,
                'memo_count': len(memos),
                'date_range': {
                    'first': min(memo['timestamp'] for memo in memos),
                    'last': max(memo['timestamp'] for memo in memos)
                }
            }
        except Exception as e:
            print(f"Error analyzing memos: {e}")
            return None

    def _extract_score(self, response_text: str) -> int:
        """Extract the numerical score from the LLM response"""
        try:
            numbers = re.findall(r'\b([0-9]{1,3})\b', response_text)
            for num in numbers:
                num = int(num)
                if 0 <= num <= 100:
                    return num
            return 0
        except:
            return 0

def main():
    # Load credentials from config.json
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            openrouter_key = config.get('openrouter_key')
            google_creds_path = config.get('google_creds_path')
            
        if not openrouter_key or not google_creds_path:
            raise ValueError("Missing required credentials in config.json: 'openrouter_key' and 'google_creds_path'")
            
    except FileNotFoundError:
        raise FileNotFoundError("config.json file not found. Please create it with your credentials.")
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON format in config.json")
    
    analyzer = CredibilityAnalyzer(openrouter_key, google_creds_path)

    # Find the most recent pft_user_memos file
    memo_files = [f for f in os.listdir('.') if f.startswith('pft_user_memos_') and f.endswith('.json')]
    if not memo_files:
        print("No PFT memo files found!")
        return
        
    latest_memo_file = max(memo_files)  # Gets the most recent file based on timestamp in filename
    print(f"Using memo file: {latest_memo_file}")

    # Load the memo data
    with open(latest_memo_file, 'r') as f:
        user_memos = json.load(f)

    stock_symbol = "NVDA"  # Change this to your target stock

    # Create a structured output
    output = {
        "analysis_metadata": {
            "timestamp": datetime.now().isoformat(),
            "stock_symbol": stock_symbol,
            "model_used": "anthropic/claude-3.5-haiku-20241022",
            "total_users_analyzed": 0,
            "average_credibility_score": 0
        },
        "user_analyses": {}
    }

    total_score = 0
    
    # Process the data
    for user_address, memos in user_memos.items():
        print(f"Analyzing user {user_address}...")
        analysis = analyzer.analyze_user_memos(memos, stock_symbol)
        if analysis:
            output["user_analyses"][user_address] = {
                "credibility_score": analysis['score'],
                "explanation": analysis['explanation'],
                "analysis_details": {
                    "memo_count": analysis['memo_count'],
                    "first_memo_date": analysis['date_range']['first'],
                    "last_memo_date": analysis['date_range']['last'],
                    "memo_timespan_days": (datetime.fromisoformat(analysis['date_range']['last']) - 
                                         datetime.fromisoformat(analysis['date_range']['first'])).days
                }
            }
            total_score += analysis['score']

    # Update metadata
    output["analysis_metadata"]["total_users_analyzed"] = len(output["user_analyses"])
    if output["analysis_metadata"]["total_users_analyzed"] > 0:
        output["analysis_metadata"]["average_credibility_score"] = (
            total_score / output["analysis_metadata"]["total_users_analyzed"]
        )

    # Save results with formatted timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_filename = f"credibility_analysis_{stock_symbol}_{timestamp}.json"
    
    with open(output_filename, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nAnalysis saved to {output_filename}")
    print(f"Analyzed {len(output['user_analyses'])} users")
    print(f"Average credibility score: {output['analysis_metadata']['average_credibility_score']:.2f}")

if __name__ == "__main__":
    main()