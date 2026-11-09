"""
Telcel API Client & CLI
Standalone Python client to interact with Mi Telcel backend APIs.
Reverse engineered from Mi Telcel APK (v15.1.2) and Telcel Contenedor (v16.11.1).
"""

import sys
import os
import argparse
import base64
import urllib.parse
from typing import Optional, Dict, Any, List
import requests

# Endpoints
SSO_AUTHORIZE_URL = "https://oid.telcel-id.com:9000/authorize"
SSO_TOKEN_URL = "https://oid.telcel-id.com:9000/token"
SECURITY_TOKEN_URL = "https://mi-telcel.smapps.mx/security/1.0.0/v2/token"
API_BASE_URL = "https://mi-telcel.smapps.mx"
B2F_GATEWAY_URL = "https://api.gateway.telcel.wavebybemobi.com/api/v1"

# Client Constants extracted from APK
CLIENT_ID = "0b28e5a4-04a2-4af2-a706-247992076717"
CLIENT_SECRET = "da5b0985-68ef-46d8-84b3-246ffa6e0651"
REDIRECT_URI = "https://mitelcel.smapps.mx/sso/callback"
BASIC_AUTH_GATEWAY = "Basic bXRwc2VydmljZXM6NyQ4N3JmRnN3ZSQyMV8="

DEFAULT_HEADERS = {
    "App-Version": "15.1.2",
    "Code-Version": "1582",
    "Device-Id": "SPH",
    "Os": "GMS",
    "Os-Version": "14",
    "X-Channel": "mobile-app",
    "tipoRequest": "1",
}


class TelcelClient:
    """Client for authenticating and interacting with Mi Telcel and Wave by Bemobi backend services."""

    def __init__(self, msisdn: str, password: str, timeout: int = 15):
        clean_number = "".join(filter(str.isdigit, msisdn))
        if len(clean_number) == 10:
            self.user = clean_number
            self.sso_username = f"52{clean_number}"
        elif len(clean_number) == 12 and clean_number.startswith("52"):
            self.user = clean_number[2:]
            self.sso_username = clean_number
        else:
            self.user = clean_number
            self.sso_username = clean_number

        self.password = password
        self.timeout = timeout
        self.session = requests.Session()

        self.sso_token: Optional[str] = None
        self.mit_token: Optional[str] = None
        self.b2f_token: Optional[str] = None
        self.wso2_token: Optional[str] = None

        self.profile: Optional[str] = None
        self.region: Optional[str] = None
        self.name: Optional[str] = None
        self.email: Optional[str] = None

    def login(self) -> bool:
        """Perform OAuth2 SSO authentication flow and retrieve multi-scope service tokens."""
        # 1. Authorize Code Request
        auth_headers = {
            **DEFAULT_HEADERS,
            "USERNAME": self.sso_username,
            "PASSWORD": self.password,
        }
        auth_params = {
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "state": "MTP_App",
            "nonce": "M1T3c3L_Pls",
            "acr_values": "1",
            "scope": "openid",
            "client_id": CLIENT_ID,
        }

        r1 = self.session.get(
            SSO_AUTHORIZE_URL,
            headers=auth_headers,
            params=auth_params,
            allow_redirects=False,
            timeout=self.timeout,
        )

        loc = r1.headers.get("location", "")
        if not loc:
            raise RuntimeError(f"SSO Authorize failed: HTTP {r1.status_code} - {r1.text}")

        parsed_qs = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query)
        if "error" in parsed_qs:
            err = parsed_qs.get("error", ["Unknown error"])[0]
            err_desc = parsed_qs.get("error_description", [""])[0]
            raise ValueError(f"SSO Authentication Error: {err} ({err_desc})")

        auth_code = parsed_qs.get("code", [""])[0]
        if not auth_code:
            raise RuntimeError(f"No authorization code returned: {loc}")

        # 2. Token Exchange
        token_payload = {
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "code": auth_code,
            "client_id": CLIENT_ID,
        }
        r2 = self.session.post(
            SSO_TOKEN_URL,
            data=token_payload,
            auth=(CLIENT_ID, CLIENT_SECRET),
            headers=DEFAULT_HEADERS,
            timeout=self.timeout,
        )
        if r2.status_code != 200:
            raise RuntimeError(f"Token exchange failed: HTTP {r2.status_code} - {r2.text}")

        self.sso_token = r2.json().get("access_token")

        # 3. Security Service Token Exchange (token:mit, token:b2f, token:wso2)
        sec_headers = {
            **DEFAULT_HEADERS,
            "Authorization": BASIC_AUTH_GATEWAY,
            "scope": "token:mit|token:b2f|token:wso2",
        }
        r3 = self.session.get(
            SECURITY_TOKEN_URL,
            headers=sec_headers,
            params={"user": self.user, "token": self.sso_token},
            timeout=self.timeout,
        )
        if r3.status_code != 200:
            raise RuntimeError(f"Security token exchange failed: HTTP {r3.status_code} - {r3.text}")

        tokens_res = r3.json().get("tokenResponse", {}).get("tokens", [])
        token_map = {t.get("id"): t.get("access_token") for t in tokens_res}

        self.mit_token = token_map.get("token:mit")
        self.b2f_token = token_map.get("token:b2f")
        self.wso2_token = token_map.get("token:wso2")

        if not self.mit_token:
            raise RuntimeError("token:mit was not returned in security token response.")

        # Cache user info details
        self.get_user_info()
        return True

    def _api_headers(self) -> Dict[str, str]:
        if not self.mit_token:
            raise RuntimeError("Client not authenticated. Call login() first.")
        return {
            **DEFAULT_HEADERS,
            "Authorization": BASIC_AUTH_GATEWAY,
            "Token": self.mit_token,
            "user": self.user,
            "profile": self.profile or "AMIGO",
            "region": self.region or "4",
            "name": self.name or "",
            "email": self.email or "",
            "mode": "LIGHT",
            "Content-Type": "application/json",
        }

    def get_user_info(self) -> Dict[str, Any]:
        """Validate subscriber and retrieve line information (profile, region, name, email)."""
        url = f"{API_BASE_URL}/users/1.0.0/v2/info/validate"
        headers = {
            **DEFAULT_HEADERS,
            "Authorization": BASIC_AUTH_GATEWAY,
            "Token": self.mit_token,
            "Content-Type": "application/json",
        }
        resp = self.session.post(url, headers=headers, json={"user": self.user}, timeout=self.timeout)
        data = resp.json()
        val_info = data.get("validateUserInfoResponse", {})
        line_info = val_info.get("line", {})
        self.profile = line_info.get("profile", "AMIGO")
        self.region = str(line_info.get("region", "4"))

        info_obj = val_info.get("information", {})
        self.name = info_obj.get("name", "Usuario")
        self.email = info_obj.get("email", "")
        return data

    def get_consumption(self) -> Dict[str, Any]:
        """Retrieve active data consumption, package quota, percentage, and validity."""
        url = f"{API_BASE_URL}/users/1.0.0/consumption"
        params = {"user": self.user, "profile": self.profile, "region": self.region}
        resp = self.session.get(url, headers=self._api_headers(), params=params, timeout=self.timeout)
        return resp.json()

    def get_balance(self) -> Dict[str, Any]:
        """Retrieve prepaid balance, tariff scheme, and benefit sheets."""
        url = f"{API_BASE_URL}/users/1.0.0/balance"
        params = {"user": self.user, "profile": self.profile, "region": self.region}
        resp = self.session.get(url, headers=self._api_headers(), params=params, timeout=self.timeout)
        return resp.json()

    def get_statement_months(self) -> List[str]:
        """Retrieve list of months available for detailed consumption statements."""
        url = f"{API_BASE_URL}/users/1.0.0/consumption/details"
        params = {
            "user": self.user,
            "profile": self.profile,
            "region": self.region,
            "typeRequest": "getModule",
        }
        resp = self.session.get(url, headers=self._api_headers(), params=params, timeout=self.timeout)
        data = resp.json()
        months_arr = data.get("userConsumptionDetailsResponse", {}).get("mainModule", {}).get("months", [])
        return [m.get("month") for m in months_arr if m.get("month")]

    def download_statement_pdf(self, month: str, output_path: str) -> str:
        """Download official consumption PDF statement for a specific billing month."""
        url = f"{API_BASE_URL}/users/1.0.0/consumption/details"
        params = {
            "user": self.user,
            "profile": self.profile,
            "region": self.region,
            "typeRequest": "getAccount",
            "month": month,
        }
        resp = self.session.get(url, headers=self._api_headers(), params=params, timeout=30)
        data = resp.json()
        b64_doc = data.get("userConsumptionDetailsResponse", {}).get("document", "")
        if not b64_doc:
            raise RuntimeError(f"No document returned for month: {month}")

        pdf_bytes = base64.b64decode(b64_doc)
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
        return output_path

    def get_package_catalog(self) -> Dict[str, Any]:
        """Retrieve available packages and recharge catalog for the line's profile."""
        url = f"{API_BASE_URL}/packages/1.0.0/v1/list"
        params = {"user": self.user, "profile": self.profile, "region": self.region}
        resp = self.session.get(url, headers=self._api_headers(), params=params, timeout=self.timeout)
        return resp.json()

    def get_chatbot_session_url(self) -> str:
        """Create an authenticated Telcel Aivo Bot webview session URL."""
        url = f"{API_BASE_URL}/chatbot/1.0.0/session/createChatbotSession"
        payload = {
            "user": self.user,
            "session": self.sso_token,
            "name": self.name,
            "email": self.email,
            "region": self.region,
        }
        resp = self.session.post(url, headers=self._api_headers(), json=payload, timeout=self.timeout)
        data = resp.json()
        return data.get("createChatbotSessionResponse", {}).get("url", "")

    def get_recharge_frame_url(self) -> str:
        """Generate a pre-authenticated webview session URL for online balance recharge."""
        url = f"{API_BASE_URL}/IFrames/1.0.0/v1/balance-recharge/build"
        params = {
            "user": self.user,
            "profile": self.profile,
            "region": self.region,
            "account": "",
            "name": self.name,
            "email": self.email,
            "mode": "LIGHT",
        }
        resp = self.session.get(url, headers=self._api_headers(), params=params, timeout=self.timeout)
        data = resp.json()
        return data.get("balanceRechargeFrameResponse", {}).get("url", "")

    def get_saved_cards_url(self) -> str:
        """Generate a pre-authenticated webview session URL to manage saved debit/credit cards."""
        url = f"{API_BASE_URL}/IFrames/1.0.0/v1/saved-cards/build"
        params = {"user": self.user, "profile": self.profile, "region": self.region}
        resp = self.session.get(url, headers=self._api_headers(), params=params, timeout=self.timeout)
        data = resp.json()
        return data.get("savedCardsFrameResponse", {}).get("url", "")

    def get_b2f_line_status(self) -> Dict[str, Any]:
        """Query Wave by Bemobi microservice for instant line suspension & status."""
        if not self.b2f_token:
            raise RuntimeError("token:b2f is not available.")
        url = f"{B2F_GATEWAY_URL}/users/52{self.user}/line"
        headers = {"Authorization": f"Bearer {self.b2f_token}", "Content-Type": "application/json"}
        resp = self.session.get(url, headers=headers, timeout=self.timeout)
        return resp.json()


def print_consumption(cons: Dict[str, Any]):
    components = cons.get("userConsumptionResponse", {}).get("components", [])
    if not components:
        print("[!] No active consumption components returned.")
        return

    print("\n" + "=" * 55)
    print("              RESUMEN DE CONSUMO TELCEL")
    print("=" * 55)

    for comp in components:
        title = comp.get("title", "Consumo")
        print(f"\n>> {title}")
        for card in comp.get("cards", []):
            info = card.get("cardInfo", {})
            pkg_name = info.get("packageName", "Paquete")
            incl = info.get("dataIncluded", "N/A")
            used = info.get("dataUsed", "N/A")
            avail = info.get("dataAvailable", "N/A")
            validity = info.get("validity", "").replace("<b>", "").replace("</b>", "")
            pct_used = info.get("percentageUsed", 0)

            print(f"  * Paquete:   {pkg_name}")
            print(f"  * Incluidos: {incl}")
            print(f"  * Usados:    {used} ({pct_used}%)")
            print(f"  * Restante:  {avail}")
            if validity:
                print(f"  * Vigencia:  {validity}")
    print("=" * 55)


def print_balance(bal: Dict[str, Any]):
    resp = bal.get("userBalanceResponse", {})
    scheme = resp.get("scheme", {})
    print("\n" + "=" * 55)
    print("              SALDO Y ESQUEMA DE COBRO")
    print("=" * 55)
    print(f"  * Esquema:      {scheme.get('schemeName', 'N/A')}")
    benefits = scheme.get("schemeSheet", {}).get("sheetObject", {}).get("benefits", {}).get("list", [])
    if benefits:
        print("  * Beneficios:")
        for b in benefits:
            print(f"      - {b}")
    for comp in resp.get("components", []):
        msg = comp.get("cardMessage")
        if msg:
            print(f"  * Mensaje:      {msg}")
    print("=" * 55)


def print_packages(pkgs: Dict[str, Any]):
    sections = pkgs.get("listPackageResponse", {}).get("section", [])
    print("\n" + "=" * 55)
    print("              CATÁLOGO DE PAQUETES")
    print("=" * 55)
    for sec in sections:
        title = sec.get("sectionTitle", "Sección")
        items = sec.get("packages", [])
        print(f"\n>> {title} ({len(items)} disponibles)")
        for p in items[:5]:
            name = p.get("name", "N/A")
            cost = p.get("cost", "")
            mb = p.get("mb", "")
            validity = p.get("validity", "")
            print(f"   * {name:<32} | ${cost:<4} | {mb:<8} | {validity}")
    print("=" * 55)


def main():
    parser = argparse.ArgumentParser(description="Telcel API CLI - Interact with Mi Telcel backend services.")
    parser.add_argument("-u", "--user", required=True, help="10-digit Telcel phone number")
    parser.add_argument("-p", "--password", required=True, help="Mi Telcel account password")

    parser.add_argument("--consumption", action="store_true", help="Display current data usage (default)")
    parser.add_argument("--balance", action="store_true", help="Display balance and scheme benefits")
    parser.add_argument("--packages", action="store_true", help="List available recharge and package catalog")
    parser.add_argument("--statements", action="store_true", help="List available statement months")
    parser.add_argument("--download-statement", metavar="MONTH", help="Download PDF statement (e.g. 'Octubre - 2026')")
    parser.add_argument("--chatbot", action="store_true", help="Generate authenticated chatbot session URL")
    parser.add_argument("--recharge-url", action="store_true", help="Generate authenticated balance recharge URL")
    parser.add_argument("--cards-url", action="store_true", help="Generate authenticated saved cards URL")
    parser.add_argument("--line", action="store_true", help="Query Bemobi microservice for line status")
    parser.add_argument("--all", action="store_true", help="Run comprehensive query across all services")
    parser.add_argument("--json", action="store_true", help="Output raw JSON results")

    args = parser.parse_args()

    client = TelcelClient(args.user, args.password)
    try:
        print(f"[*] Authenticating with Telcel SSO ({client.user})...")
        client.login()
        print(f"[+] Authenticated: {client.name} | Profile: {client.profile} | Region: {client.region}")

        # Default action if no specific flag
        if not any([args.consumption, args.balance, args.packages, args.statements,
                    args.download_statement, args.chatbot, args.recharge_url,
                    args.cards_url, args.line, args.all]):
            args.consumption = True

        if args.all:
            args.consumption = True
            args.balance = True
            args.packages = True
            args.statements = True
            args.line = True
            args.chatbot = True
            args.recharge_url = True
            args.cards_url = True

        if args.consumption:
            cons = client.get_consumption()
            if args.json:
                import json
                print(json.dumps(cons, indent=2, ensure_ascii=False))
            else:
                print_consumption(cons)

        if args.balance:
            bal = client.get_balance()
            if args.json:
                import json
                print(json.dumps(bal, indent=2, ensure_ascii=False))
            else:
                print_balance(bal)

        if args.packages:
            pkgs = client.get_package_catalog()
            if args.json:
                import json
                print(json.dumps(pkgs, indent=2, ensure_ascii=False))
            else:
                print_packages(pkgs)

        if args.statements:
            months = client.get_statement_months()
            print("\n[+] Meses de estado de cuenta disponibles:")
            for m in months:
                print(f"    - {m}")

        if args.download_statement:
            out_file = f"telcel_statement_{args.download_statement.replace(' ', '_').replace('-', '_')}.pdf"
            print(f"[*] Downloading statement for '{args.download_statement}' to {out_file}...")
            client.download_statement_pdf(args.download_statement, out_file)
            print(f"[+] Download complete: {os.path.abspath(out_file)}")

        if args.line:
            status = client.get_b2f_line_status()
            print("\n[+] Wave B2F Line Status:")
            print(f"    - Perfil:     {status.get('profile')}")
            print(f"    - Suspendida: {status.get('isSuspended')}")

        if args.chatbot:
            bot_url = client.get_chatbot_session_url()
            print(f"\n[+] Chatbot Aivo Session URL:\n{bot_url}")

        if args.recharge_url:
            rec_url = client.get_recharge_frame_url()
            print(f"\n[+] Recarga en Línea Session URL:\n{rec_url}")

        if args.cards_url:
            cards_url = client.get_saved_cards_url()
            print(f"\n[+] Tarjetas Guardadas Session URL:\n{cards_url}")

    except Exception as e:
        print(f"[-] Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
