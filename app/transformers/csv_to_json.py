import csv
from io import StringIO
from loguru import logger

def csv_to_json(csv_data: str):
    try:
        output = []
        csv_file = StringIO(csv_data)
        reader = csv.DictReader(csv_file)
        for row in reader:
            output.append(dict(row))
        return output
    except Exception as e:
        logger.error(f"Error parsing CSV: {str(e)}")
        return {"error": str(e)}