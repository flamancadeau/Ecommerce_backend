from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):

    response = exception_handler(exc, context)

    if response is not None:
        customized_response = {"success": False, "message": str(exc), "errors": []}

        if isinstance(response.data, dict):
            for key, value in response.data.items():
                error = {"field": key, "message": value}
                customized_response["errors"].append(error)
        elif isinstance(response.data, list):
            for error_msg in response.data:
                customized_response["errors"].append(
                    {"field": "non_field_errors", "message": error_msg}
                )
        else:
            customized_response["errors"].append(
                {"field": "non_field_errors", "message": response.data}
            )

        response.data = customized_response

    return response
