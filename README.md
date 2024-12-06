# PFT Memo Analysis Tool

This tool collects and analyzes memos attached to PFT (Post Fiat Token) transactions on the XRPL blockchain. It includes:

- Memo collection from the XRPL
- Google Doc content fetching for memos containing doc links
- Credibility analysis of memo authors

## Setup

1. Clone this repository.
2. Install dependencies.
3. Update `config.json` with your OpenRouter API Key and the path to your Google Docs API credentials.

## Usage

1. Run the analysis script: 
   ```bash
   python run_analysis.py
   ```
2. The tool will:
   - Fetch PFT transaction memos from the XRPL.
   - Extract and process any Google Doc links.
   - Analyze author credibility.

### Output Files

- `pft_user_memos_.json`: Raw memo data.
- `credibility_analysis_.json`: Author credibility scores and analysis.
