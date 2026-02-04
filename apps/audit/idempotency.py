from functools import wraps
from rest_framework.response import Response
from .models import IdempotencyKey
from django.db import transaction


def idempotent_request(key_field="idempotency_key"):
    """
    Decorator to make a view action idempotent.
    Checks for the key in request data.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(view_instance, request, *args, **kwargs):
            key = request.data.get(key_field) or request.headers.get(
                "X-Idempotency-Key"
            )

            if not key:
                return view_func(view_instance, request, *args, **kwargs)

            full_key = f"{request.path}:{key}"

            try:
                with transaction.atomic():
                    (
                        idem_key,
                        created,
                    ) = IdempotencyKey.objects.select_for_update().get_or_create(
                        key=full_key, defaults={"request_path": request.path}
                    )

                    if not created and idem_key.response_code:
                        return Response(
                            idem_key.response_body, status=idem_key.response_code
                        )

                    response = view_func(view_instance, request, *args, **kwargs)

                    if response.status_code < 500:
                        idem_key.response_code = response.status_code
                        idem_key.response_body = response.data
                        idem_key.save()

                    return response
            except Exception as e:

                raise e

        return _wrapped_view

    return decorator
