# Telcel API Client & CLI

A lightweight, standalone Python client and command-line interface to interact with América Móvil / Mi Telcel backend APIs.

Reverse engineered from the official Mi Telcel Android application (`com.speedymovil.wire`, v15.1.2) and Telcel Contenedor (`com.telcel.contenedor`, v16.11.1).

---

## Capabilities & Verified Features

| Capability | Backend Endpoint | CLI Flag | Description |
| :--- | :--- | :--- | :--- |
| **Authentication & Tokens** | `oid.telcel-id.com:9000/token` & `security/1.0.0/v2/token` | *(Automatic)* | Performs PKCE OAuth2 login, acquires `ssoToken`, and exchanges it for multi-scope tokens (`token:mit`, `token:b2f`, `token:wso2`). |
| **Line & Account Validation** | `/users/1.0.0/v2/info/validate` | *(Automatic)* | Validates account identity, full name, email, commercial scheme (`AMIGO` / `MASIVO`), and regional routing (`region=4`). |
| **Real-Time Consumption** | `/users/1.0.0/consumption` | `--consumption` | Active data packages, megabytes consumed, remaining quota, percentage, and validity countdown. |
| **Balance & Tariff Scheme** | `/users/1.0.0/balance` | `--balance` | Prepaid saldo, current tariff plan, and list of included roaming/voice/data benefits. |
| **Historical Statement Months** | `/users/1.0.0/consumption/details` | `--statements` | Lists all billing months available for detailed consumption statements. |
| **Download Statement PDF** | `/users/1.0.0/consumption/details` | `--download-statement <MONTH>` | Decodes and exports the official Telcel consumption statement PDF directly to disk. |
| **Package & Recharge Catalog**| `/packages/1.0.0/v1/list` | `--packages` | Available packages, roaming bundles, and recharge options. |
| **Wave B2F Line Status** | `api.gateway.telcel.wavebybemobi.com/api/v1/users/52{phone}/line` | `--line` | Queries Bemobi microservices for line suspension status and profile. |
| **Chatbot Aivo Session** | `/chatbot/1.0.0/session/createChatbotSession` | `--chatbot` | Generates pre-authenticated session URLs for Telcel's Aivo customer support assistant. |
| **Online Recharge Portal** | `/IFrames/1.0.0/v1/balance-recharge/build` | `--recharge-url` | Generates a pre-authenticated webview session URL for online payment and card recharges. |
| **Saved Cards Wallet** | `/IFrames/1.0.0/v1/saved-cards/build` | `--cards-url` | Generates a pre-authenticated session URL to manage debit/credit cards tokenized with Vesta. |

---

## Installation

```bash
git clone https://github.com/r0bledas/telcel-api-client.git
cd telcel-api-client
pip install -r requirements.txt
```

---

## CLI Usage & Examples

### 1. Run All Checks (Full Health & Status Report)
```bash
python telcel_client.py -u 5512345678 -p YOUR_PASSWORD --all
```

### 2. Check Data Consumption & Remaining Megabytes
```bash
python telcel_client.py -u 5512345678 -p YOUR_PASSWORD --consumption
```

### 3. Check Current Scheme & Benefits
```bash
python telcel_client.py -u 5512345678 -p YOUR_PASSWORD --balance
```

### 4. Check Available Statement Months & Download Official PDF
```bash
# Check available months
python telcel_client.py -u 5512345678 -p YOUR_PASSWORD --statements

# Download a specific month's PDF
python telcel_client.py -u 5512345678 -p YOUR_PASSWORD --download-statement "Octubre - 2026"
```

### 5. Generate Pre-Authenticated Webview Session URLs
```bash
# Chatbot support
python telcel_client.py -u 5512345678 -p YOUR_PASSWORD --chatbot

# Online recharge
python telcel_client.py -u 5512345678 -p YOUR_PASSWORD --recharge-url

# Manage saved credit/debit cards
python telcel_client.py -u 5512345678 -p YOUR_PASSWORD --cards-url
```

### 6. Export Machine-Readable JSON
```bash
python telcel_client.py -u 5512345678 -p YOUR_PASSWORD --consumption --json
```

---

## Python Library Usage

```python
from telcel_client import TelcelClient

# Initialize client with placeholder
client = TelcelClient(msisdn="5512345678", password="YOUR_PASSWORD")

# Perform full SSO & security token exchange
client.login()
print(f"Logged in as: {client.name} | Scheme: {client.profile} | Region: {client.region}")

# 1. Query Data Usage
consumption = client.get_consumption()

# 2. Query Balance & Tariff Scheme
balance = client.get_balance()

# 3. Download statement PDF
months = client.get_statement_months()
client.download_statement_pdf(months[0], "statement.pdf")

# 4. Generate direct payment session URL
recharge_url = client.get_recharge_frame_url()
```

---

## Security & Architecture Summary

- **SSO Identity Provider:** `https://oid.telcel-id.com:9000` (OAuth2 Authorization Code flow with basic authentication client secret).
- **Core API Gateway:** `https://mi-telcel.smapps.mx` (Authenticated via `Token: <token:mit>` and `Authorization: Basic bXRwc2VydmljZXM6NyQ4N3JmRnN3ZSQyMV8=`).
- **Wave Gateway:** `https://api.gateway.telcel.wavebybemobi.com` (Wave by Bemobi, authenticated via `token:b2f`).

---

## Disclaimer

This project is for educational, interoperability, and reverse engineering research purposes only. All trademarks belong to América Móvil / Radiomóvil Dipsa, S.A. de C.V. (Telcel).
