from pdf_extractor import extract_text_from_pdf
from question_generator import generate_questions

def main():
    pdf_path = "textbook.pdf"  # Put your PDF in same folder
    
    print("Extracting text from PDF...")
    text = extract_text_from_pdf(pdf_path)
    print(f"Extracted {len(text)} characters")
    
    print("\nGenerating questions...")
    questions = generate_questions(text, num_questions=10)
    
    print("\n" + "="*50)
    print(questions)
    print("="*50)
    
    with open("generated_questions.txt", "w", encoding="utf-8") as f:
        f.write(questions)

if __name__ == "__main__":
    main()

