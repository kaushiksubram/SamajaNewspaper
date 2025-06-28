import streamlit as st
from langchain_community.llms import Cohere
from langchain.agents import initialize_agent, Tool
from langchain_experimental.tools.python.tool import PythonREPLTool
import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import os
import tempfile
import base64
from PyPDF2 import PdfReader, PdfWriter

# --- Helper Functions ---
def scrape_newspaper_images(date_str):
    """
    Scrape all page image URLs for the given date from the newspaper site.
    Returns a list of image URLs.
    """
    # This is a placeholder. Actual implementation will depend on the site's structure.
    # You may need to inspect the site to find the correct way to get image URLs for a date.
    url = f"https://samajaepaper.in/indexnext.php?pagedate={date_str}"
    resp = requests.get(url)
    soup = BeautifulSoup(resp.content, 'html.parser')
    # Example: Find all <img> tags with a specific class or attribute
    images = []
    for img in soup.find_all('img'):
        src = img.get('src')
        if src and 'epaperimages' in src:
            if not src.startswith('http'):
                src = 'https://samajaepaper.in/' + src.lstrip('/')
            images.append(src)
    return images

def download_images(image_urls):
    """Download images and return list of PIL Images."""
    images = []
    for url in image_urls:
        resp = requests.get(url)
        img = Image.open(BytesIO(resp.content))
        images.append(img)
    return images

def merge_images_to_pdf(images, output_path):
    """Merge PIL Images into a single PDF file."""
    # Ensure all images are in RGB mode and only merge, not duplicate
    rgb_images = [img.convert('RGB') for img in images]
    if rgb_images:
        rgb_images[0].save(output_path, save_all=True, append_images=rgb_images[1:], format='PDF')
    return output_path

def split_pdf_second_half(input_pdf_path, output_pdf_path):
    """Split the PDF and save only the second half to output_pdf_path."""
    reader = PdfReader(input_pdf_path)
    total_pages = len(reader.pages)
    half = total_pages // 2
    # If odd, second half is larger
    start = half
    writer = PdfWriter()
    for i in range(start, total_pages):
        writer.add_page(reader.pages[i])
    with open(output_pdf_path, 'wb') as f:
        writer.write(f)
    return total_pages, output_pdf_path

def get_pdf_download_link(pdf_path):
    with open(pdf_path, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    href = f'<a href="data:application/pdf;base64,{b64}" download="newspaper.pdf">Download merged newspaper PDF</a>'
    return href


# --- Streamlit UI ---
st.title("Merged Newspaper Downloader")
st.write("Enter a date to download and merge all pages of the newspaper.")

# User input for Cohere API Key

cohere_api_key = st.text_input("Enter the provided Key", type="password")
if not cohere_api_key:
    st.warning("Please enter the provided API Key to continue.")
    st.stop()

# Validate Cohere API Key
import cohere
if cohere_api_key:
    try:
        co = cohere.Client(cohere_api_key)
        # Use a minimal generate call for validation
        _ = co.generate(prompt="Hello", max_tokens=1, model="command")
    except Exception as e:
        st.error("Invalid API Key. Please check your key and try again.")
        st.stop()

# --- LangChain Agent Setup ---
cohere_llm = Cohere(cohere_api_key=cohere_api_key)

# Define tools for the agent
scrape_tool = Tool(
    name="Scrape Newspaper Images",
    func=scrape_newspaper_images,
    description="Scrape all page image URLs for a given date (YYYY-MM-DD) from the newspaper site."
)
download_tool = Tool(
    name="Download Images",
    func=download_images,
    description="Download images from a list of URLs and return PIL Images."
)
merge_tool = Tool(
    name="Merge Images to PDF",
    func=merge_images_to_pdf,
    description="Merge a list of PIL Images into a single PDF file."
)


agent = initialize_agent(
    tools=[scrape_tool, download_tool, merge_tool, PythonREPLTool()],
    llm=cohere_llm,
    agent="zero-shot-react-description",
    verbose=True
)


input_date = st.date_input("Select Date")
if st.button("Download Newspaper"):
    with st.spinner("Processing..."):
        date_str = input_date.strftime('%Y-%m-%d')
        # Agent orchestrates the process
        image_urls = scrape_newspaper_images(date_str)
        if not image_urls:
            st.error("No images found for this date.")
        else:
            images = download_images(image_urls)
            # Create a temp file with date in the filename
            filename = f"Samaja_{date_str}.pdf"
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{date_str}_merged.pdf") as tmp_merged:
                merged_pdf_path = merge_images_to_pdf(images, tmp_merged.name)
            # Split and keep only the second half
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{date_str}_secondhalf.pdf") as tmp_half:
                total_pages, second_half_pdf_path = split_pdf_second_half(merged_pdf_path, tmp_half.name)
            # Now, split the second half to keep only the first 20 pages
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{date_str}_first20.pdf") as tmp_first20:
                reader = PdfReader(second_half_pdf_path)
                writer = PdfWriter()
                n_pages = min(20, len(reader.pages))
                for i in range(n_pages):
                    writer.add_page(reader.pages[i])
                with open(tmp_first20.name, 'wb') as f:
                    writer.write(f)
                first20_pdf_path = tmp_first20.name
            st.success(f"Merged PDF created! Only the first 20 pages are included.")
            # Provide download link with date-stamped filename
            with open(first20_pdf_path, "rb") as f:
                data = f.read()
            import base64
            b64 = base64.b64encode(data).decode()
            href = f'<a href="data:application/pdf;base64,{b64}" download="{filename}">Download the merged newspaper PDF</a>'
            st.markdown(href, unsafe_allow_html=True)
            os.unlink(merged_pdf_path)
            os.unlink(second_half_pdf_path)
            os.unlink(first20_pdf_path)
