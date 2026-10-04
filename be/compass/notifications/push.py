"""Private browser subscription storage and bounded Web Push delivery."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import uuid
from datetime import timedelta
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from pywebpush import WebPushException, webpush

from .models import PushDelivery, PushDeliveryStatus, PushSubscription
from .push_policy import push_body_for

logger = logging.getLogger("compass.notifications")
MAX_ATTEMPTS = 3


class InvalidPushSubscription(ValueError):
    pass


def _cipher() -> Fernet:
    return Fernet(settings.WEB_PUSH_STORAGE_KEY.encode("ascii"))


def _decode_key(value: str, *, length: int) -> None:
    if len(value) > 180 or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise InvalidPushSubscription("Invalid browser subscription keys.")
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, base64.binascii.Error) as exc:
        raise InvalidPushSubscription("Invalid browser subscription keys.") from exc
    if len(raw) != length:
        raise InvalidPushSubscription("Invalid browser subscription keys.")
    if length == 65 and raw[0] != 4:
        raise InvalidPushSubscription("Invalid browser subscription keys.")


def _digest_endpoint(endpoint: str) -> str:
    if not isinstance(endpoint, str) or len(endpoint) > 2048:
        raise InvalidPushSubscription("Invalid browser subscription endpoint.")
    try:
        url = urlsplit(endpoint)
        host = (url.hostname or "").lower()
        port = url.port
    except ValueError as exc:
        raise InvalidPushSubscription("Invalid browser subscription endpoint.") from exc
    # A narrow provider allowlist prevents an authenticated account from turning the
    # worker into an SSRF client. Add new push service hosts only after review.
    allowed = host in {
        "fcm.googleapis.com",
        "updates.push.services.mozilla.com",
        "web.push.apple.com",
        "webpush.push.apple.com",
    } or host.endswith(".notify.windows.com")
    if (
        url.scheme != "https"
        or not allowed
        or port not in (None, 443)
        or url.username
        or url.password
        or url.fragment
        or not url.path.startswith("/")
    ):
        raise InvalidPushSubscription("Invalid browser subscription endpoint.")
    return hashlib.sha256(endpoint.encode("utf-8")).hexdigest()


def register_subscription(
    *, user, session, endpoint: str, p256dh: str, auth: str
) -> PushSubscription:
    digest = _digest_endpoint(endpoint)
    _decode_key(p256dh, length=65)
    _decode_key(auth, length=16)
    cipher = _cipher()
    with transaction.atomic():
        existing = (
            PushSubscription.objects.select_for_update().filter(endpoint_digest=digest).first()
        )
        if existing and (existing.user_id != user.pk or existing.session_id != session.pk):
            PushDelivery.objects.filter(
                subscription=existing,
                status__in=(PushDeliveryStatus.PENDING, PushDeliveryStatus.PROCESSING),
            ).update(
                status=PushDeliveryStatus.CANCELLED,
                failure_code="rebound",
                claim_token=None,
                claim_expires_at=None,
                next_attempt_at=None,
            )
        subscription, _created = PushSubscription.objects.update_or_create(
            endpoint_digest=digest,
            defaults={
                "user": user,
                "session": session,
                "encrypted_endpoint": cipher.encrypt(endpoint.encode()).decode(),
                "encrypted_p256dh": cipher.encrypt(p256dh.encode()).decode(),
                "encrypted_auth": cipher.encrypt(auth.encode()).decode(),
                "active": True,
            },
        )
    return subscription


def subscription_enabled(*, user, session, endpoint: str) -> bool:
    digest = _digest_endpoint(endpoint)
    return PushSubscription.objects.filter(
        user=user, session=session, endpoint_digest=digest, active=True
    ).exists()


def remove_subscription(*, user, endpoint: str) -> bool:
    digest = _digest_endpoint(endpoint)
    with transaction.atomic():
        subscription = (
            PushSubscription.objects.select_for_update()
            .filter(user=user, endpoint_digest=digest, active=True)
            .first()
        )
        if subscription is None:
            return False
        subscription.active = False
        subscription.save(update_fields=["active", "updated_at"])
        PushDelivery.objects.filter(
            subscription=subscription,
            status__in=(PushDeliveryStatus.PENDING, PushDeliveryStatus.PROCESSING),
        ).update(
            status=PushDeliveryStatus.CANCELLED,
            failure_code="disabled",
            claim_token=None,
            claim_expires_at=None,
            next_attempt_at=None,
        )
        return True


def create_push_deliveries(notification) -> tuple[str, ...]:
    if not settings.WEB_PUSH_ENABLED or not notification.recipient.is_active:
        return ()
    if push_body_for(notification.event_code) is None:
        return ()
    now = timezone.now()
    ids = []
    for subscription in PushSubscription.objects.filter(
        user=notification.recipient,
        active=True,
        session__revoked_at__isnull=True,
        session__expires_at__gt=now,
    ):
        delivery, created = PushDelivery.objects.get_or_create(
            notification=notification, subscription=subscription
        )
        if created:
            ids.append(str(delivery.pk))
    return tuple(ids)


def due_push_delivery_ids() -> list[uuid.UUID]:
    now = timezone.now()
    return list(
        PushDelivery.objects.filter(
            Q(status=PushDeliveryStatus.PENDING, next_attempt_at__lte=now)
            | Q(status=PushDeliveryStatus.PROCESSING, claim_expires_at__lte=now)
        )
        .order_by("next_attempt_at")
        .values_list("pk", flat=True)[:200]
    )


def _send(subscription: PushSubscription, body: str) -> None:
    cipher = _cipher()
    webpush(
        subscription_info={
            "endpoint": cipher.decrypt(subscription.encrypted_endpoint.encode()).decode(),
            "keys": {
                "p256dh": cipher.decrypt(subscription.encrypted_p256dh.encode()).decode(),
                "auth": cipher.decrypt(subscription.encrypted_auth.encode()).decode(),
            },
        },
        data=json.dumps({"title": "COMPASS", "body": body, "path": "/portal/notifications"}),
        vapid_private_key=settings.WEB_PUSH_PRIVATE_KEY,
        vapid_claims={"sub": settings.WEB_PUSH_CONTACT},
        ttl=3600,
        timeout=5,
    )


def deliver_push_delivery(delivery_id: uuid.UUID) -> str:
    now = timezone.now()
    with transaction.atomic():
        delivery = (
            PushDelivery.objects.select_for_update()
            .select_related("notification__recipient", "subscription__session")
            .filter(pk=delivery_id)
            .first()
        )
        if delivery is None or delivery.status in {
            PushDeliveryStatus.SENT,
            PushDeliveryStatus.FAILED,
            PushDeliveryStatus.CANCELLED,
        }:
            return "skipped"
        if (
            delivery.status == PushDeliveryStatus.PROCESSING
            and delivery.claim_expires_at
            and delivery.claim_expires_at > now
        ):
            return "skipped"
        if (
            delivery.status == PushDeliveryStatus.PENDING
            and delivery.next_attempt_at
            and delivery.next_attempt_at > now
        ):
            return "skipped"
        if delivery.attempt_count >= MAX_ATTEMPTS:
            delivery.status = PushDeliveryStatus.FAILED
            delivery.failure_code = "attempt_limit"
            delivery.save(update_fields=["status", "failure_code", "updated_at"])
            return PushDeliveryStatus.FAILED
        sub = delivery.subscription
        session = sub.session
        if (
            not settings.WEB_PUSH_ENABLED
            or not sub.active
            or not delivery.notification.recipient.is_active
            or sub.user_id != delivery.notification.recipient_id
            or session.user_id != sub.user_id
            or session.revoked_at is not None
            or session.expires_at <= now
            or push_body_for(delivery.notification.event_code) is None
        ):
            delivery.status = PushDeliveryStatus.CANCELLED
            delivery.save(update_fields=["status", "updated_at"])
            return PushDeliveryStatus.CANCELLED
        token = uuid.uuid4()
        delivery.status = PushDeliveryStatus.PROCESSING
        delivery.attempt_count += 1
        delivery.claim_token = token
        delivery.claim_expires_at = now + timedelta(seconds=90)
        delivery.save(
            update_fields=[
                "status",
                "attempt_count",
                "claim_token",
                "claim_expires_at",
                "updated_at",
            ]
        )
        body = push_body_for(delivery.notification.event_code)

    status = PushDeliveryStatus.SENT
    failure_code = ""
    try:
        _send(sub, body)
    except WebPushException as exc:
        code = exc.status_code
        if code in (404, 410):
            status, failure_code = PushDeliveryStatus.CANCELLED, "gone"
        elif code in (429, 500, 502, 503, 504) or code is None:
            status, failure_code = PushDeliveryStatus.PENDING, "transient"
        else:
            status, failure_code = PushDeliveryStatus.FAILED, "rejected"
    except Exception:
        status, failure_code = PushDeliveryStatus.PENDING, "transport"
    with transaction.atomic():
        current = (
            PushDelivery.objects.select_for_update()
            .filter(pk=delivery_id, claim_token=token)
            .first()
        )
        if current is None:
            return "skipped"
        if status == PushDeliveryStatus.PENDING and current.attempt_count >= MAX_ATTEMPTS:
            status = PushDeliveryStatus.FAILED
        current.status = status
        current.failure_code = failure_code
        current.claim_token = None
        current.claim_expires_at = None
        current.next_attempt_at = (
            timezone.now() + timedelta(seconds=60 * (2 ** (current.attempt_count - 1)))
            if status == PushDeliveryStatus.PENDING
            else None
        )
        current.save(
            update_fields=[
                "status",
                "failure_code",
                "claim_token",
                "claim_expires_at",
                "next_attempt_at",
                "updated_at",
            ]
        )
        if failure_code == "gone":
            PushSubscription.objects.filter(pk=current.subscription_id).update(active=False)
    logger.info(
        "push delivery processed",
        extra={
            "event": "push_delivery_processed",
            "delivery_id": str(delivery_id),
            "status": status,
            "failure_code": failure_code,
        },
    )
    return str(status)
