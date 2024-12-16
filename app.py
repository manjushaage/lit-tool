from flask import Flask, request, render_template, jsonify, send_file, flash, redirect
from werkzeug.utils import secure_filename
import os
import fitz  # PyMuPDF for PDF manipulation
import pandas as pd
from datetime import datetime
import smtplib
from email.message import EmailMessage
from flashtext import KeywordProcessor
import shutil
from concurrent.futures import ThreadPoolExecutor
import zipfile
import io

# Flask setup
app = Flask(__name__)
app.secret_key = "yuyh wkou bitn bpoy"
app.config['UPLOAD_FOLDER_PDF'] = 'uploaded_pdfs'
app.config['UPLOAD_FOLDER_EXCEL'] = 'uploaded_keywords'
app.config['HIGHLIGHTED_FOLDER'] = 'highlighted_pdfs'
app.config['PREVIOUS_HIGHLIGHTED_FOLDER'] = 'previous_highlighted_pdfs'
app.config['KEYWORDS_FOLDER'] = 'keywords' 
app.config['ERROR_LOG_FOLDER'] = 'error_log'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'csv', 'xls', 'xlsx'}

# Ensure folders exist
os.makedirs(app.config['UPLOAD_FOLDER_PDF'], exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER_EXCEL'], exist_ok=True)
os.makedirs(app.config['HIGHLIGHTED_FOLDER'], exist_ok=True)
os.makedirs(app.config['PREVIOUS_HIGHLIGHTED_FOLDER'], exist_ok=True)
os.makedirs(app.config['KEYWORDS_FOLDER'], exist_ok=True)  
os.makedirs(app.config['ERROR_LOG_FOLDER'], exist_ok=True)

# Email configuration
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
EMAIL_USER = 'florian.urach@gmail.com'
EMAIL_PASSWORD = 'yuyh wkou bitn bpoy'

progress = {}  # Track progress for each file

# Utility Functions
def allowed_file(filename):
    result = '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']
    print(f"[DEBUG] Allowed file check for {filename}: {result}")
    return result

def log_error(error_message):
    print(f"[DEBUG] Logging error: {error_message}")
    log_file_path = os.path.join(app.config['ERROR_LOG_FOLDER'], 'error_log.txt')
    with open(log_file_path, 'a', encoding='utf-8') as log_file:
        log_file.write(f"{datetime.now()} - {error_message}\n")

def detect_japanese(text):
    """Detect if a given text contains Japanese characters."""
    for char in text:
        if '\u3040' <= char <= '\u30FF' or '\u4E00' <= char <= '\u9FFF':
            return True
    return False

def send_email(subject, body, recipient_email):
    try:
        print("[DEBUG] Preparing email...")
        msg = EmailMessage()
        msg.set_content(body)
        msg['Subject'] = subject
        msg['From'] = EMAIL_USER
        msg['To'] = recipient_email

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            print("[DEBUG] Logging into SMTP server...")
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            print("[DEBUG] Sending email...")
            server.send_message(msg)

        print("[DEBUG] Email sent successfully.")
    except Exception as e:
        error_message = f"Error sending email: {str(e)}"
        log_error(error_message)
        print(f"[DEBUG] {error_message}")

def clear_uploaded_files():
    """Clear out processed files from the uploaded_pdfs folder."""
    print("[DEBUG] Clearing uploaded files...")
    for file_name in os.listdir(app.config['UPLOAD_FOLDER_PDF']):
        file_path = os.path.join(app.config['UPLOAD_FOLDER_PDF'], file_name)
        if os.path.isfile(file_path):
            os.remove(file_path)
    print("[DEBUG] Uploaded files cleared.")

def move_old_highlighted_pdfs():
    """Move existing highlighted PDFs to the previous_highlighted_pdfs folder."""
    print("[DEBUG] Moving old highlighted PDFs...")
    for file_name in os.listdir(app.config['HIGHLIGHTED_FOLDER']):
        source_path = os.path.join(app.config['HIGHLIGHTED_FOLDER'], file_name)
        destination_path = os.path.join(app.config['PREVIOUS_HIGHLIGHTED_FOLDER'], file_name)
        if os.path.isfile(source_path):
            shutil.move(source_path, destination_path)
    print("[DEBUG] Old highlighted PDFs moved.")

def pre_load_keywords(keywords_folder):
    """Load keywords from a folder."""
    print("[DEBUG] Preloading keywords...")
    keyword_processor = KeywordProcessor(case_sensitive=False)
    keyword_color_map = {}

    # Standard keyword files and colors
    keyword_files_and_colors = {
        'drugs.csv': (0, 1, 0),        #green
        'patients.csv': (0, 0.9, 0.9), #light blue
        'SS_general AE terms.csv': (1, 0, 0)   #yellow
    }

    # Add split Disease Symptoms files (yellow)
    for i in range(1, 10):
        keyword_files_and_colors[f'Disease_Symptoms{i}.csv'] = (1, 1, 0)

    # Dynamically detect and add Japanese keyword files
    for file_name in os.listdir(keywords_folder):
        if file_name.endswith('_jp.csv'):
            print(f"[DEBUG] Found Japanese keyword file: {file_name}")
            base_name = file_name.replace('_jp.csv', '.csv')
            color = keyword_files_and_colors.get(base_name, (1, 0.5, 0))  # Use existing color or default
            keyword_files_and_colors[file_name] = color

    # Load keywords from all detected files
    for file_name, color in keyword_files_and_colors.items():
        file_path = os.path.join(keywords_folder, file_name)
        if os.path.exists(file_path):
            try:
                print(f"[DEBUG] Loading keywords from {file_name}...")
                with open(file_path, 'r', encoding='utf-8') as f:
                    for keyword in f:
                        keyword = keyword.strip()
                        if keyword:
                            keyword_processor.add_keyword(keyword)
                            keyword_color_map[keyword] = color
                print(f"[DEBUG] Keywords loaded from {file_name}.")
            except Exception as e:
                log_error(f"Error loading keywords from {file_name}: {e}")
        else:
            print(f"[DEBUG] Keyword file not found: {file_name}")

    return keyword_processor, keyword_color_map

    # Standard keyword files and colors
    # keyword_files_and_colors = {
    #     'drugs.csv': (0, 1, 0),
    #     'patients.csv': (0.2, 0.6, 1),
    #     'SS_general AE terms.csv': (1, 0, 0)
    # }

    # # Add split Disease Symptoms files (yellow)
    # for i in range(1, 10):
    #     keyword_files_and_colors[f'Disease_Symptoms{i}.csv'] = (1, 1, 0)

    # # Dynamically detect and add Japanese keyword files
    # for file_name in os.listdir(keywords_folder):
    #     if file_name.endswith('_jp.csv'):
    #         print(f"[DEBUG] Found Japanese keyword file: {file_name}")
    #         base_name = file_name.replace('_jp.csv', '.csv')
    #         color = keyword_files_and_colors.get(base_name, (1, 0.5, 0))  # Use existing color or default
    #         keyword_files_and_colors[file_name] = color

    # # Load keywords from all detected files
    # for file_name, color in keyword_files_and_colors.items():
    #     file_path = os.path.join(keywords_folder, file_name)
    #     if os.path.exists(file_path):
    #         try:
    #             print(f"[DEBUG] Loading keywords from {file_name}...")
    #             with open(file_path, 'r', encoding='utf-8') as f:
    #                 for keyword in f:
    #                     keyword = keyword.strip()
    #                     if keyword:
    #                         keyword_processor.add_keyword(keyword)
    #                         keyword_color_map[keyword] = color
    #             print(f"[DEBUG] Keywords loaded from {file_name}.")
    #         except Exception as e:
    #             log_error(f"Error loading keywords from {file_name}: {e}")
    #     else:
    #         print(f"[DEBUG] Keyword file not found: {file_name}")

    # return keyword_processor, keyword_color_map

def search_keywords_and_highlight(pdf_path, filename, keyword_processor, keyword_color_map):
    global progress
    print(f"[DEBUG] Starting keyword search for {filename}...")
    highlighted_pdf_path = os.path.join(app.config['HIGHLIGHTED_FOLDER'], filename)

    progress[filename] = 0
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        log_error(f"Error opening PDF {pdf_path}: {str(e)}")
        raise ValueError(f"Cannot process PDF {filename}. It may be corrupted or invalid.")

    total_pages = len(doc)
    is_japanese = False

    for page_num, page in enumerate(doc, start=1):
        progress[filename] = int((page_num / total_pages) * 100)
        print(f"[DEBUG] Processing {filename}: Page {page_num}/{total_pages} ({progress[filename]}% complete)")
        
        text = page.get_text()
        
        # Detect Japanese content in the document
        if page_num == 1:  # Check only the first page for performance
            is_japanese = detect_japanese(text)
            print(f"[DEBUG] Detected Japanese content: {is_japanese}")
        
        matches = keyword_processor.extract_keywords(text, span_info=True)
        for match, start, end in matches:
            color = keyword_color_map.get(match)
            instances = page.search_for(match)
            for inst in instances:
                highlight = page.add_highlight_annot(inst)
                highlight.set_colors(stroke=color)
                highlight.update()

    try:
        doc.save(highlighted_pdf_path, garbage=4, deflate=True)
        print(f"[DEBUG] Saved highlighted PDF: {highlighted_pdf_path}")
    except Exception as e:
        log_error(f"Error saving highlighted PDF {highlighted_pdf_path}: {str(e)}")
        raise ValueError(f"Could not save highlighted PDF for {filename}.")
    finally:
        doc.close()

    progress[filename] = 100
    print(f"[DEBUG] Finished processing {filename}.")
    return highlighted_pdf_path

    folder = app.config['UPLOAD_FOLDER_PDF']
    print(f"Checking folder: {folder}")

    if not os.path.exists(folder):
        print("Folder does not exist!")
        return "Folder does not exist!", 500

    pdf_files = [f for f in os.listdir(folder) if f.endswith('.pdf')]
    print(f"Filtered PDFs: {pdf_files}")

    return render_template('standard_search.html', pdfs=pdf_files)

def load_selected_keywords(keyword_file_paths):
    """Load keywords from a list of specific file paths."""
    keyword_processor = KeywordProcessor(case_sensitive=False)
    keyword_color_map = {}

    for file_path in keyword_file_paths:
        if os.path.exists(file_path):
            try:
                print(f"[DEBUG] Loading keywords from {file_path}...")
                with open(file_path, 'r', encoding='utf-8') as file:
                    for line in file:
                        keyword = line.strip()
                        if keyword:
                            keyword_processor.add_keyword(keyword)
                            keyword_color_map[keyword] = (1, 0.5, 0)  # Default color: orange
                print(f"[DEBUG] Keywords loaded from {file_path}.")
            except Exception as e:
                log_error(f"Error loading keywords from {file_path}: {e}")
        else:
            print(f"[DEBUG] Keyword file not found: {file_path}")

    return keyword_processor, keyword_color_map

def get_keyword_context(text, keyword, context_length=50):
    """Extract context around the keyword."""
    keyword_index = text.lower().find(keyword.lower())
    if keyword_index == -1:
        return None  # Keyword not found

    # Calculate start and end indices for context
    start_index = max(0, keyword_index - context_length)
    end_index = min(len(text), keyword_index + len(keyword) + context_length)

    # Extract and return the context
    return text[start_index:end_index].replace('\n', ' ').strip()





""" From here is all website functionality"""

# Routes
#Index page
@app.route('/')
def index():
    print("[DEBUG] Serving index page.")
    return render_template('index.html')

#Contact page
@app.route('/contact', methods=['GET', 'POST'])
def contact_page():
    print("[DEBUG] Serving contact page.")
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        subject = request.form.get('subject')
        message = request.form.get('message')

        print(f"[DEBUG] Contact form submission: Name={name}, Email={email}, Phone={phone}, Subject={subject}, Message={message}")

        if not name or not email or not message:
            flash("All required fields must be filled!", "error")
            print("[DEBUG] Contact form validation failed.")
            return render_template('contact.html')

        try:
            send_email(
                subject=f"Contact Form: {subject or 'No Subject'}",
                body=f"Name: {name}\nEmail: {email}\nPhone: {phone}\nMessage: {message}",
                recipient_email=EMAIL_USER,
            )
            flash("Your message has been sent successfully!", "success")
            print("[DEBUG] Contact form email sent successfully.")
        except Exception as e:
            log_error(f"Error sending contact email: {e}")
            flash("Failed to send your message.", "error")
            print(f"[DEBUG] Failed to send contact form email: {e}")

    return render_template('contact.html')

#Options page
@app.route('/options')
def options_page():
    print("[DEBUG] Serving options page.")
    return render_template('options.html')

#Specific Search page
@app.route('/specific_search', methods=['GET', 'POST'])
def specific_search():
    if request.method == 'GET':
        # List all available keyword files from both folders
        keyword_files = {
            'keywords': os.listdir(app.config['KEYWORDS_FOLDER']),
            'uploaded_keywords': os.listdir(app.config['UPLOAD_FOLDER_EXCEL'])
        }
        return render_template('specific_search.html', keyword_files=keyword_files)

    if request.method == 'POST':
        print("[DEBUG] Handling specific file search...")
        move_old_highlighted_pdfs()

        # List all available keyword files (needed for POST case too)
        keyword_files = {
            'keywords': os.listdir(app.config['KEYWORDS_FOLDER']),
            'uploaded_keywords': os.listdir(app.config['UPLOAD_FOLDER_EXCEL'])
        }

        # Get selected keywords from the form
        selected_keywords = request.form.getlist('selected_keywords')
        if not selected_keywords:
            return render_template(
                'specific_search.html',
                keyword_files=keyword_files,
                message='No keyword files selected.',
                results=[]
            )

        # Resolve paths for selected keyword files from both folders
        keyword_file_paths = []
        for keyword_file in selected_keywords:
            if os.path.exists(os.path.join(app.config['KEYWORDS_FOLDER'], keyword_file)):
                keyword_file_paths.append(os.path.join(app.config['KEYWORDS_FOLDER'], keyword_file))
            elif os.path.exists(os.path.join(app.config['UPLOAD_FOLDER_EXCEL'], keyword_file)):
                keyword_file_paths.append(os.path.join(app.config['UPLOAD_FOLDER_EXCEL'], keyword_file))

        if not keyword_file_paths:
            return render_template(
                'specific_search.html',
                keyword_files=keyword_files,
                message='No valid keyword files found.',
                results=[]
            )

        # Use load_selected_keywords for specific search
        keyword_processor, keyword_color_map = load_selected_keywords(keyword_file_paths)

        # Process uploaded PDFs
        uploaded_files = os.listdir(app.config['UPLOAD_FOLDER_PDF'])
        if not uploaded_files:
            return render_template(
                'specific_search.html',
                keyword_files=keyword_files,
                message='No PDF files to process.',
                results=[]
            )

        results = []
        for file in uploaded_files:
            file_path = os.path.join(app.config['UPLOAD_FOLDER_PDF'], file)
            try:
                search_keywords_and_highlight(
                    pdf_path=file_path,
                    filename=file,
                    keyword_processor=keyword_processor,
                    keyword_color_map=keyword_color_map
                )
                results.append({'file': file, 'status': 'Processed successfully'})
            except Exception as e:
                log_error(f"Error processing {file}: {e}")
                results.append({'file': file, 'status': 'Processing failed'})

        return render_template(
            'specific_search.html',
            keyword_files=keyword_files,
            message='File processing completed!',
            results=results
        )

# Quick Search page and functionality
@app.route('/quick_search', methods=['GET', 'POST'])
def quick_search():
    if request.method == 'POST':
        print("[DEBUG] quick_search route accessed")

        keyword = request.form.get('keyword', '').strip()
        if not keyword:
            return jsonify({'message': 'Keyword is empty', 'results': []})

        folder = os.path.abspath(app.config['UPLOAD_FOLDER_PDF'])
        print(f"[DEBUG] Searching in folder: {folder}")
        if not os.path.exists(folder):
            return jsonify({'message': 'Upload folder does not exist!', 'results': []})

        results = []
        for file_name in os.listdir(folder):
            if file_name.lower().endswith('.pdf'):
                file_path = os.path.join(folder, file_name)
                print(f"[DEBUG] Processing file: {file_name}")
                try:
                    with fitz.open(file_path) as doc:
                        for page_num, page in enumerate(doc, start=1):
                            text = page.get_text()
                            print(f"[DEBUG] Extracted text from {file_name}, Page {page_num}: {text[:500]}")
                            if keyword.lower() in text.lower():
                                results.append({
                                    'file': file_name,
                                    'page': page_num,
                                    'context': text[:100],  # First 100 characters as context
                                })
                except Exception as e:
                    print(f"[ERROR] Error processing {file_name}: {e}")

        if not results:
            return jsonify({'message': 'No matches found', 'results': []})

        return jsonify({'message': 'Search completed!', 'results': results})

    return render_template('quick_search.html')

#help page
@app.route('/help')
def help():
    print("[DEBUG] Serving help page.")
    return render_template('help.html')

#Standard search page AND pdf show list
@app.route('/standard_search')
def standard_search():
    try:
        # Code for uploaded PDFs
        folder = os.path.abspath(app.config['UPLOAD_FOLDER_PDF'])
        if not os.path.exists(folder):
            print(f"[DEBUG] Folder does not exist: {folder}")
            return "Folder does not exist!", 500

        pdf_files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f)) and f.lower().endswith('.pdf')]
        print(f"[DEBUG] Filtered PDFs: {pdf_files}")

        # Render the template with the list of PDFs
        return render_template('standard_search.html', pdfs=pdf_files)
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred: {e}")
        return "An unexpected error occurred.", 500
    
#Ai page
@app.route('/ai')
def ai():
    print("[DEBUG] Serving ai page.")
    return render_template('ai.html')

#Index page
@app.route('/future')
def future():
    print("[DEBUG] Serving future page.")
    return render_template('future.html')

#Add Keyword excel list page
@app.route('/add_keyword')
def add_keyword():
    print("[DEBUG] Serving add keyword page.")
    return render_template('add_keyword.html')

#Upload of excel list functionality
@app.route('/uploaded_keywords', methods=['POST'])
def upload_keywords():
    print("[DEBUG] Handling keyword file upload...")
    keyword_folder = os.path.join('uploaded_keywords')
    os.makedirs(keyword_folder, exist_ok=True)

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file part in the request!'})

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No selected file!'})

    if allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(keyword_folder, filename)
        file.save(file_path)
        print(f"[INFO] Uploaded keyword file: {filename}")
        return jsonify({'success': True, 'message': 'File uploaded successfully!', 'filename': filename})
    else:
        return jsonify({'success': False, 'message': f'Invalid file type: {file.filename}'})

#Upload pdfs at the index page functionality
@app.route('/uploaded_pdfs', methods=['POST'])
def upload_files():
    print("[DEBUG] Handling PDF file upload...")

    # Clear existing uploaded files before uploading new ones
    clear_uploaded_files()

    if 'files' not in request.files:
        return jsonify({'success': False, 'message': 'No file part in the request!'})

    files = request.files.getlist('files')
    uploaded_files = []
    for file in files:
        if allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER_PDF'], filename)
            file.save(file_path)
            uploaded_files.append(filename)
            print(f"[DEBUG] Uploaded file: {filename}")
        else:
            return jsonify({'success': False, 'message': f"Invalid file type: {file.filename}"})

    return jsonify({'success': True, 'message': 'Files uploaded successfully!', 'files': uploaded_files})

@app.route('/clear_uploaded_files', methods=['POST'])
def handle_clear_uploaded_files():
    """Handle the button click to clear uploaded files."""
    try:
        clear_uploaded_files()
        flash("Uploaded files have been cleared successfully.", "success")
    except Exception as e:
        flash(f"Error clearing uploaded files: {str(e)}", "error")
    return redirect(request.referrer)  # Redirect back to the same page

#Search button functionality on index page
@app.route('/search', methods=['POST'])
def search_files():
    print("[DEBUG] Handling file search...")
    move_old_highlighted_pdfs()
    keyword_processor, keyword_color_map = pre_load_keywords('keywords')  # Always use the `keywords` folder
    uploaded_files = os.listdir(app.config['UPLOAD_FOLDER_PDF'])

    print(f"[DEBUG] Uploaded files: {uploaded_files}")
    if not uploaded_files:
        print("[DEBUG] No files to process.")
        return jsonify({'message': 'No files to process', 'results': []})

    results = []
    for file in uploaded_files:
        file_path = os.path.join(app.config['UPLOAD_FOLDER_PDF'], file)
        try:
            highlighted_pdf_path = search_keywords_and_highlight(
                pdf_path=file_path,
                filename=file,
                keyword_processor=keyword_processor,
                keyword_color_map=keyword_color_map
            )
            results.append({'file': file, 'status': 'Processed successfully'})
        except Exception as e:
            log_error(f"Error processing {file}: {e}")
            results.append({'file': file, 'status': 'Processing failed'})

    return jsonify({'message': 'Files processed', 'results': results})

#Status bar and progress on index page
@app.route('/status/<filename>', methods=['GET'])
def get_status(filename):
    print(f"[DEBUG] Checking status for {filename}...")
    if filename in progress:
        return jsonify({'progress': progress[filename]})
    else:
        return jsonify({'progress': 0, 'message': 'File not found'}), 404
    
@app.route('/download_all_highlighted')
def download_all_highlighted():
    folder = app.config['HIGHLIGHTED_FOLDER']
    zip_filename = "highlighted_pdfs.zip"
    try:
        # Check if the folder exists and contains files
        if not os.path.exists(folder):
            print("[DEBUG] Highlighted folder does not exist.")
            return "Highlighted folder does not exist.", 500

        files = [f for f in os.listdir(folder) if f.endswith('.pdf')]
        if not files:
            print("[DEBUG] No PDF files in highlighted folder.")
            return "No files to download.", 500

        # Create a zip file in memory
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file in files:
                file_path = os.path.join(folder, file)
                print(f"[DEBUG] Adding {file_path} to zip.")
                zf.write(file_path, arcname=file)

        memory_file.seek(0)
        print("[DEBUG] Zip file created successfully.")
        return send_file(
            memory_file,
            as_attachment=True,
            download_name=zip_filename,
            mimetype='application/zip'
        )

    except Exception as e:
        print(f"[ERROR] Error creating zip file: {e}")
        return "An error occurred while preparing the download.", 500

if __name__ == '__main__':
    print("[DEBUG] Starting Flask application...")
    app.run(debug=True)
