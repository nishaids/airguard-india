from src.deploy.public_exports import sanitize, LOCAL_PATH


def test_local_paths_are_removed_without_modifying_results():
    value={'mae':15.1,'example':'C:\\Users\\Private Person\\result.json','other':'/Users/private/report.json','source':'https://airquality.cpcb.gov.in','nested':[{'n':12}]}
    safe=sanitize(value)
    assert safe['mae']==15.1 and safe['nested']==value['nested'] and safe['source']==value['source']
    assert not LOCAL_PATH.search(str(safe))
    assert value['example'].startswith('C:')
