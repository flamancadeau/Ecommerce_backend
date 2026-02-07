from functools import wraps
from rest_framework.response import Response
from .models import IdempotencyKey


def idempotent_request(key_field="idempotency_key"):
    """
    Decorator to make a view action idempotent.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(view_instance, request, *args, **kwargs):
            key = (
                request.data.get(key_field) if isinstance(request.data, dict) else None
            )
            key = key or request.headers.get("X-Idempotency-Key")

            if not key:
                return view_func(view_instance, request, *args, **kwargs)

            full_key = f"{request.path}:{key}"

            idem_key, created = IdempotencyKey.objects.verify_or_create(
                key=full_key, request_path=request.path, request_data=request.data
            )

            if not created:
                if idem_key.status == IdempotencyKey.Status.COMPLETED:
                    return Response(
                        idem_key.response_body, status=idem_key.response_code
                    )
                elif idem_key.status == IdempotencyKey.Status.PROCESSING:
                    return Response(
                        {"error": "Request is already being processed"}, status=409
                    )

            try:
                response = view_func(view_instance, request, *args, **kwargs)

                if response.status_code < 500:
                    idem_key.mark_completed(response.status_code, response.data)
                else:
                    idem_key.mark_failed()

                return response
            except Exception as e:
                idem_key.mark_failed()
                raise e

        return _wrapped_view

    return decorator
