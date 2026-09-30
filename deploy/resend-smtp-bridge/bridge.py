"""Resend-API -> SMTP bridge for self-hosted OpenStatus.

OpenStatus sends every email through the Resend SDK, which honours RESEND_BASE_URL.
Point RESEND_BASE_URL at this service and it accepts the two calls OpenStatus makes
(POST /emails, POST /emails/batch) and delivers them through your own SMTP server.

The hard-coded OpenStatus sender (notifications@notifications.openstatus.dev) is
rewritten to SMTP_FROM_ADDRESS so your server accepts it and SPF/DKIM align; the
display name (e.g. the status page title) is kept unless SMTP_FROM_NAME is set.

Stdlib only. Env:
  BRIDGE_TOKEN        required bearer token (use the same value as RESEND_API_KEY)
  SMTP_HOST, SMTP_PORT (465), SMTP_SECURITY (ssl | starttls | none)
  SMTP_USER, SMTP_PASSWORD
  SMTP_FROM_ADDRESS   required, e.g. status@jwero.com
  SMTP_FROM_NAME      optional display-name override
  SMTP_REPLY_TO       optional; replaces OpenStatus's own reply-to (ping@openstatus.dev)
  PORT                listen port (8025)
"""
import base64
import json
import os
import smtplib
import ssl
import sys
import uuid
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parseaddr
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = os.environ.get("BRIDGE_TOKEN", "")
HOST = os.environ.get("SMTP_HOST", "")
PORT = int(os.environ.get("SMTP_PORT", "465"))
SECURITY = os.environ.get("SMTP_SECURITY", "ssl").lower()
USER = os.environ.get("SMTP_USER", "")
PASSWORD = os.environ.get("SMTP_PASSWORD", "")
FROM_ADDRESS = os.environ.get("SMTP_FROM_ADDRESS", "")
FROM_NAME = os.environ.get("SMTP_FROM_NAME", "")
REPLY_TO = os.environ.get("SMTP_REPLY_TO", "")


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def as_list(value):
    if not value:
        return []
    return [value] if isinstance(value, str) else list(value)


def build_message(payload):
    name, _ = parseaddr(payload.get("from") or "")
    msg = EmailMessage()
    msg["From"] = formataddr((FROM_NAME or name or "Status", FROM_ADDRESS))
    to, cc, bcc = as_list(payload.get("to")), as_list(payload.get("cc")), as_list(payload.get("bcc"))
    if not to:
        raise ValueError("`to` is required")
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    # OpenStatus hard-codes its own support inbox as reply-to; never send replies there.
    reply_to = [r for r in as_list(payload.get("reply_to") or payload.get("replyTo"))
                if not parseaddr(r)[1].lower().endswith("openstatus.dev")]
    if REPLY_TO:
        reply_to = [REPLY_TO]
    if reply_to:
        msg["Reply-To"] = ", ".join(reply_to)
    msg["Subject"] = payload.get("subject") or ""
    msg["Message-ID"] = make_msgid(domain=FROM_ADDRESS.split("@")[-1] or None)
    for key, value in (payload.get("headers") or {}).items():
        if key.lower() not in {"from", "to", "cc", "bcc", "subject", "message-id"}:
            msg[key] = str(value)
    text, html = payload.get("text"), payload.get("html")
    msg.set_content(text or "This message requires an HTML-capable mail client.")
    if html:
        msg.add_alternative(html, subtype="html")
    for att in payload.get("attachments") or []:
        content = att.get("content")
        if content is None:
            continue
        data = base64.b64decode(content) if isinstance(content, str) else bytes(content)
        maintype, _, subtype = (att.get("content_type") or "application/octet-stream").partition("/")
        msg.add_attachment(data, maintype=maintype, subtype=subtype or "octet-stream", filename=att.get("filename"))
    return msg, to + cc + bcc


def send(messages):
    """Deliver a list of (EmailMessage, recipients) over one SMTP session."""
    if SECURITY == "ssl":
        smtp = smtplib.SMTP_SSL(HOST, PORT, timeout=30, context=ssl.create_default_context())
    else:
        smtp = smtplib.SMTP(HOST, PORT, timeout=30)
        if SECURITY == "starttls":
            smtp.starttls(context=ssl.create_default_context())
    try:
        if USER:
            smtp.login(USER, PASSWORD)
        for msg, rcpts in messages:
            smtp.send_message(msg, from_addr=FROM_ADDRESS, to_addrs=rcpts)
    finally:
        try:
            smtp.quit()
        except Exception:
            pass


class Handler(BaseHTTPRequestHandler):
    def _reply(self, code, body):
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _error(self, code, name, message):
        self._reply(code, {"statusCode": code, "name": name, "message": message})

    def do_GET(self):
        if self.path == "/health":
            ok = bool(HOST and FROM_ADDRESS)
            return self._reply(200 if ok else 503, {"ok": ok})
        self._error(404, "not_found", "Not found")

    def do_POST(self):
        if TOKEN and self.headers.get("Authorization") != f"Bearer {TOKEN}":
            return self._error(401, "missing_api_key", "Invalid bridge token")
        if not (HOST and FROM_ADDRESS):
            return self._error(500, "application_error", "Bridge not configured: SMTP_HOST / SMTP_FROM_ADDRESS")
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"null")
        except ValueError:
            return self._error(422, "validation_error", "Body must be JSON")
        path = self.path.split("?")[0]
        if path not in ("/emails", "/emails/batch"):
            return self._error(404, "not_found", f"Unsupported endpoint {path}")
        items = payload if path == "/emails/batch" else [payload]
        if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
            return self._error(422, "validation_error", "Unexpected body shape")
        try:
            built = [build_message(i) for i in items]
        except ValueError as e:
            return self._error(422, "validation_error", str(e))
        try:
            send(built)
        except Exception as e:  # SMTP auth/connection/recipient errors
            log(f"smtp error: {type(e).__name__}: {e}")
            return self._error(500, "application_error", f"SMTP delivery failed: {type(e).__name__}")
        ids = [str(uuid.uuid4()) for _ in built]
        for (msg, rcpts), i in zip(built, ids):
            log(f"sent {i} to {len(rcpts)} recipient(s): {msg['Subject']!r}")
        return self._reply(200, {"data": [{"id": i} for i in ids]} if path == "/emails/batch" else {"id": ids[0]})

    def log_message(self, fmt, *args):  # keep request logs quiet; delivery is logged above
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8025"))
    log(f"resend-smtp-bridge listening on :{port} -> {HOST}:{PORT} ({SECURITY}) as {FROM_ADDRESS or '<unset>'}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
