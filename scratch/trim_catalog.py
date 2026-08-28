import re

filepath = r'backend/app/agent/pipeline.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

match = re.search(r'CATALOG\s*=\s*(\{.*?\n\})', content, re.DOTALL)
if match:
    new_catalog = '''{
    "cesl_pm_ebus_sewa_3_3604_buses_gcc.pdf": {
        "tender_ref": "CESL/06/2026-27/PM-eBus Sewa3/262704003",
        "is_parent": True,
        "document_type": "ORIGINAL_RFP",
        "amendment_number": None,
        "title": "Selection of Bus Operator for Procurement of 3,604 Electric Buses under PM-eBus Sewa (Tender 3)",
        "issuing_authority": "Convergence Energy Services Limited (CESL)",
        "city": "Multi-City",
        "state": "Pan-India",
        "original_bus_quantity": 3604,
        "latest_bus_quantity": 3604,
        "latest_quantity_source": "Original RFP",
        "submission_deadline": "2026-06-05T14:30:00+05:30",
        "emd_amount": 1131000000.0,
        "emd_breakdown": {
            "Lot 1 (Rajasthan)": 8.25,
            "Lot 7 (Karnataka)": 28.00
        },
        "document_fee": 25000.0,
        "source_url": "http://www.convergence.co.in/public/upload/tender_pdf/3028u9d0gkh1o9uupc.pdf"
    },
    "cesl_pm_ebus_sewa_3_amendment.pdf": {
        "tender_ref": "CESL/06/2026-27/PM-eBus Sewa3/262704003",
        "is_parent": False,
        "document_type": "AMENDMENT",
        "amendment_number": "Amendment No. 1",
        "latest_bus_quantity": 3644,
        "latest_quantity_source": "Amendment No. 1",
        "latest_submission_deadline": "2026-08-01T15:00:00+05:30",
        "latest_deadline_source": "Amendment No. 1",
        "source_url": "http://www.convergence.co.in/public/upload/tender_pdf/3028u9d0gkh1o9uupc_amend.pdf"
    },
    "cesl_pm_ebus_sewa_3_amend_4.pdf": {
        "tender_ref": "CESL/06/2026-27/PM-eBus Sewa3/262704003",
        "is_parent": False,
        "document_type": "AMENDMENT",
        "amendment_number": "Amendment No. 4",
        "latest_submission_deadline": "2026-09-11T16:00:00+05:30",
        "latest_deadline_source": "Amendment No. 4",
        "source_url": "http://www.convergence.co.in/amend4"
    },
    "jctsl_jaipur_rfp.pdf": {
        "tender_ref": "NIB No. 11/2025-26",
        "is_parent": True,
        "document_type": "ORIGINAL_RFP",
        "amendment_number": None,
        "title": "Selection of Bus Operator for Procurement, Supply, Operation and Maintenance of 50 Fully Built Pure Electric Double Decker AC Buses on Gross Cost Contracting (GCC)",
        "issuing_authority": "JCTSL",
        "city": "Jaipur",
        "state": "Rajasthan",
        "original_bus_quantity": 50,
        "latest_bus_quantity": 50,
        "latest_quantity_source": "Original RFP",
        "submission_deadline": "2026-09-22T18:00:00+05:30",
        "emd_amount": 5000000.0,
        "document_fee": 5000.0,
        "source_url": "https://transport.rajasthan.gov.in/jctsl"
    }
}'''
    
    new_content = content[:match.start(1)] + new_catalog + content[match.end(1):]
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Updated pipeline.py CATALOG")
else:
    print("Could not find CATALOG block in pipeline.py")
