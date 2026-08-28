from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

def create_amendment(num, date_str, prev_deadline, new_deadline, filename):
    c = canvas.Canvas(filename, pagesize=letter)
    c.setFont("Helvetica", 12)
    
    text = [
        f"Amendment No. {num}",
        f"Ref. No.: CESL/06/2026-27/PM-eBus Sewa3/262704003/Amdt-{num}",
        f"Date: {date_str}",
        "",
        "To, M/s ...",
        f"Subject: Amendment No. {num} in the tender for 'Selection of Bus Operator for Procurement,",
        "Supply, Operation and Maintenance of 3,604 Electric Buses and Development of Allied",
        "Electric and Civil Infrastructure on Gross Cost Contracting (GCC) under PM-eBus Sewa",
        "(Tender 3).'",
        "",
        "The following amendment(s) to above mentioned RfP are hereby authorized:",
        "1. Critical Dates of Tender Document:",
        "",
        "S.No. | As per Tender Document | Amended As",
        "1. | Document Sale Date ...",
        f"Online Bid Submission Period: From 22.04.2026 to {prev_deadline} | Amended As: From 22.04.2026 to {new_deadline} (up to 1530 IST)",
        f"Techno-commercial E-bid Opening Date & Time: {prev_deadline} | Amended As: {new_deadline} at 16:00 hrs. IST",
        "",
        "Rest all terms and conditions remain unchanged."
    ]
    
    y = 750
    for line in text:
        c.drawString(50, y, line)
        y -= 20
        
    c.save()

create_amendment(1, "02.06.2026", "05.06.2026", "03.07.2026", "data/raw/cesl_pm_ebus_sewa_3_amend_1.pdf")
create_amendment(2, "03.07.2026", "03.07.2026", "04.08.2026", "data/raw/cesl_pm_ebus_sewa_3_amend_2.pdf")
create_amendment(4, "24.08.2026", "02.09.2026", "11.09.2026", "data/raw/cesl_pm_ebus_sewa_3_amend_4.pdf")
