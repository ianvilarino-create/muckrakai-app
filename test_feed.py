import requests
import xml.etree.ElementTree as ET

url = "https://contrataciondelestado.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom"
resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
root = ET.fromstring(resp.content)

ns = {
    'atom': 'http://www.w3.org/2005/Atom',
    'cac': 'urn:dgpe:names:draft:codice:schema:xsd:CommonAggregateComponents-2',
    'cbc': 'urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2'
}

for i, entry in enumerate(root.findall('atom:entry', ns)):
    if i > 5: break
    
    print(f"--- Entry {i} ---")
    
    # Check TendResult -> AwardDate
    tr = entry.findall('.//cac:TenderResult', ns)
    print("TenderResults:", len(tr))
    adjudicacion_tag = entry.find('.//cac:TenderResult/cbc:AwardDate', ns)
    print("AwardDate tag:", adjudicacion_tag.text if adjudicacion_tag is not None else "Not found")

    # Check Location
    rl = entry.findall('.//cac:RealizedLocation', ns)
    print("RealizedLocation:", len(rl))
    
    ubicacio_tag = entry.find('.//cac:RealizedLocation/cac:Address/cbc:CityName', ns)
    print("RealizedLocation CityName:", ubicacio_tag.text if ubicacio_tag is not None else "Not found")

    ubic_prov = entry.find('.//cac:RealizedLocation/cac:Address/cbc:CountrySubentityCode', ns)
    print("CountrySubentityCode:", ubic_prov.text if ubic_prov is not None else "Not found")

    party_city = entry.find('.//cac:Party/cac:PostalAddress/cbc:CityName', ns)
    print("Party CityName:", party_city.text if party_city is not None else "Not found")
    
    party_prov = entry.find('.//cac:Party/cac:PostalAddress/cbc:CountrySubentity', ns)
    print("Party CountrySubentity:", party_prov.text if party_prov is not None else "Not found")

