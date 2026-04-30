from loguru import logger
import requests


def odata_to_json(odata_url, params=None):
    try:
        if params is None:
            params = {}
        params['$format'] = 'json'
        response = requests.get(odata_url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error with odata service: {e}")
        return None
# Придумать механизм унификации под odata
#def odata_to_json(odata_data: str):
    #try:
     #   parsed_data = parse(odata_data)
      #  return parsed_data
    #except Exception as e:
       # logger.error(f"Error parsing OData: {str(e)}")
       # return {"error": str(e)}