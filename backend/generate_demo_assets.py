import os
import io
import csv
import json
import random
import requests
from datetime import datetime, timedelta
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor

# Setup directories
os.makedirs("uploads", exist_ok=True)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen3-expert:latest"

def generate_text_via_ollama(prompt: str, fallback_text: str) -> str:
    """Queries the local Ollama instance for content, falling back to static text on failure."""
    print(f"Requesting text generation from local model '{MODEL_NAME}'...")
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False
            },
            timeout=30
        )
        if response.status_code == 200:
            result = response.json()
            return result.get("response", fallback_text).strip()
    except Exception as e:
        print(f"Ollama request failed: {e}. Trying fallback model 'timmy-gemma:latest'...")
        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": "timmy-gemma:latest",
                    "prompt": prompt,
                    "stream": False
                },
                timeout=20
            )
            if response.status_code == 200:
                result = response.json()
                return result.get("response", fallback_text).strip()
        except Exception:
            pass
    print("Ollama connection failed or timed out. Using built-in high-quality fallback text.")
    return fallback_text

def create_sales_csv():
    """Generates the sales_analytics_demo.csv dataset with trend-growth and anomalies."""
    print("Generating sales_analytics_demo.csv...")
    
    products = [
        {"name": "RTX 4070", "category": "GPUs", "base_price": 600, "q_growth": 0.05, "base_q": 120},
        {"name": "PS5 DualSense", "category": "Accessories", "base_price": 70, "q_growth": 0.06, "base_q": 700},
        {"name": "Gaming Monitor 27\"", "category": "Displays", "base_price": 300, "q_growth": 0.02, "base_q": 150},
        {"name": "Mech Keyboard TKL", "category": "Peripherals", "base_price": 100, "q_growth": 0.008, "base_q": 350},
        {"name": "NVMe SSD 2TB", "category": "Storage", "base_price": 150, "q_growth": -0.01, "base_q": 200},
        {"name": "Headset Pro X", "category": "Accessories", "base_price": 120, "q_growth": -0.02, "base_q": 210},
        {"name": "RTX 3060", "category": "GPUs", "base_price": 320, "q_growth": -0.15, "base_q": 110},  # Declining
        {"name": "1080p Webcam", "category": "Peripherals", "base_price": 80, "q_growth": -0.09, "base_q": 140}  # Declining
    ]
    
    channels = ["Online", "Retail", "Marketplace"]
    
    # Generate dates: Jan 2024 to Dec 2025
    start_date = datetime(2024, 1, 1)
    rows = []
    
    for month_idx in range(24):
        current_month = start_date + timedelta(days=month_idx * 30.5)
        month_str = current_month.strftime("%Y-%m-%d")
        
        is_anomaly_month = (current_month.year == 2025 and current_month.month == 8)  # Aug 2025
        
        for prod in products:
            for channel in channels:
                # Base quantity with random fluctuations
                q_trend = prod["base_q"] * ((1 + prod["q_growth"]) ** month_idx)
                
                # Apply product specific decline rate for the last 90 days of 2025 (month_idx >= 21)
                if month_idx >= 21:
                    if prod["name"] == "RTX 3060":
                        q_trend *= 0.39  # ~61% decline
                    elif prod["name"] == "1080p Webcam":
                        q_trend *= 0.62  # ~38% decline
                
                # Random noise +/- 10%
                noise = random.uniform(0.9, 1.1)
                quantity = max(1, int(q_trend * noise / len(channels)))
                
                # Inject sharp anomaly drop in Aug 2025 for all products (e.g. ~37% drop)
                if is_anomaly_month:
                    quantity = int(quantity * 0.63)
                
                # Calculate revenue
                price = prod["base_price"]
                revenue = quantity * price
                
                rows.append({
                    "order_date": month_str,
                    "product_name": prod["name"],
                    "category": prod["category"],
                    "revenue": revenue,
                    "units_sold": quantity,
                    "unit_price": price,
                    "channel": channel
                })
                
    # Write to CSV
    csv_path = "uploads/sales_analytics_demo.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["order_date", "product_name", "category", "revenue", "units_sold", "unit_price", "channel"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Sales CSV written to {csv_path} with {len(rows)} records.")

def create_compliance_pdf():
    """Generates the eu_packaging_compliance.pdf directive documentation."""
    print("Generating eu_packaging_compliance.pdf...")
    
    prompt = (
        "Write a detailed formal policy document titled 'EU Circular Economy & Electronic Waste Packaging Directive (Directive 2026/94/EC)'. "
        "The directive is introduced by the European Parliament in Q1 2026 to curb non-biodegradable packaging. "
        "Explicitly mention that legacy GPUs (specifically citing older generation graphic cards like the 'RTX 3060 series') "
        "and consumer peripherals (specifically citing '1080p webcams') placed on the market will face severe import tariffs, "
        "bans, or compliance audits due to their reliance on non-recyclable polymers. "
        "The tone should be highly formal and look like an official policy document."
    )
    
    fallback_text = (
        "<b>Directive 2026/94/EC of the European Parliament and of the Council</b><br/>"
        "<i>Dated: February 14, 2026</i><br/><br/>"
        "<b>Subject: Restriction of Non-Biodegradable Polymers and legacy electronics packaging compliance.</b><br/><br/>"
        "Under the provisions of the EU Circular Economy Framework, this directive establishes new guidelines for electronic hardware "
        "packaging imported into member states. Non-compliant packaging utilizing single-use plastics or non-recyclable polymers is "
        "subject to immediate restriction.<br/><br/>"
        "<b>Section 3.1: Scope of Legacy Graphics Processing Units (GPUs)</b><br/>"
        "Legacy GPU hardware containing older semiconductor form factors (specifically including the <b>RTX 3060 series</b> graphics cards) "
        "relying on bulk polystyrene packaging shall face a flat compliance tariff of 25% starting Q1 2026. Retailers are instructed "
        "to liquidate remaining inventory before the phase-out date.<br/><br/>"
        "<b>Section 3.2: Scope of Consumer Peripherals & Imaging Devices</b><br/>"
        "High-density plastic structures used in consumer peripherals (specifically including <b>1080p webcams</b> and standard-definition sensors) "
        "must transit to 100% recyclable cardboard casing. Failure to comply by March 31, 2026, will result in import restrictions in "
        "member states.<br/><br/>"
        "<b>Section 4: Budgetary Reallocations & Risk Assessment</b><br/>"
        "Brands are advised to reallocate marketing budgets and discontinue active promotion of these obsolescent and non-compliant SKUs. "
        "Inventory levels of RTX 3060 and 1080p webcams should be reduced immediately to avoid depreciation write-downs."
    )
    
    generated_content = generate_text_via_ollama(prompt, fallback_text)
    
    pdf_path = "uploads/eu_packaging_compliance.pdf"
    doc = SimpleDocTemplate(pdf_path, pagesize=letter, leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=HexColor('#1E293B'),
        spaceAfter=15
    )
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontSize=10.5,
        leading=16,
        textColor=HexColor('#334155'),
        spaceAfter=12
    )
    
    story = [
        Paragraph("DIRECTIVE 2026/94/EC OF THE EUROPEAN PARLIAMENT", title_style),
        Spacer(1, 10),
        Paragraph(generated_content.replace("\n", "<br/>"), body_style)
    ]
    
    doc.build(story)
    print(f"Compliance PDF written to {pdf_path}.")

if __name__ == "__main__":
    create_sales_csv()
    create_compliance_pdf()
    print("All demo files generated successfully in uploads/")
