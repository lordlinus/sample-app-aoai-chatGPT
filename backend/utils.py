import os
import json
import logging
import requests
import dataclasses

DEBUG = os.environ.get("DEBUG", "false")
if DEBUG.lower() == "true":
    logging.basicConfig(level=logging.DEBUG)

AZURE_SEARCH_PERMITTED_GROUPS_COLUMN = os.environ.get(
    "AZURE_SEARCH_PERMITTED_GROUPS_COLUMN"
)


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)


async def format_as_ndjson(r):
    try:
        async for event in r:
            yield json.dumps(event, cls=JSONEncoder) + "\n"
    except Exception as error:
        logging.exception("Exception while generating response stream: %s", error)
        yield json.dumps({"error": str(error)})


def parse_multi_columns(columns: str) -> list:
    if "|" in columns:
        return columns.split("|")
    else:
        return columns.split(",")


def fetchUserGroups(userToken, nextLink=None):
    # Recursively fetch group membership
    if nextLink:
        endpoint = nextLink
    else:
        endpoint = "https://graph.microsoft.com/v1.0/me/transitiveMemberOf?$select=id"

    headers = {"Authorization": "bearer " + userToken}
    try:
        r = requests.get(endpoint, headers=headers)
        if r.status_code != 200:
            logging.error(f"Error fetching user groups: {r.status_code} {r.text}")
            return []

        r = r.json()
        if "@odata.nextLink" in r:
            nextLinkData = fetchUserGroups(userToken, r["@odata.nextLink"])
            r["value"].extend(nextLinkData)

        return r["value"]
    except Exception as e:
        logging.error(f"Exception in fetchUserGroups: {e}")
        return []


def generateFilterString(userToken):
    # Get list of groups user is a member of
    userGroups = fetchUserGroups(userToken)

    # Construct filter string
    if not userGroups:
        logging.debug("No user groups found")

    group_ids = ", ".join([obj["id"] for obj in userGroups])
    return f"{AZURE_SEARCH_PERMITTED_GROUPS_COLUMN}/any(g:search.in(g, '{group_ids}'))"


def format_pf_non_streaming_response(
    chatCompletion, history_metadata, message_uuid=None
):
    logging.debug("chatCompletion: {chatCompletion}")
    response_field = os.environ.get("PROMPTFLOW_RESPONSE_FIELD_NAME")
    if not response_field:
        response_field = get_pf_swagger_spec()
    response_obj = {
        "id": chatCompletion["id"],
        "model": "",
        "created": "",
        "object": "",
        "choices": [
            {
                "messages": [
                    {"role": "assistant", "content": chatCompletion[response_field]}
                ]
            }
        ],
        "history_metadata": history_metadata,
    }
    return response_obj


def format_non_streaming_response(chatCompletion, history_metadata, message_uuid=None):
    response_obj = {
        "id": chatCompletion.id,
        "model": chatCompletion.model,
        "created": chatCompletion.created,
        "object": chatCompletion.object,
        "choices": [{"messages": []}],
        "history_metadata": history_metadata,
    }

    if len(chatCompletion.choices) > 0:
        message = chatCompletion.choices[0].message
        if message:
<<<<<<< HEAD
            if hasattr(message, "context"):
                response_obj["choices"][0]["messages"].append({
                    "role": "tool",
                    "content": json.dumps(message.context),
                })
            response_obj["choices"][0]["messages"].append({
                "role": "assistant",
                "content": message.content,
            })
=======
            if hasattr(message, "context") and message.context.get("messages"):
                for m in message.context["messages"]:
                    if m["role"] == "tool":
                        response_obj["choices"][0]["messages"].append(
                            {"role": "tool", "content": m["content"]}
                        )
            elif hasattr(message, "context"):
                response_obj["choices"][0]["messages"].append(
                    {
                        "role": "tool",
                        "content": json.dumps(message.context),
                    }
                )
            response_obj["choices"][0]["messages"].append(
                {
                    "role": "assistant",
                    "content": message.content,
                }
            )
>>>>>>> 560ad81 (add support for promptflow endpoint)
            return response_obj

    return {}


def format_stream_response(chatCompletionChunk, history_metadata, message_uuid=None):
    response_obj = {
        "id": chatCompletionChunk.id,
        "model": chatCompletionChunk.model,
        "created": chatCompletionChunk.created,
        "object": chatCompletionChunk.object,
        "choices": [{"messages": []}],
        "history_metadata": history_metadata,
    }

    if len(chatCompletionChunk.choices) > 0:
        delta = chatCompletionChunk.choices[0].delta
        if delta:
<<<<<<< HEAD
            if hasattr(delta, "context"):
                messageObj = {
                    "role": "tool",
                    "content": json.dumps(delta.context)
                }
                response_obj["choices"][0]["messages"].append(messageObj)
                return response_obj
=======
            if hasattr(delta, "context") and delta.context.get("messages"):
                for m in delta.context["messages"]:
                    if m["role"] == "tool":
                        messageObj = {"role": "tool", "content": m["content"]}
                        response_obj["choices"][0]["messages"].append(messageObj)
                        return response_obj
>>>>>>> 560ad81 (add support for promptflow endpoint)
            if delta.role == "assistant" and hasattr(delta, "context"):
                messageObj = {
                    "role": "assistant",
                    "context": delta.context,
                }
                response_obj["choices"][0]["messages"].append(messageObj)
                return response_obj
            else:
                if delta.content:
                    messageObj = {
                        "role": "assistant",
                        "content": delta.content,
                    }
                    response_obj["choices"][0]["messages"].append(messageObj)
                    return response_obj

    return {}


def convert_to_pf_format(input_json):
    output_json = []
    # align the input json to the format expected by promptflow chat flow
    for message in input_json["messages"]:
        if message:
            if message["role"] == "user":
                new_obj = {
                    "inputs": {"question": message["content"]},
                    "outputs": {"answer": ""},
                }
                output_json.append(new_obj)
            elif message["role"] == "assistant" and output_json:
                output_json[-1]["outputs"]["answer"] = message["content"]
    return output_json


def get_pf_swagger_spec():
    logging.debug("Fetching Promptflow Swagger spec")
    response = requests.get(
        url=f"{os.environ.get('PROMPTFLOW_ENDPOINT').split('/score')[0]}/swagger.json",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": "Bearer " + os.environ.get("PROMPTFLOW_API_KEY"),
        },
    )
    if response.status_code == 200:
        swagger_dict = response.json()  # Convert the response to JSON
        response_fields = swagger_dict["paths"]["/score"]["post"]["responses"]["200"][
            "content"
        ]["application/json"]["schema"]["properties"]
        # get the first response field name from the swagger spec
        # this is the field name that will be used to extract the response from the promptflow response. set 'PROMPTFLOW_RESPONSE_FIELD_NAME' if you want to use a different field name
        response_field = list(response_fields.keys())[0]
        logging.debug(f"Response field name set to: {response_field}")
        # set the response field name in the environment variable for subsequent use
        os.environ["PROMPTFLOW_RESPONSE_FIELD_NAME"] = response_field
        return response_field
    else:
        logging.error(
            f"Error fetching Promptflow Swagger spec {response.status_code} {response.text}"
        )
