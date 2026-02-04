from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):

    response = exception_handler(exc, context)

    if response is not None:
        customized_response = {}
        customized_response["errors"] = []

        for key, value in response.data.items():
            error = {"field": key, "message": value}
            customized_response["errors"].append(error)

        response.data = customized_response

    return response
