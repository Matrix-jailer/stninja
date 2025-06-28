import asyncio
import random
import re
from typing import List, Dict, Set, Any
from urllib.parse import urljoin, urlparse
from fastapi import FastAPI, HTTPException
from pydantic import HttpUrl
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from loguru import logger
from playwright.async_api import async_playwright, Page, BrowserContext
from playwright_stealth import stealth_async

# Configure logging
logger.remove()
logger.add("stealthninja.log", rotation="10 MB", level="DEBUG")

# Keyword definitions (exact counts from original stealthninja.py)
NETWORK_PAYMENT_URL_KEYWORDS = [
    re.compile(pattern, re.IGNORECASE) for pattern in [
        "/cart", "/checkout", "/payment", "/buy", "/purchase", "/order", "/billing", "/subscribe",
        "/shop", "/store", "/pricing", "/add-to-cart", "/pay-now", "/secure-checkout", "/complete-order",
        "/transaction", "/invoice", "/checkout2", "/donate", "/donation", "/add-to-bag", "/add-to-basket",
        "/shop-now", "/buy-now", "/order-now", "/proceed-to-checkout", "/pay", "/payment-method",
        "/credit-card", "/debit-card", "/place-order", "/confirm-purchase", "/get-started",
        "/sign-up", "/join-now", "/membership", "/upgrade", "/renew", "/trial", "/subscribe-now",
        "/book-now", "/reserve", "/fund", "/pledge", "/support", "/contribute",
        "/complete-purchase", "/finalize-order", "/payment-details", "/billing-info",
        "/secure-payment", "/pay-securely", "/shop-secure", "/give", "/donate-now", "/donatenow",
        "/donate_now", "/get-now", "/browse", "/items", "/product", "/item",
        "/giftcard", "/topup", "/plans", "/buynow"
    ]
]  # 64 patterns

GATEWAY_KEYWORDS = {
    'stripe': [re.compile(pattern, re.IGNORECASE) for pattern in [r'stripe\.com', r'data-stripe', r'client_secret']],
    'paypal': [re.compile(pattern, re.IGNORECASE) for pattern in [r'paypal\.com', r'paypalobjects', r'paypal-button']],
    'paytm': [re.compile(pattern, re.IGNORECASE) for pattern in [r'paytm\.com', r'paytm']],
    'razorpay': [re.compile(pattern, re.IGNORECASE) for pattern in [r'razorpay\.com', r'razorpay']],
    'square': [re.compile(pattern, re.IGNORECASE) for pattern in [r'squareup\.com', r'square']],
    'adyen': [re.compile(pattern, re.IGNORECASE) for pattern in [r'adyen\.com', r'adyen']],
    'braintree': [re.compile(pattern, re.IGNORECASE) for pattern in [r'braintreegateway\.com', r'braintree']],
    'authorize.net': [re.compile(pattern, re.IGNORECASE) for pattern in [r'authorize\.net', r'authnet']],
    'klarna': [re.compile(pattern, re.IGNORECASE) for pattern in [r'klarna\.com', r'klarna']],
    'checkout.com': [re.compile(pattern, re.IGNORECASE) for pattern in [r'checkout\.com', r'cko']],
    'Shopify Payments': [re.compile(pattern, re.IGNORECASE) for pattern in [r'shopify\.com/payments', r'shopify-checkout']],
    'worldpay': [re.compile(pattern, re.IGNORECASE) for pattern in [r'worldpay\.com', r'worldpay']],
    '2checkout': [re.compile(pattern, re.IGNORECASE) for pattern in [r'2checkout\.com', r'2co']],
    'Amazon pay': [re.compile(pattern, re.IGNORECASE) for pattern in [r'payments\.amazon\.com', r'amazon-pay']],
    'Apple pay': [re.compile(pattern, re.IGNORECASE) for pattern in [r'apple\.com/apple-pay', r'apple-pay']],
    'Google pay': [re.compile(pattern, re.IGNORECASE) for pattern in [r'pay\.google\.com', r'google-pay']],
    'mollie': [re.compile(pattern, re.IGNORECASE) for pattern in [r'mollie\.com', r'mollie']],
    'opayo': [re.compile(pattern, re.IGNORECASE) for pattern in [r'opayo\.com', r'opayo']],
    'paddle': [re.compile(pattern, re.IGNORECASE) for pattern in [r'paddle\.com', r'paddle']]
}  # 19 gateways

CAPTCHA_PATTERNS = {
    'reCaptcha': [re.compile(pattern, re.IGNORECASE) for pattern in [r'g-recaptcha', r'data-sitekey']],
    'hCaptcha': [re.compile(pattern, re.IGNORECASE) for pattern in [r'hcaptcha\.com', r'h-captcha']],
    'Turnstile': [re.compile(pattern, re.IGNORECASE) for pattern in [r'cf-turnstile', r'challenge-platform']],
    'Arkose Labs': [re.compile(pattern, re.IGNORECASE) for pattern in [r'arkoselabs\.com', r'arkose']],
    'GeeTest': [re.compile(pattern, re.IGNORECASE) for pattern in [r'geetest\.com', r'geetest']],
    'BotDetect': [re.compile(pattern, re.IGNORECASE) for pattern in [r'botdetect', r'captcha']],
    'KeyCAPTCHA': [re.compile(pattern, re.IGNORECASE) for pattern in [r'keycaptcha', r'key-captcha']],
    'Anti Bot Detection': [re.compile(pattern, re.IGNORECASE) for pattern in [r'anti-bot', r'bot-detection']],
    'Captcha': [re.compile(pattern, re.IGNORECASE) for pattern in [r'captcha', r'verify-human']]
}  # 9 captchas

CLOUDFLARE_KEYWORDS = [
    re.compile(pattern, re.IGNORECASE) for pattern in [
        r'cloudflare\.com', r'cf-ray', r'cf-chl-bypass', r'cf-turnstile', r'challenge-platform',
        r'cf_captcha', r'cf_clearance', r'cloudflare/turnstile', r'cf_challenge', r'cloudflareinsights\.com'
    ]
]  # 10 patterns

GRAPHQL_KEYWORDS = [
    re.compile(pattern, re.IGNORECASE) for pattern in [
        r'/graphql', r'graphql\.', r'query \{', r'mutation \{', r'graphql-endpoint', r'graphql-api', r'graphql/v1'
    ]
]  # 7 patterns

THREE_D_SECURE_KEYWORDS = [
    re.compile(pattern, re.IGNORECASE) for pattern in [
        r'3dsecure', r'3ds', r'acs', r'challenge', r'verifiedbyvisa', r'securecode', r'mastercard\.com/3ds',
        r'stripe\.com/3ds', r'adyen\.com/hpp', r'cardinalcommerce', r'3d-secure', r'3ds2', r'authentication',
        r'visa\.com/3ds', r'mastercard\.com/securecode', r'3d_secure', r'acs_url', r'pareq', r'pares',
        r'authentication_data', r'3ds_challenge', r'3ds_auth', r'3ds_redirect'
    ]
]  # 23 patterns

CARD_KEYWORDS = [
    re.compile(r'\b' + card_type + r'\b', re.IGNORECASE) for card_type in [
        'visa', 'mastercard', 'amex', 'american express', 'discover', 'diners club', 'jcb'
    ]
]  # 7 card types

PLATFORM_KEYWORDS = {
    'shopify': 'shopify', 'woocommerce': 'woocommerce', 'magento': 'magento',
    'bigcommerce': 'bigcommerce', 'squarespace': 'squarespace'
}  # 5 platforms

BUTTON_KEYWORDS = [
    'pay', 'checkout', 'subscribe', 'purchase', 'buy', 'order', 'upgrade',
    'billing', 'shop', 'add to cart', 'price', 'plan'
]  # 12 keywords

NON_HTML_EXTENSIONS = [
    '.css', '.js', '.jpg', '.jpeg', '.png', '.gif', '.svg', '.woff', '.woff2',
    '.ttf', '.eot'
]  # 11 extensions

SKIP_DOMAINS = [
    'google-analytics.com', 'googletagmanager.com', 'facebook.com', 'twitter.com',
    'usercentrics.eu', 'app.usercentrics.eu', 'doubleclick.net', 'adservice.google.com',
    'cloudflare.com', 'gstatic.com'
]  # 10 domains

IGNORE_IF_URL_CONTAINS = [
    "wp-content", "wp-includes", "skin/frontend", "/assets/", "/themes/", "/static/",
    "/media/", "/images/", "/img/", "https://facebook.com", "https://googletagmanager.com",
    "https://static.klaviyo.com", "content-autofill.googleapis.com", "https://www.google.com",
    "googleads.g.doubleclick.net", "https://www.googletagmanager.com", "googletagmanager.com",
    "https://www.googleadservices.com", "googleadservices.com", "https://fonts.googleapis.com",
    "fonts.googleapis.com", "http://clients2.google.com", "clients2.google.com",
    "https://analytics.google.com", "analytics.google.com", "googleapis", "gstatic",
    "googletagmanager", "google-analytics", "analytics", "doubleclick.net", "facebook.net",
    "fbcdn", "pixel.", "tiktokcdn", "matomo", "segment.io", "clarity.ms", "mouseflow",
    "hotjar", "fonts.", "fontawesome"
]  # 41 patterns

class StealthPaymentDetector:
    """A stealth web scraper for detecting payment gateways and related features."""

    def __init__(self):
        """Initialize the detector with user agent and crawling settings."""
        self.ua = UserAgent()
        self.results: Dict[str, Any] = {
            "payment_gateways": [],
            "captchas": [],
            "cloudflare": False,
            "graphql": False,
            "3ds": [],
            "platforms": [],
            "cards": [],
            "network_requests": [],
            "hidden_payment_data": []
        }
        self.visited_urls: Set[str] = set()
        self.max_depth: int = 2  # Match GhostAPIPRO.py
        self.max_urls: int = 50  # Match GhostAPIPRO.py

    def is_valid_url(self, url: str) -> bool:
        """Check if a URL is valid for crawling."""
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False
        if any(ext in url.lower() for ext in NON_HTML_EXTENSIONS):
            return False
        if any(domain in parsed.netloc for domain in SKIP_DOMAINS):
            return False
        if any(ignore in url.lower() for ignore in IGNORE_IF_URL_CONTAINS):
            return False
        return parsed.netloc == urlparse(list(self.visited_urls)[0] if self.visited_urls else url).netloc

    async def crawl_page(self, page: Page, url: str, depth: int = 0) -> List[str]:
        """Crawl a page and collect payment-related URLs."""
        if depth > self.max_depth or len(self.visited_urls) >= self.max_urls:
            return []
        try:
            await page.goto(url, timeout=30000)
            links = await page.query_selector_all('a[href]')
            payment_related_urls = []
            tasks = []
            for link in links:
                href = await link.get_attribute('href')
                absolute_url = urljoin(url, href)
                if self.is_valid_url(absolute_url) and absolute_url not in self.visited_urls:
                    self.visited_urls.add(absolute_url)
                    if any(pattern.search(absolute_url.lower()) for pattern in NETWORK_PAYMENT_URL_KEYWORDS):
                        payment_related_urls.append(absolute_url)
                        logger.debug(f"Found payment-related URL: {absolute_url}")
                    tasks.append(self.crawl_page(page, absolute_url, depth + 1))
            await asyncio.gather(*tasks, return_exceptions=True)
            return payment_related_urls
        except Exception as e:
            logger.error(f"Error crawling {url}: {e}")
            return []

    async def analyze_page(self, page: Page, url: str) -> None:
        """Analyze a page for payment gateways, captchas, and other features."""
        try:
            await page.goto(url, timeout=30000)
            await page.wait_for_timeout(5000)  # Replace time.sleep(5)
            page_source = await page.content()
            soup = BeautifulSoup(page_source, 'lxml')

            # DOM Tags Analysis
            for gateway, patterns in GATEWAY_KEYWORDS.items():
                for pattern in patterns:
                    if pattern.search(page_source.lower()) and gateway not in self.results["payment_gateways"]:
                        self.results["payment_gateways"].append(gateway)

            for captcha, patterns in CAPTCHA_PATTERNS.items():
                for pattern in patterns:
                    if pattern.search(page_source.lower()) and captcha not in self.results["captchas"]:
                        self.results["captchas"].append(captcha)

            for pattern in CLOUDFLARE_KEYWORDS:
                if pattern.search(page_source.lower()):
                    self.results["cloudflare"] = True

            for pattern in GRAPHQL_KEYWORDS:
                if pattern.search(page_source.lower()):
                    self.results["graphql"] = True

            for pattern in THREE_D_SECURE_KEYWORDS:
                if pattern.search(page_source.lower()) and pattern.pattern not in self.results["3ds"]:
                    self.results["3ds"].append(pattern.pattern)

            for platform, keyword in PLATFORM_KEYWORDS.items():
                if keyword in page_source.lower() and platform not in self.results["platforms"]:
                    self.results["platforms"].append(platform)

            for pattern in CARD_KEYWORDS:
                if pattern.search(page_source.lower()) and pattern.pattern not in self.results["cards"]:
                    self.results["cards"].append(pattern.pattern)

            # Hidden Inputs and Script Content
            for input_elem in soup.find_all("input", type="hidden"):
                name = input_elem.get("name", "")
                value = input_elem.get("value", "")
                for gateway, patterns in GATEWAY_KEYWORDS.items():
                    for pattern in patterns:
                        if pattern.search(name) or pattern.search(value):
                            self.results["hidden_payment_data"].append({
                                "type": "hidden_input",
                                "name": name,
                                "value": value,
                                "gateway": gateway
                            })

            for script in soup.find_all("script"):
                script_content = script.get_text()
                for gateway, patterns in GATEWAY_KEYWORDS.items():
                    for pattern in patterns:
                        if pattern.search(script_content):
                            self.results["hidden_payment_data"].append({
                                "type": "script_content",
                                "content_snippet": script_content[:100],
                                "gateway": gateway
                            })

            # Shadow DOM Analysis
            async def get_shadow_dom(element):
                try:
                    shadow_root = await page.evaluate_handle('el => el.shadowRoot', element)
                    if shadow_root:
                        shadow_html = await page.evaluate('el => el.innerHTML', shadow_root)
                        for gateway, patterns in GATEWAY_KEYWORDS.items():
                            for pattern in patterns:
                                if pattern.search(shadow_html.lower()) and gateway not in self.results["payment_gateways"]:
                                    self.results["payment_gateways"].append(gateway)
                        for pattern in THREE_D_SECURE_KEYWORDS:
                            if pattern.search(shadow_html.lower()) and pattern.pattern not in self.results["3ds"]:
                                self.results["3ds"].append(pattern.pattern)
                except:
                    pass

            elements = await page.query_selector_all('*')
            for element in elements:
                await get_shadow_dom(element)

            # Network Requests (Sources Tab)
            async def capture_network_requests():
                async def on_request(request):
                    request_url = request.url.lower()
                    if any(pattern.search(request_url) for pattern in NETWORK_PAYMENT_URL_KEYWORDS):
                        self.results["network_requests"].append(request_url)
                        for gateway, patterns in GATEWAY_KEYWORDS.items():
                            for pattern in patterns:
                                if pattern.search(request_url) and gateway not in self.results["payment_gateways"]:
                                    self.results["payment_gateways"].append(gateway)
                        for pattern in THREE_D_SECURE_KEYWORDS:
                            if pattern.search(request_url) and pattern.pattern not in self.results["3ds"]:
                                self.results["3ds"].append(pattern.pattern)

                page.on("request", on_request)

            await capture_network_requests()

            # Click Payment-Related Buttons
            buttons = await page.query_selector_all('button, input[type="submit"], a')
            for button in buttons:
                text = (await button.inner_text()).lower()
                if any(keyword in text for keyword in BUTTON_KEYWORDS):
                    try:
                        await button.click(timeout=5000)
                        await page.wait_for_timeout(2000)
                        page_source = await page.content()
                        soup = BeautifulSoup(page_source, 'lxml')
                        for gateway, patterns in GATEWAY_KEYWORDS.items():
                            for pattern in patterns:
                                if pattern.search(page_source.lower()) and gateway not in self.results["payment_gateways"]:
                                    self.results["payment_gateways"].append(gateway)
                        for input_elem in soup.find_all("input", type="hidden"):
                            name = input_elem.get("name", "")
                            value = input_elem.get("value", "")
                            for gateway, patterns in GATEWAY_KEYWORDS.items():
                                for pattern in patterns:
                                    if pattern.search(name) or pattern.search(value):
                                        self.results["hidden_payment_data"].append({
                                            "type": "hidden_input",
                                            "name": name,
                                            "value": value,
                                            "gateway": gateway
                                        })
                    except:
                        pass

        except Exception as e:
            logger.error(f"Error analyzing {url}: {e}")

    async def playwright_network_analysis(self, url: str) -> Dict[str, Any]:
        """Analyze a website for payment gateways and related features using Playwright."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=self.ua.random,
                viewport={"width": random.randint(800, 1920), "height": random.randint(600, 1080)},
                bypass_csp=True,
                ignore_https_errors=True
            )
            page = await context.new_page()
            await stealth_async(page)  # Apply stealth settings

            # Check initial URL for payment indicators (your requested change)
            await page.wait_for_timeout(5000)  # Replace time.sleep(5)
            has_payment_indicators = any(pattern.search(url.lower()) for pattern in NETWORK_PAYMENT_URL_KEYWORDS)
            if has_payment_indicators:
                logger.debug(f"Initial URL is payment-related: {url}")

            # Crawl to collect payment-related URLs
            payment_urls = await self.crawl_page(page, url)
            if has_payment_indicators:
                payment_urls.insert(0, url)  # Include initial URL if payment-related

            # Analyze payment-related URLs
            for payment_url in payment_urls:
                logger.debug(f"Analyzing payment URL: {payment_url}")
                await self.analyze_page(page, payment_url)

            await browser.close()
            return self.results

# FastAPI application
app = FastAPI(title="StealthNinja Payment Detector", version="1.0.0")

@app.get("/gate/search")
async def search_payment_indicators(url: HttpUrl):
    """API endpoint to analyze a URL for payment indicators."""
    try:
        detector = StealthPaymentDetector()
        result = await detector.playwright_network_analysis(str(url))
        return result
    except Exception as e:
        logger.error(f"Error processing {url}: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing {url}: {str(e)}")
