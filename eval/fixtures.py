"""Pre-generated LLM response fixtures for offline/mock eval runs."""
from __future__ import annotations

RESEARCH_REPORTS: dict[str, dict] = {
    "AAPL": {
        "ticker": "AAPL",
        "summary": "Apple reported strong Q4 FY2024 results with revenue of $94.9B (+6% YoY), beating estimates. iPhone revenue of $46.2B and record Services revenue of $24.97B reflect durable demand. Apple Intelligence rollout with iOS 18.1 is supporting the upgrade cycle, with 20% of users upgrading in the first week. Supply chain checks indicate 10% higher iPhone 16 Pro production orders for Q4. Barclays raised its price target to $260.",
        "sentiment": "bullish",
        "confidence": 0.82,
        "citations": [
            "[1] (2024-10-31 via Reuters): Apple Inc. reported Q4 FY2024 revenue of $94.9 billion, up 6% YoY, beating analyst consensus of $94.3 billion.",
            "[2] (2024-10-29 via Bloomberg): Apple began rolling out Apple Intelligence AI features with iOS 18.1. Analysts estimate 20% of iPhone users upgraded within the first week.",
            "[3] (2024-10-22 via Barclays Research): Supply chain checks suggest Apple increased iPhone 16 Pro production orders by 10% for Q4. Barclays raised price target to $260 from $240.",
        ],
        "recommendation": "buy",
    },
    "MSFT": {
        "ticker": "MSFT",
        "summary": "Microsoft delivered a strong Q1 FY2025 with Azure accelerating to 33% growth (from 29% prior quarter), driven by AI workload demand. Intelligent Cloud revenue of $24.1B beat estimates. Copilot for M365 now has 300M paid-eligible seats with 70% of Fortune 500 on Azure AI. CFO guided Q2 Azure growth of 34-35%, signalling continued acceleration. Goldman Sachs reiterated Buy at $500.",
        "sentiment": "bullish",
        "confidence": 0.85,
        "citations": [
            "[1] (2024-10-30 via CNBC): Microsoft reported Q1 FY2025 revenue of $65.6B, up 16% YoY. Azure grew 33% YoY, accelerating from 29%.",
            "[2] (2024-10-24 via Goldman Sachs): Copilot for M365 has over 300M paid seats. 70% of Fortune 500 using Azure AI. Goldman reiterated Buy at $500.",
        ],
        "recommendation": "buy",
    },
    "GOOGL": {
        "ticker": "GOOGL",
        "summary": "Alphabet beat Q3 2024 estimates across all segments: Search +12%, Cloud +35%, YouTube +12%. EPS of $2.12 significantly beat the $1.85 estimate. AI Overviews in Search are showing higher monetisation rates than traditional results in early tests, with 1B monthly active users. Deutsche Bank raised its price target to $210.",
        "sentiment": "bullish",
        "confidence": 0.79,
        "citations": [
            "[1] (2024-10-29 via Wall Street Journal): Alphabet reported Q3 2024 revenue of $88.3B, up 15% YoY. Google Cloud hit $11.4B, up 35%. EPS $2.12 beat $1.85 estimate.",
            "[2] (2024-10-30 via Deutsche Bank): AI Overviews showing higher monetisation rates. 1B monthly active users. Deutsche Bank raised price target to $210.",
        ],
        "recommendation": "buy",
    },
    "AMZN": {
        "ticker": "AMZN",
        "summary": "Amazon posted record Q3 2024 operating income of $17.4B with AWS margins expanding to 38.1%. AWS grew 19% to $27.5B, beating estimates. Multi-year AI infrastructure deals with hyperscalers and the Trainium2 chip GA strengthen the competitive moat. Q4 operating income guided at $16-20B, a wide range but well above prior year.",
        "sentiment": "bullish",
        "confidence": 0.78,
        "citations": [
            "[1] (2024-10-31 via Reuters): Amazon Q3 2024 AWS grew 19% to $27.5B. Operating income record $17.4B, AWS margins 38.1%.",
            "[2] (2024-10-25 via Bloomberg): AWS secured multi-year AI infrastructure deals worth over $1B each. Trainium2 now generally available.",
        ],
        "recommendation": "buy",
    },
    "NVDA": {
        "ticker": "NVDA",
        "summary": "Nvidia Blackwell GPU shipments have begun with demand far exceeding supply and a 12-month backlog. Data center revenue is tracking toward $30B for Q3 FY2025. However, Taiwan supply constraints from TSMC for CoWoS advanced packaging represent a near-term risk that could limit Q4 guidance upside. Valuation at 35x forward earnings is elevated. Mixed signals warrant a modest position.",
        "sentiment": "bullish",
        "confidence": 0.68,
        "citations": [
            "[1] (2024-10-23 via Bank of America): Nvidia Blackwell GPU shipments begun. CEO Jensen Huang: demand far exceeds supply with 12-month backlog. BofA raised PT to $190.",
            "[2] (2024-10-28 via Wells Fargo): Data center revenue tracking near $30B for Q3. Consensus rising to $32.5B for Q4. Wells Fargo Overweight at $185.",
            "[3] (2024-10-21 via Needham): TSMC flagged CoWoS capacity constraints for Blackwell. Needham maintains Hold citing 35x forward earnings valuation.",
        ],
        "recommendation": "buy",
    },
    "SPY": {
        "ticker": "SPY",
        "summary": "Insufficient evidence to form a direct view on SPY as a trading target.",
        "sentiment": "neutral",
        "confidence": 0.2,
        "citations": ["[1] No sufficient evidence retrieved."],
        "recommendation": "hold",
    },
}

TRADE_PROPOSALS: list[dict] = [
    {
        "ticker": "AAPL",
        "side": "BUY",
        "shares": 250,
        "rationale": "Strong Q4 beat, Services record, AI upgrade cycle underway. High confidence.",
        "citations": ["[1] Reuters Q4 beat", "[2] Bloomberg iOS 18.1 upgrade"],
        "confidence": 0.82,
    },
    {
        "ticker": "MSFT",
        "side": "BUY",
        "shares": 20,
        "rationale": "Azure acceleration to 33%, Copilot monetisation scaling. Strong buy signal.",
        "citations": ["[1] CNBC Azure 33% growth", "[2] Goldman Sachs 300M Copilot seats"],
        "confidence": 0.85,
    },
    {
        "ticker": "GOOGL",
        "side": "BUY",
        "shares": 30,
        "rationale": "Cloud +35%, Search AI monetisation upside, EPS beat. Attractive risk/reward.",
        "citations": ["[1] WSJ Q3 beat", "[2] Deutsche Bank AI Overviews"],
        "confidence": 0.79,
    },
    {
        "ticker": "NVDA",
        "side": "BUY",
        "shares": 15,
        "rationale": "Blackwell demand > supply, data center revenue tracking $30B. Supply risk limits size.",
        "citations": ["[1] BofA Blackwell launch", "[2] Wells Fargo $30B tracking"],
        "confidence": 0.68,
    },
]

RISK_ASSESSMENTS: list[dict] = [
    {
        "ticker": "AAPL",
        "approved": True,
        "risk_flags": [],
        "requires_hitl": False,
        "adjusted_shares": None,
    },
    {
        "ticker": "MSFT",
        "approved": True,
        "risk_flags": [],
        "requires_hitl": False,
        "adjusted_shares": None,
    },
    {
        "ticker": "GOOGL",
        "approved": True,
        "risk_flags": [],
        "requires_hitl": False,
        "adjusted_shares": None,
    },
    {
        "ticker": "NVDA",
        "approved": True,
        "risk_flags": ["supply chain concentration risk", "elevated valuation"],
        "requires_hitl": False,
        "adjusted_shares": None,
    },
]

DAILY_NARRATIVE = (
    "Trading day 2024-10-31: Strong earnings season drove broad-based buy signals across the tech universe. "
    "Apple beat Q4 estimates with record Services revenue and AI-driven upgrade momentum. Microsoft Azure "
    "accelerated to 33% growth with Copilot monetisation scaling. Alphabet delivered a clean Q3 beat with "
    "Cloud up 35%. Amazon posted record operating margins in AWS. Nvidia remains the highest-conviction AI "
    "infrastructure play despite near-term supply constraints. The portfolio initiated positions across all "
    "four names. Risk flags on NVDA noted; position sized conservatively. No HITL events triggered."
)
