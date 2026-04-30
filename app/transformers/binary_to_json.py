from loguru import logger

def binary_to_json(binary_data: bytes):
    try:
        return {"data": list(binary_data)}
    except Exception as e:
        logger.error(f"Error converting binary data: {str(e)}")
        return {"error": str(e)}