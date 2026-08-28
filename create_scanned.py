from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
import os

def create_scanned_jctsl_pdf():
    # 1. Create an image with text (simulating a scanned document)
    img = Image.new('RGB', (800, 1000), color='white')
    d = ImageDraw.Draw(img)
    # Use default font
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()
        
    text = """
    JCTSL Jaipur RFP
    Selection of Bus Operator for Procurement, Supply, Operation and Maintenance
    of 50 Fully Built Pure Electric Double Decker AC Buses on Gross Cost Contracting (GCC)
    in Jaipur, Jodhpur and Udaipur Cities.
    
    NIB No. 11/2025-26
    
    Deadline for submission: 22-Sep-2026, 18:00 IST
    
    Minimum Annual Turnover: 10 Crores
    EMD Amount: 50 Lakhs
    """
    
    d.text((50, 50), text, fill=(0,0,0), font=font)
    img_path = "temp_scan.png"
    img.save(img_path)
    
    # 2. Put the image in a PDF (so it has no text layer, just an image)
    c = canvas.Canvas("data/raw/jctsl_jaipur_rfp.pdf")
    c.drawImage(img_path, 0, 0, width=600, height=800)
    c.save()
    
    os.remove(img_path)
    print("Scanned JCTSL PDF created.")

if __name__ == "__main__":
    create_scanned_jctsl_pdf()
