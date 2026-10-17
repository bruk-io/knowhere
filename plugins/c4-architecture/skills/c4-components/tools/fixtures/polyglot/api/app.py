from fastapi import FastAPI
app = FastAPI()

@app.get("/health")
def health():
    return {"ok": True}

class PaymentsViewSet(ViewSet):
    pass

@shared_task
def send_receipt():
    pass
