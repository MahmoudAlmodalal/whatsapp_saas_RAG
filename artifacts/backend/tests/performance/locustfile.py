"""
tests/performance/locustfile.py
─────────────────────────────────
Locust load tests for the WhatsApp AI SaaS platform.

Run with:
    locust -f tests/performance/locustfile.py --headless \\
      --users 100 --spawn-rate 10 --run-time 60s \\
      --host http://localhost:8000

Target SLAs:
    - Webhook endpoint: p95 latency < 200ms at 100 RPS
    - Auth login: p95 latency < 500ms
    - Document list: p95 latency < 300ms
"""
import hashlib
import hmac
import json
import random
import time
import uuid
from locust import HttpUser, task, between, events

APP_SECRET = "test-app-secret-67890"
TEST_VERIFY_TOKEN = "test-verify-token"


def _generate_webhook_payload(from_number: str, msg_id: str, text: str) -> tuple[bytes, str]:
    """Generate a signed WhatsApp webhook payload."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "perf_test_entry",
            "changes": [{
                "field": "messages",
                "value": {
                    "metadata": {"phone_number_id": "123456789"},
                    "messages": [{
                        "id": msg_id,
                        "from": from_number,
                        "type": "text",
                        "text": {"body": text},
                        "timestamp": str(int(time.time())),
                    }],
                    "contacts": [{"profile": {"name": "مستخدم اختبار"}}],
                },
            }],
        }],
    }
    raw = json.dumps(payload, ensure_ascii=False).encode()
    signature = "sha256=" + hmac.new(APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return raw, signature


_ARABIC_MESSAGES = [
    "ما هو سعر المنتج؟",
    "كيف يمكنني إرجاع الطلب؟",
    "هل تتوفر منتجات باللون الأزرق؟",
    "ما هي ساعات العمل؟",
    "أريد الاستفسار عن الشحن",
    "هل تقبلون الدفع بالبطاقة؟",
    "متى يصل الطلب؟",
    "أحتاج مساعدة في طلبيتي",
]


class WebhookUser(HttpUser):
    """Simulates incoming WhatsApp webhook traffic."""

    wait_time = between(0.01, 0.05)  # 20-100 RPS per user

    def on_start(self):
        """Each virtual user gets a unique phone number."""
        self.phone = f"+9665{random.randint(10000000, 99999999)}"
        self._msg_counter = 0

    @task(8)
    def send_text_message(self):
        """Primary task: send a text message via webhook."""
        self._msg_counter += 1
        msg_id = f"wamid.perf.{uuid.uuid4().hex}"
        text = random.choice(_ARABIC_MESSAGES)

        payload_bytes, signature = _generate_webhook_payload(
            from_number=self.phone,
            msg_id=msg_id,
            text=text,
        )

        with self.client.post(
            "/api/v1/webhook",
            data=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": signature,
            },
            catch_response=True,
            name="POST /webhook [text]",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 429:
                resp.failure("Rate limited")
            else:
                resp.failure(f"Unexpected status: {resp.status_code}")

    @task(2)
    def send_duplicate_message(self):
        """Test dedup: send same message ID twice (second should be silently ignored)."""
        msg_id = f"wamid.dup.{self.phone}.fixed"
        payload_bytes, signature = _generate_webhook_payload(
            from_number=self.phone,
            msg_id=msg_id,
            text="رسالة مكررة للاختبار",
        )
        headers = {
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
        }
        self.client.post(
            "/api/v1/webhook",
            data=payload_bytes,
            headers=headers,
            name="POST /webhook [duplicate]",
        )
        self.client.post(
            "/api/v1/webhook",
            data=payload_bytes,
            headers=headers,
            name="POST /webhook [duplicate]",
        )


class AdminUser(HttpUser):
    """Simulates dashboard admin users."""

    wait_time = between(1, 3)
    _token: str | None = None

    def on_start(self):
        """Log in once to get a token."""
        resp = self.client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.sa", "password": "s3cret_admin"},
        )
        if resp.status_code == 200:
            self._token = resp.json().get("access_token")

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    @task(5)
    def list_documents(self):
        self.client.get(
            "/api/v1/documents/",
            headers=self._auth_headers(),
            name="GET /documents/",
        )

    @task(3)
    def list_conversations(self):
        self.client.get(
            "/api/v1/conversations/",
            headers=self._auth_headers(),
            name="GET /conversations/",
        )

    @task(2)
    def health_check(self):
        self.client.get("/health", name="GET /health")


class AuthStressUser(HttpUser):
    """Stress-tests the auth endpoints."""

    wait_time = between(0.5, 2)

    @task(3)
    def login_valid(self):
        self.client.post(
            "/api/v1/auth/login",
            json={"email": "agent@test.sa", "password": "s3cret_agent"},
            name="POST /auth/login [valid]",
        )

    @task(1)
    def login_invalid(self):
        self.client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@nothere.com", "password": "wrong"},
            name="POST /auth/login [invalid]",
        )


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("\n🚀 Starting WhatsApp SaaS Load Test")
    print("Target SLAs: Webhook p95 < 200ms | Login p95 < 500ms\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("\n📊 Load test completed. Check Locust report for SLA analysis.\n")
