import xmltodict

def xml_to_json(xml_data):
    return xmltodict.parse(xml_data)