from flask import Flask, render_template, request, send_file
import fitz
import os
import zipfile
import logging
import time
import shutil
import csv
from datetime import datetime

app = Flask(__name__)

# =========================
# FOLDER CONFIGURATION
# =========================

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
LOG_FOLDER = "logs"
HISTORY_FOLDER = "history"
ORGANIZED_FOLDER = "organized_pdfs"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(LOG_FOLDER, exist_ok=True)
os.makedirs(HISTORY_FOLDER, exist_ok=True)
os.makedirs(ORGANIZED_FOLDER, exist_ok=True)

# =========================
# HISTORY FILE
# =========================

HISTORY_FILE = "history/history.csv"

if not os.path.exists(HISTORY_FILE):

    with open(HISTORY_FILE, mode='w', newline='') as file:

        writer = csv.writer(file)

        writer.writerow([
            "Date",
            "File Name",
            "Status",
            "Remarks"
        ])

# =========================
# LOGGING
# =========================

logging.basicConfig(
    filename='logs/app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# =========================
# HISTORY FUNCTION
# =========================

def add_history(file_name, status, remarks):

    with open(HISTORY_FILE, mode='a', newline='') as file:

        writer = csv.writer(file)

        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            file_name,
            status,
            remarks
        ])

# =========================
# DOB MASK FUNCTION
# =========================

def hide_dob(input_pdf, output_pdf):

    try:

        logging.info(
            f"Processing started: {input_pdf}"
        )

        doc = fitz.open(input_pdf)

        dob_found = False
        masking_done = False

        for page_number, page in enumerate(doc):

            dob_fields = page.search_for("Date of Birth")

            for field in dob_fields:

                search_area = fitz.Rect(
                    field.x1 + 5,
                    field.y0 - 2,
                    field.x1 + 120,
                    field.y1 + 2
                )

                words = page.get_text("words")

                dob_words = []

                for word in words:

                    rect = fitz.Rect(word[:4])

                    if search_area.intersects(rect):

                        dob_words.append(word)

                if dob_words:

                    dob_found = True

                    x0 = min(w[0] for w in dob_words)
                    y0 = min(w[1] for w in dob_words)
                    x1 = max(w[2] for w in dob_words)
                    y1 = max(w[3] for w in dob_words)

                    dob_rect = fitz.Rect(
                        x0,
                        y0,
                        x1,
                        y1
                    )

                    page.draw_rect(
                        dob_rect,
                        color=(1,1,1),
                        fill=(1,1,1)
                    )

                    masking_done = True

        if masking_done:

            doc.save(output_pdf)

        else:

            shutil.copy(input_pdf, output_pdf)

        doc.close()

        return True

    except Exception as e:

        logging.error(
            f"Error processing PDF: {str(e)}"
        )

        return False

# =========================
# HOME PAGE
# =========================

@app.route("/")
def home():

    history_data = []

    if os.path.exists(HISTORY_FILE):

        with open(HISTORY_FILE, mode='r') as file:

            reader = csv.reader(file)

            next(reader, None)

            history_data = list(reader)

            history_data.reverse()

    return render_template(
        "index.html",
        history_data=history_data
    )

# =========================
# DOB MASK MODULE
# =========================

@app.route("/upload", methods=["POST"])
def upload():

    try:

        files = request.files.getlist("pdfs")

        if not files or files[0].filename == "":

            return """
                <h3>Please select PDF files</h3>
                <a href='/'>Go Back</a>
            """

        timestamp = str(int(time.time()))

        zip_filename = f"processed_pdfs_{timestamp}.zip"

        zip_path = os.path.join(
            OUTPUT_FOLDER,
            zip_filename
        )

        with zipfile.ZipFile(zip_path, "w") as zipf:

            for file in files:

                filename = f"{timestamp}_{file.filename}"

                input_path = os.path.join(
                    UPLOAD_FOLDER,
                    filename
                )

                output_path = os.path.join(
                    OUTPUT_FOLDER,
                    filename
                )

                file.save(input_path)

                result = hide_dob(
                    input_path,
                    output_path
                )

                if result:

                    add_history(
                        file.filename,
                        "SUCCESS",
                        "DOB masked successfully"
                    )

                    zipf.write(
                        output_path,
                        arcname=file.filename
                    )

                else:

                    add_history(
                        file.filename,
                        "FAILED",
                        "DOB masking failed"
                    )

        return send_file(
            zip_path,
            as_attachment=True
        )

    except Exception as e:

        logging.error(str(e))

        return """
            <h3>Error processing PDFs</h3>
            <a href='/'>Go Back</a>
        """

# =========================
# PDF FOLDER ORGANIZER
# =========================

@app.route("/organize", methods=["POST"])
def organize_pdfs():

    try:

        files = request.files.getlist("folder_pdfs")

        if not files or files[0].filename == "":

            return """
                <h3>Please select PDF files</h3>
                <a href='/'>Go Back</a>
            """

        timestamp = str(int(time.time()))

        zip_filename = f"organized_pdfs_{timestamp}.zip"

        zip_path = os.path.join(
            OUTPUT_FOLDER,
            zip_filename
        )

        with zipfile.ZipFile(zip_path, "w") as zipf:

            for file in files:

                original_filename = file.filename

                folder_name = os.path.splitext(
                    original_filename
                )[0]

                folder_path = os.path.join(
                    ORGANIZED_FOLDER,
                    folder_name
                )

                os.makedirs(
                    folder_path,
                    exist_ok=True
                )

                pdf_path = os.path.join(
                    folder_path,
                    original_filename
                )

                file.save(pdf_path)

                add_history(
                    original_filename,
                    "SUCCESS",
                    f"Folder created: {folder_name}"
                )

                zipf.write(
                    pdf_path,
                    arcname=f"{folder_name}/{original_filename}"
                )

        return send_file(
            zip_path,
            as_attachment=True
        )

    except Exception as e:

        logging.error(str(e))

        return """
            <h3>Error organizing PDFs</h3>
            <a href='/'>Go Back</a>
        """

# =========================
# RUN APP
# =========================

if __name__ == "__main__":
    
    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port
    )