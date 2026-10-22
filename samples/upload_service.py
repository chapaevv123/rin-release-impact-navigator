"""Synthetic fixture, not a real user's application."""
from flask import Request


def upload_limit(request: Request) -> int | None:
    return request.max_content_length
