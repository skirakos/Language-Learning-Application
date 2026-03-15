# Language Learning Application

A web-based language learning tool that allows users to upload images and extract vocabulary from them using OCR. The extracted words are saved to a personal vocabulary list, which users can review and quiz themselves on.

## Features

- **OCR-powered vocabulary extraction** — upload any image containing text and the app will extract the words automatically
- **Personal vocabulary storage** — extracted words are saved to a local SQLite database per user
- **Quiz/review mode** — practice and reinforce the vocabulary you've collected

## Tech Stack

- **Backend:** Python, Flask
- **OCR:** Python OCR library (Tesseract/pytesseract)
- **Database:** SQLite
- **Frontend:** HTML, CSS

## Getting Started

```bash
# Clone the repository
git clone https://github.com/skirakos/Language-Learning-Application.git
cd Language-Learning-Application

# Install dependencies
pip install flask pytesseract pillow

# Run database migration
python migrate.py

# Start the app
python app.py
```

Then open `http://localhost:5000` in your browser.


## About

Built as a university project. The idea came from the frustration of manually copying vocabulary from textbook images — automating that step with OCR made the learning workflow significantly faster.
