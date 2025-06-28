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
    '/checkout', '/payment', '/pay', '/setup_intent', '/authorize_payment', '/intent',
    '/confirm', '/charge', '/authorize', '/submit_payment', '/create_order',
    '/payment_intent', '/process_payment', '/transaction', '/confirm_payment',
    '/capture', '/payment-method', '/billing', '/invoice', '/order/submit',
    '/tokenize', '/session', '/execute-payment', '/complete', '/pricing', '/subscribe'
]

IGNORE_IF_URL_CONTAINS = ['logout', 'login', 'signup', 'signout', 'account', 'profile']

NON_HTML_EXTENSIONS = ['.css', '.js', '.jpg', '.jpeg', '.png', '.gif', '.svg', '.woff', '.woff2', '.ttf', '.eot']

SKIP_DOMAINS = [
    'google-analytics.com', 'googletagmanager.com', 'facebook.com', 'twitter.com',
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
    'mollie.com', 'opayo.eu', 'paddle.com', 'chargebee.com', 'recurly.com', 'fastspring.com'
]

GATEWAY_KEYWORDS = {
    'stripe': [re.compile(pattern, re.IGNORECASE) for pattern in [
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
    'paypal': [re.compile(pattern, re.IGNORECASE) for pattern in [
        r'api\.paypal\.com', r'paypal\.com', r'paypal-sdk\.com', r'paypal\.js', r'paypalobjects\.com',
        r'paypal_express_checkout', r'e\.PAYPAL_EXPRESS_CHECKOUT', r'paypal-button',
        r'paypal-checkout-sdk', r'paypal-sdk\.js', r'paypal-smart-button', r'paypal_express_checkout/api',
        r'paypal-rest-sdk', r'paypal-transaction', r'itch\.io/api-transaction/paypal',
        r'PayPal\.Buttons', r'paypal\.Buttons', r'data-paypal-client-id', r'paypal\.com/sdk/js',
        r'paypal\.Order\.create', r'paypal-checkout-component', r'api-m\.paypal\.com', r'paypal-funding',
        r'paypal-hosted-fields', r'paypal-transaction-id', r'paypal\.me', r'paypal\.com/v2/checkout',
        r'paypal-checkout', r'paypal\.com/api', r'sdk\.paypal\.com', r'gotopaypalexpresscheckout'
    ]],
    'braintree': [re.compile(pattern, re.IGNORECASE) for pattern in [
        r'api\.braintreegateway\.com/v1', r'braintreepayments\.com', r'js\.braintreegateway\.com',
        r'client_token', r'braintree\.js', r'braintree-hosted-fields', r'braintree-dropin', r'braintree-v3',
        r'braintree-client', r'braintree-data-collector', r'braintree-payment-form', r'braintree-3ds-verify',
        r'client\.create', r'braintree\.min\.js', r'assets\.braintreegateway\.com', r'braintree\.setup',
        r'data-braintree', r'braintree\.tokenize', r'braintree-dropin-ui', r'braintree\.com'
    ]],
    'adyen': [re.compile(pattern, re.IGNORECASE) for pattern in [
        r'checkoutshopper-live\.adyen\.com', r'adyen\.com/hpp', r'adyen\.js', r'data-adyen',
        r'adyen-checkout', r'adyen-payment', r'adyen-components', r'adyen-encrypted-data',
        r'adyen-cse', r'adyen-dropin', r'adyen-web-checkout', r'live\.adyen-services\.com',
        r'adyen\.encrypt', r'checkoutshopper-test\.adyen\.com', r'adyen-checkout__component',
        r'adyen\.com/v1', r'adyen-payment-method', r'adyen-action', r'adyen\.min\.js', r'adyen\.com'
    ]],
    'paddle': [re.compile(pattern, re.IGNORECASE) for pattern in [
        r'paddle\.com', r'api\.paddle\.com', r'checkout\.paddle\.com', r'paddlejs',
        r'paddle\.js', r'paddle-checkout', r'data-paddle', r'Paddle\.Setup',
        r'paddle-checkout-sdk', r'secure\.paddle\.com', r'paddle\.min\.js',
        r'paddle-billing', r'paddle-payment', r'paddle-subscription'
    ]],
    'chargebee': [re.compile(pattern, re.IGNORECASE) for pattern in [
        r'chargebee\.com', r'api\.chargebee\.com', r'js\.chargebee\.com',
        r'chargebee\.js', r'data-cb', r'chargebee-checkout', r'cb-checkout',
        r'chargebee-payment', r'chargebee-portal', r'chargebee-subscription',
        r'chargebee\.min\.js', r'cb\.init', r'chargebee-hosted'
    ]],
    'recurly': [re.compile(pattern, re.IGNORECASE) for pattern in [
        r'recurly\.com', r'api\.recurly\.com', r'js\.recurly\.com',
        r'recurly\.js', r'data-recurly', r'recurly-checkout', r'recurly-payment',
        r'recurly-subscription', r'recurly\.min\.js', r'recurly\.configure'
    ]],
    'fastspring': [re.compile(pattern, re.IGNORECASE) for pattern in [
        r'fastspring\.com', r'api\.fastspring\.com', r'fastspring\.js',
        r'fastspring-checkout', r'data-fastspring', r'fastspring\.min\.js',
        r'fastspring\.storefront', r'fastspring\.builder'
    ]]
}

CAPTCHA_PATTERNS = {
    'recaptcha': ['recaptcha', 'g-recaptcha', 'recaptcha/api.js', 'recaptcha/enterprise.js'],
    'hcaptcha': ['hcaptcha', 'hcaptcha.com', 'hcaptcha-checkbox', 'hcaptcha-invisible'],
    'cloudflare': ['cf-turnstile', 'cloudflare/turnstile', 'challenge-platform'],
    'arkose': ['arkoselabs', 'funcaptcha', 'arkose.js'],
    'datadome': ['datadome', 'datadome.co', 'captcha-endpoint']
}

CLOUDFLARE_KEYWORDS = [re.compile(pattern, re.IGNORECASE) for pattern in [
    r'cloudflare\.com', r'cf-turnstile', r'challenge-platform', r'cf_captcha', r'cf_clearance',
    r'cloudflare/turnstile', r'cf_challenge', r'cloudflareinsights\.com'
]]

GRAPHQL_KEYWORDS = [re.compile(pattern, re.IGNORECASE) for pattern in [
    r'/graphql', r'graphql\.', r'query \{', r'mutation \{', r'graphql-endpoint',
    r'graphql-api', r'graphql/v1'
]]

THREE_D_SECURE_KEYWORDS = [re.compile(pattern, re.IGNORECASE) for pattern in [
    r'3ds', r'3d-secure', r'3ds2', r'verifiedbyvisa', r'securecode', r'acs\.url',
    r'3dsecure', r'3ds-challenge', r'3ds-auth', r'cardinalcommerce', r'3ds-iframe',
    r'3ds-verify', r'authentication\.3ds', r'3ds\.js'
]]

CARD_KEYWORDS = [re.compile(r'\b' + card_type + r'\b', re.IGNORECASE) for card_type in [
    'visa', 'mastercard', 'amex', 'american express', 'discover', 'diners club', 'jcb'
]]

BUTTON_KEYWORDS = ['pay', 'checkout', 'subscribe', 'purchase', 'buy', 'order', 'upgrade', 'billing', 'payment']

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
                if any(keyword in req_url.lower() for keyword in NETWORK_PAYMENT_URL_KEYWORDS) and \
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
                    if pattern in content.lower():
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
                            if pattern in iframe_html.lower():
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
                text = await button.inner_text() or ''
                text = text.lower().strip()
                if any(keyword in text for keyword in BUTTON_KEYWORDS):
                    logger.info(f'Found payment-related button: {text}')
                    try:
                        await button.wait_for_element_state('visible', timeout=10000)
                        await button.scroll_into_view_if_needed(timeout=10000)
                        is_in_viewport = await button.evaluate('(element) => { const rect = element.getBoundingClientRect(); return (rect.top >= -100 && rect.left >= -100 && rect.bottom <= window.innerHeight + 100 && rect.right <= window.innerWidth + 100); }')
                        if not is_in_viewport:
                            logger.warning(f'Button "{text}" is not fully in viewport, skipping: {await button.evaluate("el => JSON.stringify(el.getBoundingClientRect())")}')
                            continue
                        await button.click(timeout=10000, trial=3, force=True)
                        logger.info(f'Clicked button: {text}')
                        await page.wait_for_timeout(5000)
                        await self.analyze_dom(page, url)
                    except Exception as e:
                        logger.error(f'Error clicking button {text}: {e}')
                        continue
                else:
                    logger.debug(f'Button skipped, no payment keywords in text: {text}')
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
                    has_payment_indicators = any(keyword in url.lower() for keyword in NETWORK_PAYMENT_URL_KEYWORDS)
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
                if any(keyword in req_url.lower() for keyword in NETWORK_PAYMENT_URL_KEYWORDS) and \
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

                has_payment_indicators = any(keyword in url.lower() for keyword in NETWORK_PAYMENT_URL_KEYWORDS)
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
                        if any(keyword in href.lower() for keyword in NETWORK_PAYMENT_URL_KEYWORDS) and \
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
