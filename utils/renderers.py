from rest_framework.renderers import JSONRenderer


class UnifiedJSONRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        if renderer_context is None:
            renderer_context = {}

        response = renderer_context.get("response")
        status_code = response.status_code if response else 200

        formatted_response = {
            "status": "success",
            "message": "Request was successful.",
            "data": data,
            "code": status_code,
        }

        if status_code >= 400:
            formatted_response["status"] = "fail"
            formatted_response["data"] = None

            if data is None:
                formatted_response["message"] = "An unknown error occurred."
            elif isinstance(data, dict):
                if "detail" in data:
                    formatted_response["message"] = str(data["detail"])
                elif "message" in data:

                    formatted_response["message"] = str(data["message"])
                else:

                    messages = []
                    for key, value in data.items():
                        error_text = value
                        if isinstance(value, list):
                            error_text = ", ".join([str(v) for v in value])
                        messages.append(f"{key}: {error_text}")
                    formatted_response["message"] = " | ".join(messages)

            elif isinstance(data, list):
                formatted_response["message"] = ", ".join([str(x) for x in data])
            else:
                formatted_response["message"] = str(data)

        return super().render(formatted_response, accepted_media_type, renderer_context)
