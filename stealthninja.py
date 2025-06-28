import logging
import random
import re
import os
import time
import asyncio
from urllib.parse import urlparse, urljoin
from playwright.async_api import async_playwright
from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.common.by import By
from seleniumwire import webdriver
from fake_useragent import UserAgent

# Configure logging with DEBUG level
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global constants
NETWORK_PAYMENT_URL_KEYWORDS = [
    re.compile(rf"\b{kw}\b", re.IGNORECASE)
    for kw in [
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
        "/giftcard", "/topup", "/plans", "/buynow", "/sell", "/sell-now", "/purchase-now",
        "/shopnow", "/shopping", "/menu",
        "/sale", "/vps", "/server",
        "/cart-items", "/buy-secure", "/cart-page", "/checkout-page",
        "/order-summary", "/payment-form", "/purchase-flow", "/shop-cart", "/ecommerce", "/store-cart",
        "/buy-button", "/purchase-button", "/add-item", "/remove-item", "/cart-update",
        "/apply-coupon", "/redeem-code", "/discount-code", "/promo-code", "/gift-card", "/pay-with",
        "/payment-options", "/express-checkout", "/quick-buy", "/one-click-buy", "/instant-purchase"
    ]
]

IGNORE_IF_URL_CONTAINS = [
    # Common asset/content folders
    "wp-content", "wp-includes", "skin/frontend", "/assets/", "/themes/", "/static/", "/media/", "/images/", "/img/",

    "https://facebook.com", "https://googlemanager.com", "https://static.klaviyo.com", "static.klaviyo.com", "https://content-autofill.googleapis.com",
    "content-autofill.googleapis.com", "https://www.google.com", "https://googleads.g.doubleclick.net", "googleads.g.doubleclick.net", "googleads.g.doubleclick.net",
    "https://www.googletagmanager.com", "googletagmanager.com", "https://www.googleadservices.com", "googleadservices.com", "https://fonts.googleapis.com",
    "fonts.googleapis.com", "http://clients2.google.com", "clients2.google.com", "https://analytics.google.com", "hanalytics.google.com",
    
    # Analytics & marketing scripts
    "googleapis", "gstatic", "googletagmanager", "google-analytics", "analytics", "doubleclick.net", 
    "facebook.net", "fbcdn", "pixel.", "tiktokcdn", "matomo", "segment.io", "clarity.ms", "mouseflow", "hotjar", 
    
    # Fonts, icons, visual only
    "fonts.", "fontawesome", ".woff", ".woff2", ".ttf", ".eot", ".otf", ".ico", ".svg",
    
    # CDN & framework scripts
    "cdn.jsdelivr.net", "cloudflareinsights.com", "cdnjs", "bootstrapcdn", "polyfill.io", 
    "jsdelivr.net", "unpkg.com", "yastatic.net", "akamai", "fastly", "usercentrics.eu", "app.usercentrics.eu",
    
    # Media, tracking images
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".svg", ".ico", 
    
    # Useless scripts/styles
    ".css", ".scss", ".less", ".map", ".js", "main.js", "bundle.js", "common.js", "theme.js", "style.css", "custom.css",

    # Other non-payment known paths
    "/favicon", "/robots.txt", "/sitemap", "/manifest", "/rss", "/feed", "/help", "/support", "/about", "/terms", "/privacy",
]

NON_HTML_EXTENSIONS = ['.css', '.js', '.jpg', '.jpeg', '.png', '.gif', '.svg', '.woff', '.woff2', '.ttf', '.eot']

SKIP_DOMAINS = [
    'google-analytics.com', 'googletagmanager.com', 'facebook.com', 'twitter.com', 'usercentrics.eu', app.usercentrics.eu',
    'doubleclick.net', 'adservice.google.com', 'cloudflare.com', 'gstatic.com'
]

PLATFORM_KEYWORDS = {
    'shopify': 'shopify',
    'woocommerce': 'woocommerce',
    'magento': 'magento',
    'bigcommerce': 'bigcommerce',
    'squarespace': 'squarespace'
}

PAYMENT_GATEWAY_DOMAINS = [
    'paypal.com', 'stripe.com', 'braintreegateway.com', 'adyen.com', 'authorize.net',
    'squareup.com', 'klarna.com', 'checkout.com', 'razorpay.com', 'paytm.in',
    'shopify.com', 'worldpay.com', '2co.com', 'amazon.com', 'apple.com', 'google.com',
    'mollie.com', 'opayo.eu', 'paddle.com'
]

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
        r'api\.paypal\.com', r'paypal\.com', r'paypal-sdk\.com', r'paypal\.js', r'paypalobjects\.com', r'paypal_express_checkout', r'e\.PAYPAL_EXPRESS_CHECKOUT',
        r'paypal-button', r'paypal-checkout-sdk', r'paypal-sdk\.js', r'paypal-smart-button', r'paypal_express_checkout/api',
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
    ]],
    "authorize.net": [re.compile(pattern, re.IGNORECASE) for pattern in [
        r'authorize\.net/gateway/transact\.dll', r'js\.authorize\.net/v1/Accept\.js', r'js\.authorize\.net',
        r'anet\.js', r'data-authorize', r'authorize-payment', r'apitest\.authorize\.net',
        r'accept\.authorize\.net', r'api\.authorize\.net', r'authorize-hosted-form',
        r'merchantAuthentication', r'data-api-login-id', r'data-client-key', r'Accept\.dispatchData',
        r'api\.authorize\.net/xml/v1', r'accept\.authorize\.net/payment', r'authorize\.net/profile'
    ]],
    "square": [re.compile(pattern, re.IGNORECASE) for pattern in [
        r'squareup\.com', r'js\.squarecdn\.com', r'square\.js', r'data-square', r'square-payment-form',
        r'square-checkout-sdk', r'connect\.squareup\.com', r'square\.min\.js', r'squarecdn\.com',
        r'squareupsandbox\.com', r'sandbox\.web\.squarecdn\.com', r'square-payment-flow', r'square\.card',
        r'squareup\.com/payments', r'data-square-application-id', r'square\.createPayment'
    ]],
    "klarna": [re.compile(pattern, re.IGNORECASE) for pattern in [
        r'klarna\.com', r'js\.klarna\.com', r'klarna\.js', r'data-klarna', r'klarna-checkout',
        r'klarna-onsite-messaging', r'playground\.klarna\.com', r'klarna-payments', r'klarna\.min\.js',
        r'klarna-order-id', r'klarna-checkout-container', r'klarna-load', r'api\.klarna\.com'
    ]],
    "checkout.com": [re.compile(pattern, re.IGNORECASE) for pattern in [
        r'api\.checkout\.com', r'cko\.js', r'data-checkout', r'checkout-sdk', r'checkout-payment',
        r'js\.checkout\.com', r'secure\.checkout\.com', r'checkout\.frames\.js', r'api\.sandbox\.checkout\.com',
        r'cko-payment-token', r'checkout\.init', r'cko-hosted', r'checkout\.com/v2', r'cko-card-token'
    ]],
    "razorpay": [re.compile(pattern, re.IGNORECASE) for pattern in [
        r'checkout\.razorpay\.com', r'razorpay\.js', r'data-razorpay', r'razorpay-checkout',
        r'razorpay-payment-api', r'razorpay-sdk', r'razorpay-payment-button', r'razorpay-order-id',
        r'api\.razorpay\.com', r'razorpay\.min\.js', r'payment_box payment_method_razorpay',
        r'razorpay', r'cdn\.razorpay\.com', r'rzp_payment_icon\.svg', r'razorpay\.checkout',
        r'data-razorpay-key', r'razorpay_payment_id', r'checkout\.razorpay\.com/v1', r'razorpay-hosted'
    ]],
    "paytm": [re.compile(pattern, re.IGNORECASE) for pattern in [
        r'securegw\.paytm\.in', r'api\.paytm\.com', r'paytm\.js', r'data-paytm', r'paytm-checkout',
        r'paytm-payment-sdk', r'paytm-wallet', r'paytm\.allinonesdk', r'securegw-stage\.paytm\.in',
        r'paytm\.min\.js', r'paytm-transaction-id', r'paytm\.invoke', r'paytm-checkout-js',
        r'data-paytm-order-id'
    ]],
    "Shopify Payments": [re.compile(pattern, re.IGNORECASE) for pattern in [
        r'pay\.shopify\.com', r'data-shopify-payments', r'shopify-checkout-sdk', r'shopify-payment-api',
        r'shopify-sdk', r'shopify-express-checkout', r'shopify_payments\.js', r'checkout\.shopify\.com',
        r'shopify-payment-token', r'shopify\.card', r'shopify-checkout-api', r'data-shopify-checkout',
        r'shopify\.com/api'
    ]],
    "worldpay": [re.compile(pattern, re.IGNORECASE) for pattern in [
        r'secure\.worldpay\.com', r'worldpay\.js', r'data-worldpay', r'worldpay-checkout',
        r'worldpay-payment-sdk', r'worldpay-secure', r'secure-test\.worldpay\.com', r'worldpay\.min\.js',
        r'worldpay\.token', r'worldpay-payment-form', r'access\.worldpay\.com', r'worldpay-3ds',
        r'data-worldpay-token'
    ]],
    "2checkout": [re.compile(pattern, re.IGNORECASE) for pattern in [
        r'www\.2checkout\.com', r'2co\.js', r'data-2checkout', r'2checkout-payment', r'secure\.2co\.com',
        r'2checkout-hosted', r'api\.2checkout\.com', r'2co\.min\.js', r'2checkout\.token', r'2co-checkout',
        r'data-2co-seller-id', r'2checkout\.convertplus', r'secure\.2co\.com/v2'
    ]],
    "Amazon pay": [re.compile(pattern, re.IGNORECASE) for pattern in [
        r'payments\.amazon\.com', r'amazonpay\.js', r'data-amazon-pay', r'amazon-pay-button',
        r'amazon-pay-checkout-sdk', r'amazon-pay-wallet', r'amazon-checkout\.js', r'payments\.amazon\.com/v2',
        r'amazon-pay-token', r'amazon-pay-sdk', r'data-amazon-pay-merchant-id', r'amazon-pay-signin',
        r'amazon-pay-checkout-session'
    ]],
    "Apple pay": [re.compile(pattern, re.IGNORECASE) for pattern in [
        r'apple-pay\.js', r'data-apple-pay', r'apple-pay-button', r'apple-pay-checkout-sdk',
        r'apple-pay-session', r'apple-pay-payment-request', r'ApplePaySession', r'apple-pay-merchant-id',
        r'apple-pay-payment', r'apple-pay-sdk', r'data-apple-pay-token', r'apple-pay-checkout',
        r'apple-pay-domain'
    ]],
    "Google pay": [re.compile(pattern, re.IGNORECASE) for pattern in [
        r'pay\.google\.com', r'googlepay\.js', r'data-google-pay', r'google-pay-button',
        r'google-pay-checkout-sdk', r'google-pay-tokenization', r'payments\.googleapis\.com',
        r'google\.payments\.api', r'google-pay-token', r'google-pay-payment-method',
        r'data-google-pay-merchant-id', r'google-pay-checkout', r'google-pay-sdk'
    ]],
    "mollie": [re.compile(pattern, re.IGNORECASE) for pattern in [
        r'api\.mollie\.com', r'mollie\.js', r'data-mollie', r'mollie-checkout', r'mollie-payment-sdk',
        r'mollie-components', r'mollie\.min\.js', r'profile\.mollie\.com', r'mollie-payment-token',
        r'mollie-create-payment', r'data-mollie-profile-id', r'mollie-checkout-form', r'mollie-redirect'
    ]],
    "opayo": [re.compile(pattern, re.IGNORECASE) for pattern in [
        r'live\.opayo\.eu', r'opayo\.js', r'data-opayo', r'opoayo-checkout', r'opayo-payment-sdk',
        r'opayo-form', r'test\.opayo\.eu', r'opayo\.min\.js', r'opayo-payment-token', r'opayo-3ds',
        r'data-opayo-merchant-id', r'opayo-hosted', r'opayo\.api'
    ]],
    "paddle": [re.compile(pattern, re.IGNORECASE) for pattern in [
        r'checkout\.paddle\.com', r'paddle_button\.js', r'paddle\.js', r'data-paddle',
        r'paddle-checkout-sdk', r'paddle-product-id', r'api\.paddle\.com', r'paddle\.min\.js',
        r'paddle-checkout', r'data-paddle-vendor-id', r'paddle\.Checkout\.open', r'paddle-transaction-id',
        r'paddle-hosted'
    ]]
}

# Captcha patterns
CAPTCHA_PATTERNS = {
    "reCaptcha": [
        "g-recaptcha", "recaptcha/api.js", "data-sitekey", "nocaptcha",
        "recaptcha.net", "www.google.com/recaptcha", "grecaptcha.execute",
        "grecaptcha.render", "grecaptcha.ready", "recaptcha-token"
    ],
    "hCaptcha": [
        "hcaptcha", "assets.hcaptcha.com", "hcaptcha.com/1/api.js",
        "data-hcaptcha-sitekey", "js.stripe.com/v3/hcaptcha-invisible", "hcaptcha-invisible", "hcaptcha.execute"
    ],
    "Turnstile": [
        "turnstile", "challenges.cloudflare.com", "cf-turnstile-response",
        "data-sitekey", "__cf_chl_", "cf_clearance"
    ],
    "Arkose Labs": [
        "arkose-labs", "funcaptcha", "client-api.arkoselabs.com",
        "fc-token", "fc-widget", "arkose", "press and hold", "funcaptcha.com"
    ],
    "GeeTest": [
        "geetest", "gt_captcha_obj", "gt.js", "geetest_challenge",
        "geetest_validate", "geetest_seccode"
    ],
    "BotDetect": [
        "botdetectcaptcha", "BotDetect", "BDC_CaptchaImage", "CaptchaCodeTextBox"
    ],
    "KeyCAPTCHA": [
        "keycaptcha", "kc_submit", "kc__widget", "s_kc_cid"
    ],
    "Anti Bot Detection": [
        "fingerprintjs", "js.challenge", "checking your browser",
        "verify you are human", "please enable javascript and cookies",
        "sec-ch-ua-platform"
    ],
    "Captcha": [
        "captcha-container", "captcha-box", "captcha-frame", "captcha_input",
        "id=\"captcha\"", "class=\"captcha\"", "iframe.+?captcha",
        "data-captcha-sitekey"
    ]
}

CLOUDFLARE_KEYWORDS = [re.compile(pattern, re.IGNORECASE) for pattern in [
    r'cloudflare\.com', r'cf-turnstile', r'challenge-platform', r'cf_captcha', r'cf_clearance',
    r'cloudflare/turnstile', r'cf_challenge', r'cloudflareinsights\.com'
]]

GRAPHQL_KEYWORDS = [re.compile(pattern, re.IGNORECASE) for pattern in [
    r'/graphql', r'graphql\.', r'query \{', r'mutation \{', r'graphql-endpoint',
    r'graphql-api', r'graphql/v1'
]]

# 3D Secure keywords (regex)
THREE_D_SECURE_KEYWORDS = [re.compile(pattern, re.IGNORECASE) for pattern in [
    r'three_d_secure', r'3dsecure', r'acs', r'acs_url', r'acsurl', r'redirect',
    r'secure-auth', r'three_d_secure_usage', r'challenge', r'3ds', r'3ds1', r'3ds2', r'tds', r'tdsecure',
    r'3d-secure', r'three-d', r'3dcheck', r'3d-auth', r'three-ds',
    r'stripe\.com/3ds', r'm\.stripe\.network', r'hooks\.stripe\.com/3ds',
    r'paddle_frame', r'paddlejs', r'secure\.paddle\.com', r'buy\.paddle\.com',
    r'idcheck', r'garanti\.com\.tr', r'adyen\.com/hpp', r'adyen\.com/checkout',
    r'adyenpayments\.com/3ds', r'auth\.razorpay\.com', r'razorpay\.com/3ds',
    r'secure\.razorpay\.com', r'3ds\.braintreegateway\.com', r'verify\.3ds',
    r'checkout\.com/3ds', r'checkout\.com/challenge', r'3ds\.paypal\.com',
    r'authentication\.klarna\.com', r'secure\.klarna\.com/3ds'
]]

CARD_KEYWORDS = [re.compile(r'\b' + card_type + r'\b', re.IGNORECASE) for card_type in [
    'visa', 'mastercard', 'amex', 'american express', 'discover', 'diners club', 'jcb'
]]

BUTTON_KEYWORDS = ['pay', 'checkout', 'subscribe', 'purchase', 'buy', 'order', 'upgrade', 'billing', 'payment', 'shop', 'add to cart', 'price']

class StealthPaymentDetector:
    def __init__(self):
        self.ua = UserAgent()
        self.results = {
            'payment_gateways': [],
            'captchas': [],
            'cloudflare': False,
            'graphql': False,
            '3ds': [],
            'platforms': [],
            'card_types': [],
            'network_requests': [],
            'hidden_payment_data': []
        }
        self.visited_urls = set()
        self.max_depth = 1  # Reduced to avoid Cloudflare triggers
        self.max_urls = 10

    async def capture_network(self, page, url):
        'Capture network requests using Playwright.'
        try:
            async def handle_request(request):
                req_url = request.url
                if any(pattern.search(req_url.lower()) for pattern in NETWORK_PAYMENT_URL_KEYWORDS) and \
                   not any(ignore in req_url.lower() for ignore in IGNORE_IF_URL_CONTAINS) and \
                   not any(req_url.lower().endswith(ext) for ext in NON_HTML_EXTENSIONS) and \
                   not any(domain in req_url.lower() for domain in SKIP_DOMAINS):
                    self.results['network_requests'].append({
                        'url': req_url,
                        'method': request.method,
                        'resource_type': request.resource_type
                    })
                    logger.info(f'Playwright captured payment-related network request: {req_url}')
                    for gateway in PAYMENT_GATEWAY_DOMAINS:
                        if gateway in req_url.lower():
                            if gateway not in self.results['payment_gateways']:
                                self.results['payment_gateways'].append(gateway)
                                logger.info(f'Playwright detected payment gateway: {gateway}')
                    for pattern in THREE_D_SECURE_KEYWORDS:
                        if pattern.search(req_url):
                            self.results['3ds'].append({'url': req_url, 'pattern': pattern.pattern})
                            logger.info(f'Playwright detected 3DS network request: {req_url}')
                    for pattern in GRAPHQL_KEYWORDS:
                        if pattern.search(req_url):
                            self.results['graphql'] = True
                            logger.info(f'Playwright detected GraphQL network request: {req_url}')
                    for pattern in CLOUDFLARE_KEYWORDS:
                        if pattern.search(req_url):
                            self.results['cloudflare'] = True
                            logger.info(f'Playwright detected Cloudflare: {req_url}')

            page.on('request', handle_request)
        except Exception as e:
            logger.error(f'Error setting up network capture for {url}: {e}')

    async def analyze_dom(self, page, url):
        'Analyze DOM, iframes, shadow DOM, and hidden elements for payment-related data.'
        try:
            # Wait for potential payment elements to load
            await page.wait_for_timeout(5000)
            try:
                await page.wait_for_selector('[data-stripe], [data-paypal], [data-braintree], [data-adyen], [data-paddle], [data-chargebee], [data-recurly]', timeout=10000)
                logger.info(f'Detected potential payment elements on {url}')
            except:
                logger.debug(f'No payment elements found via selector on {url}')

            content = await page.content()

            for platform, keyword in PLATFORM_KEYWORDS.items():
                if keyword.lower() in content.lower():
                    if platform not in self.results['platforms']:
                        self.results['platforms'].append(platform)
                        logger.info(f'Detected platform: {platform}')

            for gateway, patterns in GATEWAY_KEYWORDS.items():
                for pattern in patterns:
                    if pattern.search(content):
                        if gateway not in self.results['payment_gateways']:
                            self.results['payment_gateways'].append(gateway)
                            logger.info(f'Detected payment gateway: {gateway}')

            for captcha_type, patterns in CAPTCHA_PATTERNS.items():
                for pattern in patterns:
                    if pattern.lower() in content.lower():
                        if captcha_type not in self.results['captchas']:
                            self.results['captchas'].append(captcha_type)
                            logger.info(f'Detected captcha: {captcha_type}')

            for pattern in CLOUDFLARE_KEYWORDS:
                if pattern.search(content):
                    self.results['cloudflare'] = True
                    logger.info('Detected Cloudflare protection')

            for pattern in GRAPHQL_KEYWORDS:
                if pattern.search(content):
                    self.results['graphql'] = True
                    logger.info('Detected GraphQL usage')

            for pattern in THREE_D_SECURE_KEYWORDS:
                if pattern.search(content):
                    self.results['3ds'].append({'url': url, 'pattern': pattern.pattern})
                    logger.info(f'Detected 3DS pattern: {pattern.pattern} on {url}')

            for pattern in CARD_KEYWORDS:
                if pattern.search(content):
                    card_type = pattern.pattern.replace(r'\b', '')
                    if card_type not in self.results['card_types']:
                        self.results['card_types'].append(card_type)
                        logger.info(f'Detected card type: {card_type}')

            hidden_inputs = await page.query_selector_all('input[type="hidden"]')
            for input_elem in hidden_inputs:
                name = await input_elem.get_attribute('name') or ''
                value = await input_elem.get_attribute('value') or ''
                for gateway, patterns in GATEWAY_KEYWORDS.items():
                    for pattern in patterns:
                        if pattern.search(name) or pattern.search(value):
                            self.results['hidden_payment_data'].append({
                                'type': 'hidden_input',
                                'name': name,
                                'value': value,
                                'gateway': gateway
                            })
                            logger.info(f'Detected hidden payment data: {name}={value} for {gateway}')

            scripts = await page.query_selector_all('script')
            for script in scripts:
                script_content = await script.inner_html()
                for gateway, patterns in GATEWAY_KEYWORDS.items():
                    for pattern in patterns:
                        if pattern.search(script_content):
                            self.results['hidden_payment_data'].append({
                                'type': 'script_content',
                                'content_snippet': script_content[:100],
                                'gateway': gateway
                            })
                            logger.info(f'Detected payment data in script: {gateway}')

            async def traverse_iframes(frame, depth=0, max_depth=3):
                if depth > max_depth:
                    return
                try:
                    iframe_html = await frame.content()
                    for gateway, patterns in GATEWAY_KEYWORDS.items():
                        for pattern in patterns:
                            if pattern.search(iframe_html):
                                if gateway not in self.results['payment_gateways']:
                                    self.results['payment_gateways'].append(gateway)
                                    logger.info(f'Detected payment gateway in iframe (depth {depth}): {gateway}')
                    for captcha_type, patterns in CAPTCHA_PATTERNS.items():
                        for pattern in patterns:
                            if pattern.lower() in iframe_html.lower():
                                if captcha_type not in self.results['captchas']:
                                    self.results['captchas'].append(captcha_type)
                                    logger.info(f'Detected captcha in iframe (depth {depth}): {captcha_type}')
                    child_iframes = await frame.query_selector_all('iframe')
                    for child_iframe in child_iframes:
                        child_frame = await child_iframe.content_frame()
                        if child_frame:
                            await traverse_iframes(child_frame, depth + 1, max_depth)
                except Exception as e:
                    logger.error(f'Error processing iframe at depth {depth}: {e}')

            iframes = await page.query_selector_all('iframe')
            for iframe in iframes:
                iframe_content = await iframe.content_frame()
                if iframe_content:
                    await traverse_iframes(iframe_content, depth=0)

            async def traverse_shadow(root, depth=0, max_depth=3):
                if depth > max_depth:
                    return
                try:
                    shadow = await root.evaluate_handle('el => el.shadowRoot')
                    if shadow:
                        shadow_content = await shadow.evaluate('root => root.innerHTML')
                        for gateway, patterns in GATEWAY_KEYWORDS.items():
                            for pattern in patterns:
                                if pattern.search(shadow_content):
                                    if gateway not in self.results['payment_gateways']:
                                        self.results['payment_gateways'].append(gateway)
                                        logger.info(f'Detected payment gateway in shadow DOM (depth {depth}): {gateway}')
                        for captcha_type, patterns in CAPTCHA_PATTERNS.items():
                            for pattern in patterns:
                                if pattern in shadow_content.lower():
                                    if captcha_type not in self.results['captchas']:
                                        self.results['captchas'].append(captcha_type)
                                        logger.info(f'Detected captcha in shadow DOM (depth {depth}): {captcha_type}')
                        shadow_elements = await shadow.evaluate_handle('root => Array.from(root.querySelectorAll("*"))')
                        shadow_elements_list = await shadow_elements.as_element().evaluate('els => els')
                        for shadow_element in shadow_elements_list:
                            await traverse_shadow(shadow_element, depth + 1, max_depth)
                except:
                    pass

            elements = await page.query_selector_all('*')
            for element in elements:
                await traverse_shadow(element, depth=0)

        except Exception as e:
            logger.error(f'Error analyzing DOM for {url}: {e}')

    async def interact_with_buttons(self, page, url):
        'Click payment-related buttons to trigger network calls.'
        try:
            buttons = await page.query_selector_all('button, a, input[type="submit"], input[type="button"]')
            for button in buttons:
                try:
                    text = await button.inner_text(timeout=5000) or ''
                    text = text.lower().strip()
                    attributes = await button.get_attributes(timeout=5000) or {}
                    attr_string = ' '.join(attributes.values()).lower()
                    if any(keyword in text for keyword in BUTTON_KEYWORDS) or \
                    any(keyword in attr_string for keyword in BUTTON_KEYWORDS):
                        logger.info(f'Found payment-related button: {text} (attributes: {attr_string})')
                        await button.click(timeout=5000)  # Click to trigger payment flow
                    else:
                        logger.debug(f'Skipped button, no payment keywords in text: "{text}" or attributes: "{attr_string}"')
                except Exception as e:
                    logger.error(f'Error processing button: {e}')
        except Exception as e:
            logger.error(f'Error interacting with buttons on {url}: {e}')

    def selenium_network_analysis(self, url):
        'Use Selenium Wire to capture and analyze network calls.'
        try:
            options = ChromeOptions()
            options.add_argument(f'user-agent={self.ua.random}')
            options.add_argument('--headless')
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--ignore-certificate-errors')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option('excludeSwitches', ['enable-automation'])
            options.add_experimental_option('useAutomationExtension', False)

            proxy = {
                'http': os.getenv('HTTP_PROXY', ''),
                'https': os.getenv('HTTPS_PROXY', ''),
                'no_proxy': 'localhost,127.0.0.1'
            }
            seleniumwire_options = {'proxy': proxy if proxy['http'] else {}}
            seleniumwire_options['connection_timeout'] = 10
            driver = webdriver.Chrome(options=options, seleniumwire_options=seleniumwire_options)

            driver.execute_cdp_cmd('Network.setUserAgentOverride', {'userAgent': self.ua.random})
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': 'Object.defineProperty(navigator, "webdriver", { get: () => undefined })'
            })

            from selenium.webdriver.common.by import By
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    driver.get(url)
                    time.sleep(5)
                    has_payment_indicators = any(pattern.search(url.lower()) for pattern in NETWORK_PAYMENT_URL_KEYWORDS)
                    if not has_payment_indicators:
                        page_source = driver.page_source.lower()
                        for gateway, patterns in GATEWAY_KEYWORDS.items():
                            for pattern in patterns:
                                if pattern.search(page_source):
                                    has_payment_indicators = True
                                    break
                        if not has_payment_indicators:
                            logger.debug(f'Skipping {url}: no payment-related indicators found')
                            driver.quit()
                            return
                    driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
                    time.sleep(2)
                    logger.info(f'Refreshing {url} to capture fresh network calls')
                    driver.refresh()
                    time.sleep(5)
                    driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
                    time.sleep(2)
                    break
                except Exception as e:
                    logger.error(f'Retry {attempt + 1}/{max_retries} failed for driver.get({url}): {e}')
                    if attempt == max_retries - 1:
                        logger.error(f'Max retries reached for {url}, skipping Selenium analysis')
                        driver.quit()
                        return
                    time.sleep(2)

            buttons = driver.find_elements(By.CSS_SELECTOR, 'button, a, input[type="submit"], input[type="button"]')
            for button in buttons:
                text = button.text.lower().strip()
                if any(keyword in text for keyword in BUTTON_KEYWORDS):
                    logger.info(f'Selenium found payment-related button: {text}')
                    try:
                        driver.execute_script('arguments[0].scrollIntoView(true);', button)
                        time.sleep(1)
                        button.click()
                        logger.info(f'Selenium clicked button: {text}')
                        time.sleep(5)
                    except Exception as e:
                        logger.error(f'Selenium error clicking button {text}: {e}')
                        continue
                else:
                    logger.debug(f'Selenium button skipped, no payment keywords in text: {text}')

            for request in driver.requests:
                req_url = request.url
                if any(pattern.search(req_url.lower()) for pattern in NETWORK_PAYMENT_URL_KEYWORDS) and \
                   not any(ignore in req_url.lower() for ignore in IGNORE_IF_URL_CONTAINS) and \
                   not any(req_url.lower().endswith(ext) for ext in NON_HTML_EXTENSIONS) and \
                   not any(domain in req_url.lower() for domain in SKIP_DOMAINS):
                    self.results['network_requests'].append({
                        'url': req_url,
                        'method': request.method,
                        'status': request.response.status_code if request.response else None
                    })
                    logger.info(f'Selenium captured payment-related network request: {req_url}')
                    for gateway in PAYMENT_GATEWAY_DOMAINS:
                        if gateway in req_url.lower():
                            if gateway not in self.results['payment_gateways']:
                                self.results['payment_gateways'].append(gateway)
                                logger.info(f'Selenium detected payment gateway: {gateway}')
                    for pattern in THREE_D_SECURE_KEYWORDS:
                        if pattern.search(req_url):
                            self.results['3ds'].append({'url': req_url, 'pattern': pattern.pattern})
                            logger.info(f'Selenium detected 3DS network request: {req_url}')
                    for pattern in GRAPHQL_KEYWORDS:
                        if pattern.search(req_url):
                            self.results['graphql'] = True
                            logger.info(f'Selenium detected GraphQL network request: {req_url}')
                    for pattern in CLOUDFLARE_KEYWORDS:
                        if pattern.search(req_url):
                            self.results['cloudflare'] = True
                            logger.info(f'Selenium detected Cloudflare: {req_url}')

            driver.quit()
        except Exception as e:
            logger.error(f'Error in Selenium network analysis for {url}: {e}')

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

                has_payment_indicators = any(pattern.search(url.lower()) for pattern in NETWORK_PAYMENT_URL_KEYWORDS)
                if not has_payment_indicators:
                    try:
                        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                        content = await page.content()
                        for gateway, patterns in GATEWAY_KEYWORDS.items():
                            for pattern in patterns:
                                if pattern.search(content):
                                    has_payment_indicators = True
                                    break
                        iframes = await page.query_selector_all('iframe')
                        for iframe in iframes:
                            iframe_content = await iframe.content_frame()
                            if iframe_content:
                                iframe_html = await iframe_content.content()
                                for gateway, patterns in GATEWAY_KEYWORDS.items():
                                    for pattern in patterns:
                                        if pattern.search(iframe_html):
                                            has_payment_indicators = True
                                            break
                                if has_payment_indicators:
                                    break
                    except Exception as e:
                        logger.debug(f'Error checking payment indicators for {url}: {e}')

                if not has_payment_indicators:
                    logger.debug(f'Skipping {url}: no payment-related indicators found')
                    await browser.close()
                    return

                await self.capture_network(page, url)

                response = await page.goto(url, wait_until='networkidle', timeout=30000)
                if not response or response.status >= 400:
                    logger.warning(f'Failed to load {url}: Status {response.status if response else "unknown"}')
                    await browser.close()
                    return

                await self.analyze_dom(page, url)
                await self.interact_with_buttons(page, url)

                logger.info(f'Refreshing {url} to capture fresh network calls')
                await page.reload(wait_until='networkidle', timeout=30000)
                await self.analyze_dom(page, url)
                await self.interact_with_buttons(page, url)

                links = await page.query_selector_all('a[href]')
                hrefs = []
                for link in links:
                    href = await link.get_attribute('href')
                    if href and (href.startswith('http') or href.startswith('/')):
                        parsed = urlparse(href)
                        if not parsed.scheme:
                            href = urljoin(url, href)
                        if any(pattern.search(href.lower()) for pattern in NETWORK_PAYMENT_URL_KEYWORDS) and \
                           not any(ignore in href.lower() for ignore in IGNORE_IF_URL_CONTAINS) and \
                           href not in self.visited_urls:
                            hrefs.append(href)

                self.visited_urls.add(url)
                logger.info(f'Crawled {url}, found {len(hrefs)} payment-related links')

                for href in hrefs[:5]:
                    if href not in self.visited_urls:
                        await self.crawl(href, depth + 1)

                await browser.close()

            except Exception as e:
                logger.error(f'Error crawling {url}: {e}')

    async def detect_payment_gateway(self, url):
        'Detect payment gateways and related data for the given URL.'
        try:
            self.results = {
                'payment_gateways': [],
                'captchas': [],
                'cloudflare': False,
                'graphql': False,
                '3ds': [],
                'platforms': [],
                'card_types': [],
                'network_requests': [],
                'hidden_payment_data': []
            }
            self.visited_urls = set()
            await self.crawl(url)
            self.selenium_network_analysis(url)
            return self.results
        except Exception as e:
            logger.error(f'Error detecting payment gateway for {url}: {e}')
            return self.results
