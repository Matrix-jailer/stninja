from fastapi import FastAPI
from stealthninja import StealthPaymentDetector

app = FastAPI()

@app.get("/gateway")
async def detect_payment_gateway(url: str):
    detector = StealthPaymentDetector()
    result = await detector.detect_payment_gateway(url)
    return result
