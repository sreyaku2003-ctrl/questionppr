import streamlit as st
import PyPDF2
import json
from groq import Groq
import io

# Add your Groq API key here
from dotenv import load_dotenv
import os
load_dotenv()

# Get API key from environment variable (more secure for Render)
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

def extract_text_from_pdf(pdf_file):
    """Extract text from uploaded PDF file using multiple methods"""
    text = ""
    
    # Method 1: Try pdfplumber (most reliable)
    try:
        import pdfplumber
        pdf_file.seek(0)
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"
        if text.strip():
            st.success(f"✅ Extracted text using pdfplumber ({len(text)} characters)")
            return text
    except ImportError:
        st.warning("pdfplumber not installed. Trying other methods...")
    except Exception as e:
        st.warning(f"pdfplumber failed: {str(e)[:100]}")
    
    # Method 2: Try pymupdf (fitz) - very robust
    try:
        import fitz  # PyMuPDF
        pdf_file.seek(0)
        pdf_bytes = pdf_file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_text = page.get_text()
            if page_text:
                text += page_text + "\n\n"
        doc.close()
        if text.strip():
            st.success(f"✅ Extracted text using PyMuPDF ({len(text)} characters)")
            return text
    except ImportError:
        st.warning("PyMuPDF not installed. Trying other methods...")
    except Exception as e:
        st.warning(f"PyMuPDF failed: {str(e)[:100]}")
    
    # Method 3: Try pypdf with recovery mode
    try:
        from pypdf import PdfReader
        pdf_file.seek(0)
        pdf_reader = PdfReader(pdf_file, strict=False)
        for page_num, page in enumerate(pdf_reader.pages):
            try:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"
            except:
                continue
        if text.strip():
            st.success(f"✅ Extracted text using pypdf ({len(text)} characters)")
            return text
    except ImportError:
        pass
    except Exception as e:
        st.warning(f"pypdf failed: {str(e)[:100]}")
    
    # Method 4: Try PyPDF2 with lenient settings
    try:
        import PyPDF2
        pdf_file.seek(0)
        pdf_reader = PyPDF2.PdfReader(pdf_file, strict=False)
        for page_num in range(len(pdf_reader.pages)):
            try:
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"
            except:
                continue
        if text.strip():
            st.success(f"✅ Extracted text using PyPDF2 ({len(text)} characters)")
            return text
    except Exception as e:
        st.warning(f"PyPDF2 failed: {str(e)[:100]}")
    
    # Method 5: Try pdf2image + pytesseract (OCR for scanned PDFs)
    try:
        from pdf2image import convert_from_bytes
        import pytesseract
        from PIL import Image
        
        pdf_file.seek(0)
        pdf_bytes = pdf_file.read()
        
        st.info("🔍 Attempting OCR (this may take a minute)...")
        images = convert_from_bytes(pdf_bytes, first_page=1, last_page=10)  # Limit to first 10 pages
        
        for i, image in enumerate(images):
            st.info(f"Processing page {i+1}/{len(images)}...")
            page_text = pytesseract.image_to_string(image)
            if page_text:
                text += page_text + "\n\n"
        
        if text.strip():
            st.success(f"✅ Extracted text using OCR ({len(text)} characters)")
            return text
    except ImportError:
        st.warning("OCR libraries not installed. Cannot process scanned PDFs.")
    except Exception as e:
        st.warning(f"OCR failed: {str(e)[:100]}")
    
    if not text.strip():
        st.error("❌ Could not extract text from PDF using any method.")
        st.info("""
        **Possible solutions:**
        1. Your PDF might be corrupted or password-protected
        2. Try converting your PDF using online tools (smallpdf.com, ilovepdf.com)
        3. Install OCR libraries: `pip install pytesseract pdf2image`
        4. For Windows: Install Tesseract from https://github.com/UB-Mannheim/tesseract/wiki
        5. Try a different PDF file
        """)
        return None
    
    return text

def extract_chapter_content(full_text, chapter_num):
    """Extract specific chapter content from the full text"""
    import re
    pattern = rf"chapter\s*{chapter_num}[^\w]*(.+?)(?=chapter\s*\d|$)"
    match = re.search(pattern, full_text, re.IGNORECASE | re.DOTALL)
    
    if match:
        return match.group(0)[:8000]  # Limit to 8000 chars
    return full_text[:8000]  # Return first 8000 chars if chapter not found

def generate_questions(chapter_content, chapter_num, marks_config, difficulty_config):
    """Generate questions using Groq API"""
    
    total_marks = sum(marks_config.values())
    total_questions = sum(difficulty_config.values())
    
    prompt = f"""You are an expert educator creating a question paper. Analyze Chapter {chapter_num} from the textbook content below and generate high-quality, intelligent questions.

TEXTBOOK CONTENT:
{chapter_content}

SPECIFICATIONS:
- 1-mark questions: {marks_config['one']} (MCQs with 4 options, mark correct with *)
- 3-mark questions: {marks_config['three']} (short answer, definitions, explanations)
- 5-mark questions: {marks_config['five']} (long answer, derivations, analytical)

DIFFICULTY DISTRIBUTION (across all marks):
- Easy: {difficulty_config['easy']} questions (basic recall, definitions)
- Medium: {difficulty_config['medium']} questions (application, understanding)
- Hard: {difficulty_config['hard']} questions (analysis, synthesis, evaluation)

IMPORTANT REQUIREMENTS:
1. Generate EXACTLY the specified number of questions for each mark category
2. Distribute difficulty levels as specified
3. Questions must be based ONLY on the chapter content provided
4. Make questions intelligent, testing deep understanding not just memorization
5. For 1-mark: Use MCQs with 4 options (mark correct answer with *)
6. For 3-mark: Ask "explain", "differentiate", "describe" type questions
7. For 5-mark: Include "derive", "analyze", "evaluate", "compare and contrast"
8. Ensure questions cover different topics within the chapter

Return ONLY valid JSON (no markdown, no explanations):
{{
  "paper": {{
    "chapter": "{chapter_num}",
    "totalMarks": {total_marks},
    "sections": [
      {{
        "marks": 1,
        "questions": [
          {{
            "question": "question text",
            "difficulty": "easy/medium/hard",
            "type": "MCQ",
            "options": ["A) option1", "B) option2", "C) option3 *", "D) option4"],
            "topic": "specific topic"
          }}
        ]
      }},
      {{
        "marks": 3,
        "questions": [
          {{
            "question": "question text",
            "difficulty": "easy/medium/hard",
            "type": "Short Answer",
            "topic": "specific topic"
          }}
        ]
      }},
      {{
        "marks": 5,
        "questions": [
          {{
            "question": "question text",
            "difficulty": "easy/medium/hard",
            "type": "Long Answer",
            "topic": "specific topic"
          }}
        ]
      }}
    ]
  }}
}}"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=4000
        )
        
        content = response.choices[0].message.content
        
        # Extract JSON from response
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            return json.loads(json_match.group(0))
        else:
            st.error("Could not parse response from AI")
            return None
            
    except Exception as e:
        st.error(f"Error generating questions: {str(e)}")
        return None

def format_question_paper(paper_data):
    """Format question paper for display and download"""
    output = f"""
{'='*70}
                        QUESTION PAPER
                        Chapter {paper_data['chapter']}
                    Total Marks: {paper_data['totalMarks']}
{'='*70}

"""
    
    for idx, section in enumerate(paper_data['sections']):
        output += f"\nSECTION {idx + 1}: {section['marks']}-MARK QUESTIONS\n"
        output += f"{'-'*70}\n\n"
        
        for q_idx, question in enumerate(section['questions']):
            output += f"Q{q_idx + 1}. {question['question']}\n"
            output += f"    [{section['marks']} marks] [{question['difficulty'].upper()}]\n"
            
            if question.get('topic'):
                output += f"    Topic: {question['topic']}\n"
            
            if question.get('type') == 'MCQ' and question.get('options'):
                for option in question['options']:
                    output += f"    {option}\n"
            
            output += f"    Type: {question.get('type', 'N/A')}\n\n"
    
    return output

# Streamlit UI
def main():
    st.set_page_config(page_title="AI Question Paper Generator", page_icon="📚", layout="wide")
    
    st.title("📚 AI Question Paper Generator")
    st.markdown("*Powered by Groq AI (Llama 3.3 70B)*")
    
    # Installation guide in expander
    with st.expander("📦 Installation Guide", expanded=False):
        st.markdown("""
        ### Basic Installation (try this first):
        ```bash
        pip install streamlit groq PyMuPDF pdfplumber
        ```
        
        ### Full Installation (with OCR support for scanned PDFs):
        ```bash
        pip install streamlit groq PyMuPDF pdfplumber pytesseract pdf2image
        ```
        
        ### For Windows OCR Support:
        1. Download Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
        2. Install and add to PATH
        
        ### Run the app:
        ```bash
        streamlit run app.py
        ```
        
        **Recommended:** PyMuPDF (fitz) is the most robust library for PDF extraction.
        """)
        st.info("💡 The app tries 5 different methods to extract text from your PDF!")
    
    # Check if API key is set
    if GROQ_API_KEY == "gsk_your_api_key_here":
        st.error("⚠️ Please add your Groq API key in the code (line 8)")
        st.info("Get your free API key from: https://console.groq.com")
        return
    
    # Sidebar for inputs
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Input method selection
        input_method = st.radio(
            "📥 Choose Input Method",
            ["Upload PDF", "Paste Text Directly"],
            help="If PDF upload fails, paste your chapter text directly"
        )
        
        uploaded_file = None
        manual_text = None
        
        if input_method == "Upload PDF":
            uploaded_file = st.file_uploader("Upload Textbook (PDF)", type=['pdf'])
        else:
            manual_text = st.text_area(
                "Paste Chapter Text Here",
                height=200,
                placeholder="Paste the text content of your chapter here...",
                help="Copy text from your PDF viewer or word processor and paste it here"
            )
        
        # Chapter number
        chapter = st.text_input("Chapter Number", placeholder="e.g., 5 or 5.2")
        
        st.divider()
        
        # Marks configuration
        st.subheader("📊 Questions by Marks")
        marks_1 = st.number_input("1-Mark Questions", min_value=0, value=5, step=1)
        marks_3 = st.number_input("3-Mark Questions", min_value=0, value=5, step=1)
        marks_5 = st.number_input("5-Mark Questions", min_value=0, value=3, step=1)
        
        st.divider()
        
        # Difficulty configuration
        st.subheader("🎯 Difficulty Distribution")
        diff_easy = st.number_input("Easy Questions", min_value=0, value=5, step=1)
        diff_medium = st.number_input("Medium Questions", min_value=0, value=5, step=1)
        diff_hard = st.number_input("Hard Questions", min_value=0, value=3, step=1)
        
        st.divider()
        
        generate_btn = st.button("🚀 Generate Question Paper", type="primary", use_container_width=True)
    
    # Main content area
    if generate_btn:
        if input_method == "Upload PDF" and not uploaded_file:
            st.error("Please upload a PDF textbook")
            return
        
        if input_method == "Paste Text Directly" and not manual_text:
            st.error("Please paste chapter text")
            return
        
        if not chapter:
            st.error("Please enter chapter number")
            return
        
        marks_config = {'one': marks_1, 'three': marks_3, 'five': marks_5}
        difficulty_config = {'easy': diff_easy, 'medium': diff_medium, 'hard': diff_hard}
        
        if sum(marks_config.values()) == 0:
            st.error("Please specify at least one question type")
            return
        
        if sum(difficulty_config.values()) == 0:
            st.error("Please specify at least one difficulty level")
            return
        
        # Get text content
        chapter_content = None
        
        if input_method == "Upload PDF":
            with st.spinner("📖 Extracting text from PDF..."):
                full_text = extract_text_from_pdf(uploaded_file)
                
            if not full_text:
                st.warning("⚠️ Could not extract text from PDF. Try 'Paste Text Directly' option instead.")
                return
            
            with st.spinner("🔍 Analyzing chapter content..."):
                chapter_content = extract_chapter_content(full_text, chapter)
        else:
            # Use manually pasted text
            chapter_content = manual_text[:8000]  # Limit to 8000 chars
            st.success(f"✅ Using manually pasted text ({len(chapter_content)} characters)")
        
        if not chapter_content or not chapter_content.strip():
            st.error("No content found. Please check your input.")
            return
        
        with st.spinner("🤖 Generating intelligent questions... This may take 20-30 seconds..."):
            result = generate_questions(chapter_content, chapter, marks_config, difficulty_config)
        
        if result and 'paper' in result:
            paper_data = result['paper']
            
            st.success("✅ Question paper generated successfully!")
            
            # Display paper
            st.header(f"Question Paper - Chapter {paper_data['chapter']}")
            st.subheader(f"Total Marks: {paper_data['totalMarks']}")
            
            for idx, section in enumerate(paper_data['sections']):
                st.markdown(f"### Section {idx + 1}: {section['marks']}-Mark Questions")
                
                for q_idx, question in enumerate(section['questions']):
                    with st.container():
                        col1, col2, col3 = st.columns([8, 1, 1])
                        
                        with col1:
                            st.markdown(f"**Q{q_idx + 1}.** {question['question']}")
                            if question.get('topic'):
                                st.caption(f"📌 Topic: {question['topic']}")
                        
                        with col2:
                            diff_color = {
                                'easy': '🟢',
                                'medium': '🟡',
                                'hard': '🔴'
                            }
                            st.markdown(f"{diff_color.get(question['difficulty'], '⚪')} {question['difficulty'].upper()}")
                        
                        with col3:
                            st.markdown(f"**{section['marks']}M**")
                        
                        if question.get('type') == 'MCQ' and question.get('options'):
                            for option in question['options']:
                                if '*' in option:
                                    st.markdown(f"<span style='color: green; font-weight: bold;'>{option}</span>", unsafe_allow_html=True)
                                else:
                                    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;{option}")
                        
                        st.caption(f"Type: {question.get('type', 'N/A')}")
                        st.divider()
            
            # Download button
            formatted_paper = format_question_paper(paper_data)
            st.download_button(
                label="📥 Download Question Paper",
                data=formatted_paper,
                file_name=f"question_paper_chapter_{paper_data['chapter']}.txt",
                mime="text/plain",
                use_container_width=True
            )

if __name__ == "__main__":
    main()