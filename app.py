import streamlit as st
import requests
import os
import tempfile
from PyPDF2 import PdfMerger
import base64
from datetime import datetime
import time
from PIL import Image
import fitz  # PyMuPDF
import img2pdf

# --- Edition Mapping ---
edition_map = {
    "Cuttack": "ct",
    "Bhubaneshwar": "bh",
    "Sambalpur": "sa",
    "Balasore": "ba",
    "Berhampur": "br",
    "Roukerla": "ro",
    "Angul": "an",
    "Koraput": "ko",
    "Kolkata": "kk",
    "Vizag": "vz"
}

def pdf_page_to_jpg(pdf_path, jpg_path, quality, dpi):
    """Convert a single-page PDF to JPG with reduced quality and DPI."""
    with fitz.open(pdf_path) as doc:
        page = doc[0]
        pix = page.get_pixmap(dpi=dpi)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img.save(jpg_path, format='JPEG', quality=quality)

# --- Streamlit UI ---
st.title("Newspaper Downloader")
st.write("Download the first 20 pages of the selected edition and date as a single merged PDF.")

edition_names = list(edition_map.keys())
selected_edition = st.selectbox("Select Edition", edition_names)
edition_code = edition_map[selected_edition]

input_date = st.date_input("Select Date")

if st.button("Download Newspaper"):
    with st.spinner("Downloading and merging PDF pages..."):
        date_str = input_date.strftime('%d%m%Y')  # DDMMYYYY
        date_display = input_date.strftime('%d.%m.%Y')
        pdf_urls = [
            f"https://www.samajaepaper.in/epaperimages//{date_str}//{date_str}-md-{edition_code}-{i}.pdf"
            for i in range(1, 21)
        ]
        temp_files = []
        merger = PdfMerger()
        try:
            for url in pdf_urls:
                try:
                    resp = requests.get(url, timeout=10)
                    if resp.status_code == 200:
                        fd, temp_path = tempfile.mkstemp(suffix='.pdf')
                        os.close(fd)
                        time.sleep(0.5)  # Small delay to avoid overwhelming the server
                        with open(temp_path, 'wb') as f:
                            f.write(resp.content)
                        # Convert the downloaded PDF page to JPG and back to PDF for size reduction
                        fd2, jpg_path = tempfile.mkstemp(suffix='.jpg')
                        os.close(fd2)
                        pdf_page_to_jpg(temp_path, jpg_path, quality=25, dpi=120)
                        # Convert JPG back to PDF
                        fd3, compressed_pdf_path = tempfile.mkstemp(suffix='.pdf')
                        os.close(fd3)
                        with open(compressed_pdf_path, 'wb') as f:
                            f.write(img2pdf.convert(jpg_path))
                        merger.append(compressed_pdf_path)
                        temp_files.append(temp_path)
                        temp_files.append(jpg_path)
                        temp_files.append(compressed_pdf_path)
                    else:
                        st.warning(f"Page not found: {url}")
                except Exception as e:
                    st.warning(f"Failed to download {url}: {e}")
            if temp_files:
                merged_filename = f"Samaja - {selected_edition} - {date_display}.pdf"
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_merged:
                    merger.write(tmp_merged.name)
                    merger.close()
                    with open(tmp_merged.name, "rb") as f:
                        data = f.read()
                    b64 = base64.b64encode(data).decode()
                    href = f'<a href="data:application/pdf;base64,{b64}" download="{merged_filename}">Download the merged newspaper PDF</a>'
                    st.markdown(href, unsafe_allow_html=True)
                os.unlink(tmp_merged.name)
            else:
                st.error("No pages were downloaded. Please check the date and edition.")
        finally:
            for file in temp_files:
                try:
                    os.unlink(file)
                except Exception:
                    pass
