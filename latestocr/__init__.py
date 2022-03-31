import logging
import json
import os
import logging
import datetime, time, requests
from json import JSONEncoder
import os
import azure.functions as func
import base64

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Invoked OCR Skill')
    try:
        body = json.dumps(req.get_json())
        logging.info("body: " + body)
        if body:
            #logging.info("Body is :", body)
            result = compose_response(body)
            logging.info("Result to return to custom skill: " + result)
            return func.HttpResponse(result, mimetype="application/json")
        else:
            return func.HttpResponse(
                "Invalid body",
                status_code=400
            )
    except ValueError:
        return func.HttpResponse(
             "Invalid body",
             status_code=400
        )

def compose_response(json_data):
    values = json.loads(json_data)['values']
    # Prepare the Output before the loop
    results = {}
    results["values"] = []
    endpoint = os.environ["READ_ENDPOINT"]
    key = os.environ["READ_ENDPOINT_KEY"]
    i=0
    for value in values:
        output_record = read(endpoint=endpoint, key=key, recordId=value["recordId"], data=value["data"])
        merged_content=""
        #navigate the json with a for loop and extract text field
        if 'data' in output_record:
            for i in output_record['data']:
                if 'lines' in i:
                    for l in i['lines']:
                        if 'text' in l:
                            merged_content=merged_content+l['text']+' '
        output = {"recordId": value["recordId"],"data": {"text": merged_content}}
        results["values"].append(output)
    return json.dumps(results, ensure_ascii=False)

def read(endpoint, key, recordId, data):
    try:
        docUrl = base64.b64decode(data["Url"]).decode('utf-8')[:-1] + data["SasToken"]
        body = {'url': docUrl}
        header = {'Ocp-Apim-Subscription-Key': key}
        logging.info("docurl is: " + docUrl)
        body_json = json.dumps(body)
        #Read API works in two steps, first you post the job, afterwards you get the result
        response_job = requests.post(endpoint, data = body_json, headers = header)
        logging.info('Wait for Read API to process the document')
        time.sleep(3) # Let some time to process the job, you could do active polling 
        urltoretrieveresult = response_job.headers["operation-location"]
        response = requests.get(urltoretrieveresult, None, headers=header)
        dict=json.loads(response.text)
        i=0
        #sometimes the Read processing time will be longer, in that case we need to try again after a while
        while dict["status"] != "Succeeded" and i<10:
            time.sleep(3)
            response = requests.get(urltoretrieveresult, None, headers=header)
            dict=json.loads(response.text)
            logging.info('Read API processing time is longer than expected, retrying...')
            time.sleep(3)
            i=i+1
        read_result=dict['analyzeResult']['readResults']
        logging.info("Inside reading ")
        output_record = {
            "recordId": recordId,
            "data": read_result
        }

    except Exception as error:
        output_record = {
            "recordId": recordId,
            "errors": [ { "message": "Error: " + str(error) }   ] 
        }
    #logging.info("Output record: " + json.dumps(output_record, ensure_ascii=False))
    return output_record
