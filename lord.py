from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
from docx import Document
from dotenv import load_dotenv
from deep_translator import GoogleTranslator
import google.generativeai as genai
from flask_cors import CORS
import smtplib
from email.mime.text import MIMEText
import os
import sys

# UTF-8 encoding for console output
sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = '/tmp/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Gemini API
api_key = os.getenv('GEMINI_API_KEY')
genai.configure(api_key=api_key)

# Email credentials
EMAIL_SENDER = os.getenv('EMAIL_SENDER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')


# Extract text from PDF
def extract_text_from_pdf(pdf_path):
    reader = PdfReader(pdf_path)
    return ''.join(page.extract_text() for page in reader.pages if page.extract_text())

# Extract text from Word document
def extract_text_from_word(docx_path):
    doc = Document(docx_path)
    return '\n'.join([para.text for para in doc.paragraphs])

# Summarize and suggest remedies using Gemini
def summarize_text(text, language='en'):
    try:
        if not text.strip():
            return "No text found to summarize."
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        input_prompt = (
            f"Summarize this medical report and provide medical suggestions or remedies:\n\n{text}\n\n"
            "Include:\n- Patient details\n- Medical conditions\n- Medications\n"
            "- Operations (if any)\n- Follow-up needs\n- Future health risks\n- Remedies or suggestions.\n"
            "Use bullet points. Keep it under 250 words. If not a medical report, inform the user."
        )
        response = model.generate_content([input_prompt])
        summary = response.text if response and response.text else "No summary available."

        # Translate if requested
        if language and language.lower() != 'en':
            summary = GoogleTranslator(source='auto', target=language).translate(summary)

        return summary
    except Exception as e:
        return f"Error during summarization: {str(e)}"

# Send email with summary
def send_summary_email(to_email, summary):
    try:
        msg = MIMEText(summary)
        msg['Subject'] = 'Your Medical Report Summary'
        msg['From'] = EMAIL_SENDER
        msg['To'] = to_email

        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        return str(e)

# Analyze uploaded file
@app.route('/analyze', methods=['POST'])
def analyze_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    filename = secure_filename(file.filename)
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)

    ext = os.path.splitext(filename)[1].lower()
    if ext == '.pdf':
        text = extract_text_from_pdf(file_path)
    elif ext in ['.doc', '.docx']:
        text = extract_text_from_word(file_path)
    elif ext == '.txt':
        text = file.read().decode('utf-8')
    else:
        return jsonify({"error": "Unsupported file format"}), 400

    # Get language and email from form
    language = request.form.get('language', 'en')
    email = request.form.get('email')

    # Generate summary
    summary = summarize_text(text, language)

    # Clean up file
    if os.path.exists(file_path):
        os.remove(file_path)

    # Optionally send email
    email_status = None
    if email:
        result = send_summary_email(email, summary)
        email_status = "Sent successfully" if result is True else f"Failed: {result}"

    return jsonify({'summary': summary, 'email_status': email_status})

# Home page
@app.route('/')
def index():
    return render_template('index2.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
