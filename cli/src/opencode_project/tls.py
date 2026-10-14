from __future__ import annotations

import os
import ssl

import certifi


def create_ssl_context() -> ssl.SSLContext:
    ca_bundle = os.environ.get("SSL_CERT_FILE") or certifi.where()
    return ssl.create_default_context(cafile=ca_bundle)
