import re
import json
import os

filepath = r'backend/app/agent/pipeline.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# I want to find CATALOG = { ... } and keep only the 4 files we actually have.
match = re.search(r'CATALOG\s*=\s*(\{.*?\n\})', content, re.DOTALL)
if match:
    full_catalog_str = match.group(1)
    # The dictionary has string keys. We can parse it safely using Python.
    catalog_dict = eval(full_catalog_str)
    
    keep = ['cesl_pm_ebus_sewa_3_3604_buses_gcc.pdf', 'cesl_pm_ebus_sewa_3_amendment.pdf', 'cesl_pm_ebus_sewa_3_amend_4.pdf', 'jctsl_jaipur_rfp.pdf']
    
    new_catalog_dict = {k: catalog_dict[k] for k in keep if k in catalog_dict}
    
    # Dump it nicely formatted
    new_catalog_str = json.dumps(new_catalog_dict, indent=4)
    # json dumps booleans to lowercase true/false, we need True/False/None
    new_catalog_str = new_catalog_str.replace(': true', ': True').replace(': false', ': False').replace(': null', ': None')
    
    new_content = content[:match.start(1)] + new_catalog_str + content[match.end(1):]
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Successfully replaced CATALOG in pipeline.py")
else:
    print("Failed to find CATALOG block")
