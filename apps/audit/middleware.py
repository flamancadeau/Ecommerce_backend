import uuid
import logging
import time
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class AuditLogMiddleware(MiddlewareMixin):
    def process_request(self, request):

        correlation_id = request.headers.get("X-Correlation-Id", str(uuid.uuid4()))
        request.correlation_id = correlation_id
        request.start_time = time.time()

    def process_response(self, request, response):
        correlation_id = getattr(request, "correlation_id", "unknown")
        response["X-Correlation-Id"] = correlation_id

        duration = time.time() - getattr(request, "start_time", time.time())

        user = getattr(request, "user", "Anonymous")
        method = request.method
        path = request.path
        status_code = response.status_code

        logger.info(
            f"AUDIT-LOG: {correlation_id} | {user} | {method} {path} | Status: {status_code} | Duration: {duration:.3f}s"
        )

        return response
