import random
import spacy
import os
import io
from flask import Flask, render_template, request, send_file
import PyPDF2
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"

nlp = spacy.load("en_core_web_sm")

# -----------------------------
# PDF Text Extraction
# -----------------------------
def extract_text_from_pdf(pdf_file):
    text = ""
    reader = PyPDF2.PdfReader(pdf_file)
    for page in reader.pages:
        if page.extract_text():
            text += page.extract_text() + " "
    return text

# -----------------------------
# Distractor Generator
# -----------------------------
def generate_distractors(answer, keywords):
    distractors = [kw for kw in keywords if kw != answer]
    random.shuffle(distractors)
    return distractors[:3]

# -----------------------------
# Quiz Generator (Improved)
# -----------------------------
def generate_quiz(text, q_type="MCQ", difficulty="easy"):
    if not text.strip():
        return []

    doc = nlp(text)
    sentences = [s.text.strip() for s in doc.sents if len(s.text.split()) > 5]

    # Difficulty filtering
    if difficulty == "easy":
        sentences = [s for s in sentences if len(s.split()) <= 12]
    elif difficulty == "medium":
        sentences = [s for s in sentences if 12 < len(s.split()) <= 20]
    else:
        sentences = [s for s in sentences if len(s.split()) > 20]

    questions = []
    keywords = []

    for sent in sentences:
        doc_sent = nlp(sent)

        keywords += [ent.text for ent in doc_sent.ents]
        keywords += [chunk.text for chunk in doc_sent.noun_chunks]

    keywords = list(set(keywords))

    for sent in sentences:
        doc_sent = nlp(sent)

        candidates = [
            ent.text for ent in doc_sent.ents
            if ent.label_ in ["PERSON", "ORG", "GPE", "DATE"]
        ]

        if not candidates:
            candidates = [
                chunk.text for chunk in doc_sent.noun_chunks
                if len(chunk.text.split()) > 1
            ]

        if not candidates:
            continue

        answer = random.choice(candidates)
        question_text = sent.replace(answer, "_____")

        if q_type == "MCQ":
            options = generate_distractors(answer, keywords)
            options.append(answer)
            random.shuffle(options)
            questions.append((question_text, answer, options))

        elif q_type == "Fill-in":
            questions.append((question_text, answer, []))

        elif q_type == "T-F":
            questions.append((sent, random.choice(["True", "False"]), ["True", "False"]))

    return questions

# -----------------------------
# Routes
# -----------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    quiz = []

    if request.method == "POST":
        q_type = request.form["q_type"]
        difficulty = request.form["difficulty"]
        text = request.form.get("text", "")

        file = request.files.get("file")
        if file and file.filename.endswith(".pdf"):
            text = extract_text_from_pdf(file)

        quiz = generate_quiz(text, q_type, difficulty)

    return render_template("index.html", quiz=quiz)

# -----------------------------
# Export to PDF
# -----------------------------
@app.route("/export_pdf", methods=["POST"])
def export_pdf():
    quiz_text = request.form.get("quiz_data", "")
    buffer = io.BytesIO()

    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    x, y = 40, height - 40

    for line in quiz_text.split("\n"):
        if y < 40:
            c.showPage()
            y = height - 40
        c.drawString(x, y, line)
        y -= 14

    c.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="quiz.pdf",
        mimetype="application/pdf"
    )

if __name__ == "__main__":
    app.run(debug=True)
