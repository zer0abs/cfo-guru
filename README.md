# CFO AI

**A data-driven financial decision platform for e-commerce operators, combining forecasting, inventory planning, and scenario analysis.**

## Overview

CFO AI is a modular Streamlit application designed to support real-world business decision-making for an e-commerce company. It integrates profitability, cash flow, inventory, demand forecasting, sourcing, and growth quality into a single interactive system.

Rather than treating finance, operations, and forecasting as separate analyses, CFO AI brings them together into one decision layer—allowing users to understand what is happening, why it matters, and what actions to take.

The project focuses on practical, operator-level insights. It combines financial modeling, deterministic decision logic, and lightweight forecasting to simulate how real businesses evaluate tradeoffs and manage risk.

## Important Note

This project is a **demo application built around a hypothetical e-commerce business**.

- The company in the app is not a real business  
- Supplier options, scenarios, and forecasts are sample inputs used to demonstrate decision logic  
- The recommendations are rule-based illustrations of how an operator tool might guide decisions  
- The app is designed to show analytical thinking, product design, and business modeling, not live financial advice  

In other words, CFO AI is meant to simulate how a founder or operator could use a tool like this in practice.

---

## Key Features

### Financial Modeling

- Profitability analysis with decomposed unit costs  
- KPI tracking across revenue, margin, CAC, LTV, runway, and inventory turnover  
- Business Health Score combining profitability, liquidity, growth efficiency, and operational efficiency  

### Cash Flow & Risk

- Month-by-month cash forecasting  
- Runway analysis and negative-cash detection  
- Liquidity risk monitoring tied directly to operating assumptions  

### Inventory Intelligence

- Inventory purchase timing separated from fulfillment-at-sale costs  
- Stockout detection with lost-sales estimation  
- Overstock and excess-inventory detection  
- Inventory posture classification: `Tight`, `Balanced`, or `Excess`  

### Demand Forecasting

- Forecast baseline built from historical monthly demand  
- Multiple interpretable forecasting methods:
  - Moving Average  
  - Weighted Moving Average  
  - Exponential Smoothing  
- Trend detection (rising, stable, falling demand)  

### Channel Analytics

- Demand segmented into `paid`, `organic`, and `retention`  
- Channel-level acquisition cost modeling  
- Contribution and growth-quality analysis by channel  

### Scenario Analysis (Strategy Lab)

- Stress testing across:
  - Ad cost shock  
  - Demand drop  
  - Supplier cost increase  
  - Shipping cost increase  
  - Holiday demand spike  
  - Discount campaign  
- Baseline vs scenario comparisons across margin, cash, inventory, and demand quality  
- Scenario-driven recommendations  

### Supply Chain Optimizer

- Supplier comparison across:
  - Landed cost  
  - Lead time  
  - MOQ  
  - Reliability  
- Objective-based sourcing recommendations:
  - Cheapest  
  - Fastest  
  - Best value  
  - Best under cash pressure  
  - Best under stockout pressure  

### Executive Summary

- Automated operator-facing business summary  
- Clear top risks and opportunities  
- Prioritized recommended actions  
- Scenario and sourcing takeaways  
- Exportable summary outputs  

---

## Tech Stack

- Python  
- Streamlit  
- Pandas  
- NumPy  
- Plotly  
- Scikit-learn / Statsmodels (forecasting components)  

---

## Architecture

The project is structured modularly for clarity, maintainability, and extension.

- `modules/` — Core business logic (profitability, cashflow, forecasting, scenarios, supply chain, recommendations, reporting)  
- `components/` — Reusable UI elements and layouts  
- `utils/` — Shared helpers for formatting, state, and structure  
- `data/` — Demo and future datasets  
- `reports/` — Generated summaries and exports  

Business logic is separated from the Streamlit interface, and the system is primarily deterministic and rule-based, ensuring outputs are explainable and auditable.

---

## Example Use Cases

- Should I increase inventory before a demand spike?  
- Is my growth coming from low-quality paid demand?  
- Which supplier is best given my cash constraints?  
- What happens to my runway if ad costs increase?  
- Am I overstocked after a demand slowdown?  
- Is a lower-cost supplier worth the added lead-time risk?  

---

## Screenshots

### Executive Summary

![Executive Summary](path/to/executive-summary.png)

### Strategy Lab

![Strategy Lab](path/to/strategy-lab.png)

### Inventory & Cash Risk

![Inventory & Cash Risk](path/to/inventory-cash-risk.png)

### Supply Chain Optimizer

![Supply Chain Optimizer](path/to/supply-chain-optimizer.png)

---

## How to Run Locally

```bash
git clone <your-repo-url>
cd cfo_ai
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```
