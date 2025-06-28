import re
import json
import asyncio
import random
import logging
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright.async_api import async_playwright
from seleniumwire import webdriver
from fake_useragent import UserAgent
from urllib.parse import urlparse
import time
from selenium.webdriver.common.by import By

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Provided keyword lists and regex patterns (unchanged)
NETWORK_PAYMENT_URL_KEYWORDS = [
    "/checkout", "/payment", "/pay", "/setup_intent", "/authorize_payment", "/intent",
    "/confirm", "/charge", "/authorize", "/submit_payment", "/create_order",
    "/payment_intent", "/process_payment", "/transaction", "/confirm_payment",
    "/capture", "/payment-method", "/billing", "/invoice", "/order/submit",
    "/tokenize", "/session", "/execute-payment", "/complete"
]

IGNORE_IF_URL_CONTAINS = [
    "wp-content", "wp-includes", "skin/frontend", "/assets/", "/themes/", "/static/",
    "/media/", "/images/", "/img/", "https://facebook.com", "https://googlemanager.com",
    "https://static.klaviyo.com", "static.klaviyo.com", "https://content-autofill.googleapis.com",
    "content-autofill.googleapis.com", "https://www.google.com", "https://googleads.g.doubleclick.net",
    "googleads.g.doubleclick.net", "https://www.googletagmanager.com", "googletagmanager.com",
    "https://www.googleadservices.com", "googleadservices.com", "https://fonts.googleapis.com",
    "fonts.googleapis.com", "http://clients2.google.com", "clients2.google.com",
    "https://analytics.google.com", "hanalytics.google.com", "googleapis", "gstatic",
    "googletagmanager", "google-analytics", "analytics", "doubleclick.net", "facebook.net",
    "fbcdn", "pixel.", "tiktokcdn", "matomo", "segment.io", "clarity.ms", "mouseflow",
    "hotjar", "fonts.", "fontawesome", ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".ico", ".svg", "cdn.jsdelivr.net", "cloudflareinsights.com", "cdnjs", "bootstrapcdn",
    "polyfill.io", "jsdelivr.net", "unpkg.com", "yastatic.net", "akamai", "fastly",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".ico", ".css", ".scss",
    ".less", ".map", ".js", "main.js", "bundle.js", "common.js", "theme.js", "style.css",
    "custom.css", "/favicon", "/robots.txt", "/sitemap", "/manifest", "/rss", "/feed",
    "/help", "/support", "/about", "/terms", "/privacy"
]

PAYMENT_GATEWAYS = [
    "stripe", "paypal", "paytm", "razorpay", "square", "adyen", "braintree"
]

CAPTCHA_PATTERNS = {
    "reCaptcha": ["g-recaptcha", "recaptcha/api.js", "data-sitekey", "nocaptcha", "recaptcha.net", "www.google.com/recaptcha", "grecaptcha.execute", "grecaptcha.render", "grecaptcha.ready", "recaptcha-token"],
    "hCaptcha": ["hcaptcha", "assets.hcaptcha.com", "hcaptcha.com/1/api.js", "data-hcaptcha-sitekey", "js.stripe.com/v3/hcaptcha-invisible", "hcaptcha-invisible", "hcaptcha.execute"],
    "Turnstile": ["turnstile", "challenges.cloudflare.com", "cf-turnstile-response", "data-sitekey", "__cf_chl_", "cf_clearance"],
    "Arkose Labs": ["arkose-labs", "funcaptcha", "client-api.arkoselabs.com", "fc-token", "fc-widget", "arkose", "press and hold", "funcaptcha.com"],
    "GeeTest": ["geetest", "gt_captcha_obj", "gt.js", "geetest_challenge", "geetest_validate", "geetest_seccode"],
    "BotDetect": ["botdetectcaptcha", "BotDetect", "BDC_CaptchaImage", "CaptchaCodeTextBox"],
    "KeyCAPTCHA": ["keycaptcha", "kc_submit", "kc__widget", "s_kc_cid"],
    "Anti Bot Detection": ["fingerprintjs", "js.challenge", "checking your browser", "verify you are human", "please enable javascript and cookies", "sec-ch-ua-platform"],
    "Captcha": ["captcha-container", "captcha-box", "captcha-frame", "captcha_input", "id=\"captcha\"", "class=\"captcha\"", "iframe.+?captcha", "data-captcha-sitekey"]
}

PLATFORM_KEYWORDS = {
    "woocommerce": "WooCommerce", "shopify": "Shopify", "magento": "Magento",
    "bigcommerce": "BigCommerce", "prestashop": "PrestaShop", "opencart": "OpenCart",
    "wix": "Wix", "squarespace": "Squarespace"
}

CARD_KEYWORDS = [re.compile(pattern, re.IGNORECASE) for pattern in [
    r'visa', r'mastercard', r'amex', r'discover', r'diners', r'jcb', r'unionpay',
    r'maestro', r'rupay', r'cartasi', r'hipercard'
]]

THREE_D_SECURE_KEYWORDS = [re.compile(pattern, re.IGNORECASE) for pattern in [
    r'three_d_secure', r'3dsecure', r'acs', r'acs_url', r'acsurl', r'redirect',
    r'secure-auth', r'three_d_secure_usage', r'challenge', r'3ds', r'3ds1', r'3ds2',
    r'tds', r'tdsecure', r'3d-secure', r'three-d', r'3dcheck', r'3d-auth', r'three-ds',
    r'stripe\.com/3ds', r'm\.stripe\.network', r'hooks\.stripe\.com/3ds',
    r'paddle_frame', r'paddlejs', r'secure\.paddle\.com', r'buy\.paddle\.com',
    r'idcheck', r'garanti\.com\.tr', r'adyen\.com/hpp', r'adyen\.com/checkout',
    r'adyenpayments\.com/3ds', r'auth\.razorpay\.com', r'razorpay\.com/3ds',
    r'secure\.razorpay\.com', r'3ds\.braintreegateway\.com', r'verify\.3ds',
    r'checkout\.com/3ds', r'checkout\.com/challenge', r'3ds\.paypal\.com',
    r'authentication\.klarna\.com', r'secure\.klarna\.com/3ds'
]]

GATEWAY_KEYWORDS = {
    "stripe": [re.compile(pattern, re.IGNORECASE) for pattern in [
        r'stripe\.com', r'api\.stripe\.com/v1', r'js\.stripe\.com', r'stripe\.js', r'stripe\.min\.js',
        r'client_secret', r'payment_intent', r'data-stripe', r'stripe-payment-element',
        r'stripe-elements', r'stripe-checkout', r'hooks\.stripe\.com', r'm\.stripe\.network',
        r'stripe__input', r'stripe-card-element', r'stripe-v3ds', r'confirmCardPayment',
        r'createPaymentMethod', r'stripePublicKey', r'stripe\.handleCardAction',
        r'elements\.create', r'js\.stripe\.com/v3/hcaptcha-invisible', r'js\.stripe\.com/v3',
        r'stripe\.createToken', r'stripe-payment-request', r'stripe__frame',
        r'api\.stripe\.com/v1/payment_methods', r'js\.stripe\.com', r'api\.stripe\.com/v1/tokens',
        r'stripe\.com/docs', r'checkout\.stripe\.com', r'stripe-js', r'stripe-redirect',
        r'stripe-payment', r'stripe\.network', r'stripe-checkout\.js'
    ]],
    "paypal": [re.compile(pattern, re.IGNORECASE) for pattern in [
        r'api\.paypal\.com', r'paypal\.com', r'paypal-sdk\.com', r'paypal\.js', r'paypalobjects\.com',
        r'paypal_express_checkout', r'e\.PAYPAL_EXPRESS_CHECKOUT', r'paypal-button',
        r'paypal-checkout-sdk', r'paypal-sdk\.js', r'paypal-smart-button', r'paypal_express_checkout/api',
        r'paypal-rest-sdk', r'paypal-transaction', r'itch\.io/api-transaction/paypal',
        r'PayPal\.Buttons', r'paypal\.Buttons', r'data-paypal-client-id', r'paypal\.com/sdk/js',
        r'paypal\.Order\.create', r'paypal-checkout-component', r'api-m\.paypal\.com', r'paypal-funding',
        r'paypal-hosted-fields', r'paypal-transaction-id', r'paypal\.me', r'paypal\.com/v2/checkout',
        r'paypal-checkout', r'paypal\.com/api', r'sdk\.paypal\.com', r'gotopaypalexpresscheckout'
    ]],
    "braintree": [re.compile(pattern, re.IGNORECASE) for pattern in [
        r'api\.braintreegateway\.com/v1', r'braintreepayments\.com', r'js\.braintreegateway\.com',
        r'client_token', r'braintree\.js', r'braintree-hosted-fields', r'braintree-dropin', r'braintree-v3',
        r'braintree-client', r'braintree-data-collector', r'braintree-payment-form', r'braintree-3ds-verify',
        r'client\.create', r'braintree\.min\.js', r'assets\.braintreegateway\.com', r'braintree\.setup',
        r'data-braintree', r'braintree\.tokenize', r'braintree-dropin-ui', r'braintree\.com'
    ]],
    "adyen": [re.compile(pattern, re.IGNORECASE) for pattern in [
        r'checkoutshopper-live\.adyen\.com', r'adyen\.com/hpp', r'adyen\.js', r'data-adyen',
        r'adyen-checkout', r'adyen-payment', r'adyen-components', r'adyen-encrypted-data',
        r'adyen-cse', r'adyen-dropin', r'adyen-web-checkout', r'live\.adyen-services\.com',
        r'adyen\.encrypt', r'checkoutshopper-test\.adyen\.com', r'adyen-checkout__component',
        r'adyen\.com/v1', r'adyen-payment-method', r'adyen-action', r'adyen\.min\.js', r'adyen\.com'
    ]]
}

NON_HTML_EXTENSIONS = {'.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.woff', '.woff2', '.ttf', '.eot', '.mp4', '.mp3', '.pdf', '.icon', '.img'}

SKIP_DOMAINS = {'help.ko-fi.com', 'static.cloudflareinsights.com', 'twitter.com', 'facebook.com', 'youtube.com', 'https://facebook.com', 'https://googlemanager.com', 'https://static.klaviyo.com', 'static.klaviyo.com', 'https://content-autofill.googleapis.com', 'content-autofill.googleapis.com', 'https://www.google.com', 'https://googleads.g.doubleclick.net', 'googleads.g.doubleclick.net', 'https://www.googletagmanager.com', 'googletagmanager.com', 'https://www.googleadservices.com', 'googleadservices.com', 'https://fonts.googleapis.com', 'fonts.googleapis.com', 'http://clients2.google.com', 'clients2.google.com', 'https://analytics.google.com', 'hanalytics.google.com'}

PAYMENT_GATEWAY_DOMAINS = [
    'paypal.com', 'stripe.com', 'braintreegateway.com', 'adyen.com', 'authorize.net',
    'squareup.com', 'klarna.com', 'checkout.com', 'razorpay.com', 'paytm.in',
    'shopify.com', 'worldpay.com', '2co.com', 'amazon.com', 'apple.com', 'google.com',
    'mollie.com', 'opayo.eu', 'paddle.com'
]

GRAPHQL_KEYWORDS = [re.compile(pattern, re.IGNORECASE) for pattern in [
    r'graphql', r'/graphql', r'query\s*{', r'mutation\s*{', r'subscription\s*{',
    r'graphql\.js', r'graphql-endpoint', r'graphql-api', r'graphql-query'
]]

CLOUDFLARE_KEYWORDS = [re.compile(pattern, re.IGNORECASE) for pattern in [
    r'cloudflare', r'cf-ray', r'__cf_chl_', r'cf_clearance', r'challenges\.cloudflare\.com',
    r'cloudflare\.com', r'cf-turnstile-response', r'cf_captcha_kind', r'checking your browser',
    r'cloudflare-nginx', r'cf-challenge'
]]

BUTTON_KEYWORDS = [
    "shop", "buy", "subscribe", "shop now", "buy now", "add to cart", "pay now",
    "checkout", "purchase", "order now", "proceed to payment", "pay", "place order",
    "complete purchase", "make payment", "confirm purchase", "add to bag", "get now"
]

# FastAPI setup
app = FastAPI(title='Payment Gateway Detector API')

class URLRequest(BaseModel):
    url: str

class StealthPaymentDetector:
    def __init__(self):
        self.results = {
            "payment_gateways": [],
            "captchas": [],
            "cloudflare": False,
            "graphql": False,
            "3ds": [],
            "platforms": [],
            "card_types": [],
            "network_requests": [],
            "hidden_payment_data": []
        }
        self.ua = UserAgent()
        self.visited_urls = set()
        self.max_depth = 3
        self.max_urls = 50

    async def analyze_dom(self, page, url):
        'Analyze DOM, iframes, shadow DOM, and hidden elements for payment-related data.'
        try:
            content = await page.content()

            for platform, keyword in PLATFORM_KEYWORDS.items():
                if keyword.lower() in content.lower():
                    if platform not in self.results["platforms"]:
                        self.results["platforms"].append(platform)
                        logger.info(f"Detected platform: {platform}")

            for gateway, patterns in GATEWAY_KEYWORDS.items():
                for pattern in patterns:
                    if pattern.search(content):
                        if gateway not in self.results["payment_gateways"]:
                            self.results["payment_gateways"].append(gateway)
                            logger.info(f"Detected payment gateway: {gateway}")

            for captcha_type, patterns in CAPTCHA_PATTERNS.items():
                for pattern in patterns:
                    if pattern in content.lower():
                        if captcha_type not in self.results["captchas"]:
                            self.results["captchas"].append(captcha_type)
                            logger.info(f"Detected captcha: {captcha_type}")

            for pattern in CLOUDFLARE_KEYWORDS:
                if pattern.search(content):
                    self.results["cloudflare"] = True
                    logger.info("Detected Cloudflare protection")

            for pattern in GRAPHQL_KEYWORDS:
                if pattern.search(content):
                    self.results["graphql"] = True
                    logger.info("Detected GraphQL usage")

            for pattern in THREE_D_SECURE_KEYWORDS:
                if pattern.search(content):
                    self.results["3ds"].append({"url": url, "pattern": pattern.pattern})
                    logger.info(f"Detected 3DS pattern: {pattern.pattern} on {url}")

            for pattern in CARD_KEYWORDS:
                if pattern.search(content):
                    card_type = pattern.pattern.replace(r'\b', '')
                    if card_type not in self.results["card_types"]:
                        self.results["card_types"].append(card_type)
                        logger.info(f"Detected card type: {card_type}")

            hidden_inputs = await page.query_selector_all('input[type="hidden"]')
            for input_elem in hidden_inputs:
                name = await input_elem.get_attribute("name") or ""
                value = await input_elem.get_attribute("value") or ""
                for gateway, patterns in GATEWAY_KEYWORDS.items():
                    for pattern in patterns:
                        if pattern.search(name) or pattern.search(value):
                            self.results["hidden_payment_data"].append({
                                "type": "hidden_input",
                                "name": name,
                                "value": value,
                                "gateway": gateway
                            })
                            logger.info(f"Detected hidden payment data: {name}={value} for {gateway}")

            scripts = await page.query_selector_all("script")
            for script in scripts:
                script_content = await script.inner_html()
                for gateway, patterns in GATEWAY_KEYWORDS.items():
                    for pattern in patterns:
                        if pattern.search(script_content):
                            self.results["hidden_payment_data"].append({
                                "type": "script_content",
                                "content_snippet": script_content[:100],
                                "gateway": gateway
                            })
                            logger.info(f"Detected payment data in script: {gateway}")

            iframes = await page.query_selector_all("iframe")
            for iframe in iframes:
                try:
                    iframe_content = await iframe.content_frame()
                    if iframe_content:
                        iframe_html = await iframe_content.content()
                        for gateway, patterns in GATEWAY_KEYWORDS.items():
                            for pattern in patterns:
                                if pattern.search(iframe_html):
                                    if gateway not in self.results["payment_gateways"]:
                                        self.results["payment_gateways"].append(gateway)
                                        logger.info(f"Detected payment gateway in iframe: {gateway}")
                        for captcha_type, patterns in CAPTCHA_PATTERNS.items():
                            for pattern in patterns:
                                if pattern in iframe_html.lower():
                                    if captcha_type not in self.results["captchas"]:
                                        self.results["captchas"].append(captcha_type)
                                        logger.info(f"Detected captcha in iframe: {captcha_type}")
                except Exception as e:
                    logger.error(f"Error processing iframe: {e}")

            async def traverse_shadow(root):
                try:
                    shadow = await root.evaluate_handle("el => el.shadowRoot")
                    if shadow:
                        shadow_content = await shadow.evaluate("root => root.innerHTML")
                        for gateway, patterns in GATEWAY_KEYWORDS.items():
                            for pattern in patterns:
                                if pattern.search(shadow_content):
                                    if gateway not in self.results["payment_gateways"]:
                                        self.results["payment_gateways"].append(gateway)
                                        logger.info(f"Detected payment gateway in shadow DOM: {gateway}")
                        for captcha_type, patterns in CAPTCHA_PATTERNS.items():
                            for pattern in patterns:
                                if pattern in shadow_content.lower():
                                    if captcha_type not in self.results["captchas"]:
                                        self.results["captchas"].append(captcha_type)
                                        logger.info(f"Detected captcha in shadow DOM: {captcha_type}")
                except:
                    pass

            elements = await page.query_selector_all("*")
            for element in elements:
                await traverse_shadow(element)

        except Exception as e:
            logger.error(f"Error analyzing DOM for {url}: {e}")

    async def interact_with_buttons(self, page, url):
        'Click payment-related buttons to trigger network calls.'
        try:
            buttons = await page.query_selector_all('button, a, input[type="submit"], input[type="button"]')
            for button in buttons:
                text = await button.inner_text() or ""
                text = text.lower().strip()
                if any(keyword in text for keyword in BUTTON_KEYWORDS):
                    logger.info(f"Found payment-related button: {text}")
                    try:
                        # Ensure button is visible and in viewport
                        await button.wait_for_element_state("visible", timeout=5000)
                        await button.scroll_into_view_if_needed(timeout=5000)
                        # Verify button is interactable
                        is_in_viewport = await button.evaluate('(element) => { const rect = element.getBoundingClientRect(); return (rect.top >= 0 && rect.left >= 0 && rect.bottom <= window.innerHeight && rect.right <= window.innerWidth); }')
                        if not is_in_viewport:
                            logger.warning(f"Button '{text}' is not in viewport, skipping")
                            continue
                        # Attempt click with limited retries
                        await button.click(timeout=10000, trial=3)
                        logger.info(f"Clicked button: {text}")
                        await page.wait_for_timeout(2000)
                        await self.analyze_dom(page, url)
                    except Exception as e:
                        logger.error(f"Error clicking button {text}: {e}")
                        continue
        except Exception as e:
            logger.error(f"Error interacting with buttons on {url}: {e}")

    async def capture_network(self, page, url):
        'Capture network requests using Playwright.'
        try:
            def on_request(request):
                req_url = request.url
                if any(keyword in req_url.lower() for keyword in NETWORK_PAYMENT_URL_KEYWORDS) and \
                   not any(ignore in req_url.lower() for ignore in IGNORE_IF_URL_CONTAINS) and \
                   not any(req_url.lower().endswith(ext) for ext in NON_HTML_EXTENSIONS) and \
                   not any(domain in req_url.lower() for domain in SKIP_DOMAINS):
                    self.results["network_requests"].append({
                        "url": req_url,
                        "method": request.method,
                        "resource_type": request.resource_type
                    })
                    logger.info(f"Captured payment-related network request: {req_url}")
                    for gateway in PAYMENT_GATEWAY_DOMAINS:
                        if gateway in req_url.lower():
                            if gateway not in self.results["payment_gateways"]:
                                self.results["payment_gateways"].append(gateway)
                                logger.info(f"Detected payment gateway via network: {gateway}")
                    for pattern in THREE_D_SECURE_KEYWORDS:
                        if pattern.search(req_url):
                            self.results["3ds"].append({"url": req_url, "pattern": pattern.pattern})
                            logger.info(f"Detected 3DS network request: {req_url}")
                    for pattern in GRAPHQL_KEYWORDS:
                        if pattern.search(req_url):
                            self.results["graphql"] = True
                            logger.info(f"Detected GraphQL network request: {req_url}")

            page.on("request", on_request)
        except Exception as e:
            logger.error(f"Error capturing network requests for {url}: {e}")

    def selenium_network_analysis(self, url):
        'Use Selenium Wire to capture and analyze network calls.'
        try:
            options = webdriver.ChromeOptions()
            options.add_argument(f'user-agent={self.ua.random}')
            options.add_argument('--headless')
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--ignore-certificate-errors')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option('excludeSwitches', ['enable-automation'])
            options.add_experimental_option('useAutomationExtension', False)

            # Optional: Add proxy support for better Cloudflare bypass
            proxy = {
                "http": os.getenv("HTTP_PROXY", ""),
                "https": os.getenv("HTTPS_PROXY", ""),
                "no_proxy": "localhost,127.0.0.1"
            }
            seleniumwire_options = {"proxy": proxy if proxy["http"] else {}}
            seleniumwire_options["connection_timeout"] = 10
            driver = webdriver.Chrome(options=options, seleniumwire_options=seleniumwire_options)

            driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": self.ua.random})
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': 'Object.defineProperty(navigator, "webdriver", { get: () => undefined })'
            })

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    driver.get(url)
                    time.sleep(3)
                    break
                except Exception as e:
                    logger.error(f"Retry {attempt + 1}/{max_retries} failed for driver.get({url}): {e}")
                    if attempt == max_retries - 1:
                        logger.error(f"Max retries reached for {url}, skipping Selenium analysis")
                        return
                    time.sleep(2)

            buttons = driver.find_elements(By.CSS_SELECTOR, 'button, a, input[type="submit"], input[type="button"]')
            for button in buttons:
                text = button.text.lower().strip()
                if any(keyword in text for keyword in BUTTON_KEYWORDS):
                    logger.info(f"Selenium found payment-related button: {text}")
                    try:
                        button.click()
                        logger.info(f"Selenium clicked button: {text}")
                        time.sleep(2)
                    except Exception as e:
                        logger.error(f"Selenium error clicking button {text}: {e}")

            for request in driver.requests:
                req_url = request.url
                if any(keyword in req_url.lower() for keyword in NETWORK_PAYMENT_URL_KEYWORDS) and \
                   not any(ignore in req_url.lower() for ignore in IGNORE_IF_URL_CONTAINS) and \
                   not any(req_url.lower().endswith(ext) for ext in NON_HTML_EXTENSIONS) and \
                   not any(domain in req_url.lower() for domain in SKIP_DOMAINS):
                    self.results["network_requests"].append({
                        "url": req_url,
                        "method": request.method,
                        "status": request.response.status_code if request.response else None
                    })
                    logger.info(f"Selenium captured payment-related network request: {req_url}")
                    for gateway in PAYMENT_GATEWAY_DOMAINS:
                        if gateway in req_url.lower():
                            if gateway not in self.results["payment_gateways"]:
                                self.results["payment_gateways"].append(gateway)
                                logger.info(f"Selenium detected payment gateway: {gateway}")
                    for pattern in THREE_D_SECURE_KEYWORDS:
                        if pattern.search(req_url):
                            self.results["3ds"].append({"url": req_url, "pattern": pattern.pattern})
                            logger.info(f"Selenium detected 3DS network request: {req_url}")
                    for pattern in GRAPHQL_KEYWORDS:
                        if pattern.search(req_url):
                            self.results["graphql"] = True
                            logger.info(f"Selenium detected GraphQL network request: {req_url}")
                    for pattern in CLOUDFLARE_KEYWORDS:
                        if pattern.search(req_url):
                            self.results["cloudflare"] = True
                            logger.info(f"Selenium detected Cloudflare: {req_url}")

            driver.quit()
        except Exception as e:
            logger.error(f"Error in Selenium network analysis for {url}: {e}")

    async def crawl(self, url, depth=0):
        'Crawl the website using Playwright with stealth configurations.'
        if depth > self.max_depth or len(self.visited_urls) >= self.max_urls:
            return

        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True, args=[
                    '--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas', '--no-first-run', '--no-zygote', '--disable-gpu'
                ])
                
                context = await browser.new_context(
                    user_agent=self.ua.random,
                    viewport={'width': random.randint(1280, 1920), 'height': random.randint(720, 1080)},
                    java_script_enabled=True,
                    bypass_csp=True,
                    locale='en-US',
                    timezone_id='America/New_York'
                )

                await context.add_init_script('Object.defineProperty(navigator, "webdriver", { get: () => undefined }); Object.defineProperty(navigator, "languages", { get: () => ["en-US", "en"] }); Object.defineProperty(navigator, "plugins", { get: () => [1, 2, 3] }); window.chrome = { runtime: {} }; Object.defineProperty(navigator, "platform", { get: () => "Win32" });')

                page = await context.new_page()

                await self.capture_network(page, url)

                response = await page.goto(url, wait_until="networkidle", timeout=30000)
                if not response or response.status >= 400:
                    logger.warning(f"Failed to load {url}: Status {response.status if response else 'unknown'}")
                    await browser.close()
                    return

                await self.analyze_dom(page, url)
                await self.interact_with_buttons(page, url)

                links = await page.query_selector_all("a[href]")
                hrefs = []
                for link in links:
                    href = await link.get_attribute("href")
                    if href and (href.startswith("http") or href.startswith("/")):
                        parsed = urlparse(href)
                        if not parsed.scheme:
                            href = f"{urlparse(url).scheme}://{urlparse(url).netloc}{href}"
                        if any(keyword in href.lower() for keyword in NETWORK_PAYMENT_URL_KEYWORDS) and \
                           not any(ignore in href.lower() for ignore in IGNORE_IF_URL_CONTAINS) and \
                           href not in self.visited_urls:
                            hrefs.append(href)

                self.visited_urls.add(url)
                logger.info(f"Crawled {url}, found {len(hrefs)} payment-related links")

                for href in hrefs[:5]:
                    if href not in self.visited_urls:
                        await self.crawl(href, depth + 1)

                await browser.close()

            except Exception as e:
                logger.error(f"Error crawling {url}: {e}")

    async def run(self, url):
        'Run the detector and return results.'
        self.results = {
            "payment_gateways": [],
            "captchas": [],
            "cloudflare": False,
            "graphql": False,
            "3ds": [],
            "platforms": [],
            "card_types": [],
            "network_requests": [],
            "hidden_payment_data": []
        }
        self.visited_urls = set()

        await self.crawl(url)
        self.selenium_network_analysis(url)

        return self.results

@app.get("/gateway")
async def detect_payment_gateway(url: str):
    'API endpoint to detect payment gateways for a given URL.'
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")
    
    detector = StealthPaymentDetector()
    try:
        results = await detector.run(url)
        return results
    except Exception as e:
        logger.error(f"Error processing URL {url}: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing URL: {str(e)}")
