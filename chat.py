import logging
from openai import OpenAI
from dotenv import load_dotenv
import os
from PyPDF2 import PdfReader
import pandas as pd
from PIL import Image
import pytesseract

load_dotenv()
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

logging.basicConfig(level=logging.INFO)

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'csv'}
UPLOAD_FOLDER = 'uploads/'

def handle_chat(user_input, chat_history, gpt_version='gpt-3.5-turbo'):
    try:
        response = client.chat.completions.create(model=gpt_version, messages=chat_history)
        logging.info(f'OpenAI response: {response}')
        reply = response.choices[0].message.content
        chat_history.append({"role": "assistant", "content": reply})
        return {'reply': reply, 'chat_history': chat_history}
    except Exception as e:
        logging.error(f'Error in handle_chat: {str(e)}')
        return {'reply': f'Error: {str(e)}', 'chat_history': chat_history}

def handle_file_upload(file_path):
    try:
        if file_path.endswith('.pdf'):
            text = extract_text_from_pdf(file_path)
        elif file_path.endswith('.csv'):
            text = extract_text_from_csv(file_path)
        elif file_path.endswith(('.txt', '.py', '.js', '.html', '.css', '.json', '.xml', '.sql', '.md')):
            text = extract_text_from_text_file(file_path)
        elif file_path.endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
            text = extract_text_from_image(file_path)
        else:
            return 'Unsupported file type.'
        return text
    except Exception as e:
        return f'Error processing file: {str(e)}'

def extract_text_from_pdf(pdf_path):
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

def extract_text_from_csv(csv_path):
    df = pd.read_csv(csv_path)
    return df.to_string()

def extract_text_from_text_file(file_path):
    with open(file_path, 'r') as file:
        return file.read()

def extract_text_from_image(image_path):
    try:
        text = pytesseract.image_to_string(Image.open(image_path))
        return text
    except Exception as e:
        return f'Error extracting text: {str(e)}'

def generate_image(prompt):
    try:
        response = client.images.generate(prompt=prompt, n=1, size="1024x1024")
        logging.info(f'Generated image URL: {response.data[0].url}')
        return response.data[0].url
    except Exception as e:
        logging.error(f'Error generating image: {str(e)}')
        return f'Error: {str(e)}'
