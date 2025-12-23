import streamlit as st
from dotenv import load_dotenv
import os
import google.generativeai as genai
from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import YouTubeTranscriptApi
from datetime import datetime
import json
import sqlite3
from pathlib import Path
import base64
from io import BytesIO
import re
import graphviz

# PDF generation imports
try:
    from fpdf import FPDF
    PDF_AVAILABLE = True
except:
    PDF_AVAILABLE = False

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# ==================== DATABASE SETUP ====================
def init_database():
    """Initialize SQLite database for history"""
    db_path = Path("summary_history.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT,
            video_url TEXT,
            title TEXT,
            summary TEXT,
            transcript TEXT,
            language TEXT,
            timestamps TEXT,
            created_at TIMESTAMP,
            is_favorite INTEGER DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()

def save_to_history(video_id, video_url, title, summary, transcript, language, timestamps):
    """Save summary to history"""
    conn = sqlite3.connect("summary_history.db")
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO summaries (video_id, video_url, title, summary, transcript, language, timestamps, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (video_id, video_url, title, summary, transcript, language, json.dumps(timestamps), datetime.now()))
    
    conn.commit()
    conn.close()

def get_history():
    """Retrieve all summaries from history"""
    conn = sqlite3.connect("summary_history.db")
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM summaries ORDER BY created_at DESC')
    rows = cursor.fetchall()
    conn.close()
    
    return rows

def toggle_favorite(summary_id):
    """Toggle favorite status"""
    conn = sqlite3.connect("summary_history.db")
    cursor = conn.cursor()
    
    cursor.execute('UPDATE summaries SET is_favorite = NOT is_favorite WHERE id = ?', (summary_id,))
    conn.commit()
    conn.close()

def delete_from_history(summary_id):
    """Delete a summary from history"""
    conn = sqlite3.connect("summary_history.db")
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM summaries WHERE id = ?', (summary_id,))
    conn.commit()
    conn.close()

# ==================== HELPER FUNCTIONS ====================
def extract_video_id(youtube_url):
    """Extract video ID from various YouTube URL formats"""
    try:
        parsed_url = urlparse(youtube_url)
        
        if parsed_url.hostname in ['www.youtube.com', 'youtube.com']:
            query_params = parse_qs(parsed_url.query)
            return query_params.get('v', [None])[0]
        elif parsed_url.hostname == 'youtu.be':
            return parsed_url.path[1:]
        else:
            return youtube_url.split("=")[1].split("&")[0]
    except:
        return youtube_url.split("=")[1].split("&")[0]

def extract_transcript_details(youtube_video_url):
    """Extract transcript with timestamps"""
    try:
        video_id = extract_video_id(youtube_video_url)
        
        if not video_id or len(video_id) != 11:
            raise Exception(f"Invalid video ID: '{video_id}'")
        
        transcript_text = ""
        detected_language = "Unknown"
        timestamps_data = []
        
        ytt_api = YouTubeTranscriptApi()
        transcript_list = ytt_api.list(video_id)
        
        try:
            transcript = transcript_list.find_transcript(['en'])
            detected_language = "English"
            if transcript.is_generated:
                detected_language = "English (Auto-generated)"
        except:
            try:
                available_transcripts = list(transcript_list)
                if available_transcripts:
                    transcript = available_transcripts[0]
                    detected_language = f"{transcript.language} ({transcript.language_code})"
                else:
                    raise Exception("No transcripts available")
            except:
                raise Exception("No transcripts available")
            
            if transcript.language_code != 'en' and transcript.is_translatable:
                try:
                    original_lang = transcript.language
                    transcript = transcript.translate('en')
                    detected_language = f"{original_lang} (Translated to English)"
                except:
                    pass
        
        fetched_transcript = transcript.fetch()
        
        # Extract text and timestamps
        for snippet in fetched_transcript:
            transcript_text += " " + snippet.text
            timestamps_data.append({
                'start': snippet.start,
                'duration': snippet.duration,
                'text': snippet.text
            })

        return transcript_text, detected_language, timestamps_data

    except Exception as e:
        raise e

def generate_gemini_content(transcript_text, prompt):
    """Generate content using Gemini"""
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt + transcript_text)
    return response.text

def extract_key_timestamps(transcript_text, timestamps_data):
    """Extract key moments using AI"""
    prompt = """Analyze this video transcript and identify 5-7 key moments or important topics discussed. 
    For each key moment, provide:
    1. A brief title (max 10 words)
    2. A one-sentence description
    
    Format your response as:
    TIMESTAMP: [title] - [description]
    
    Transcript: """
    
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt + transcript_text[:3000])  # Limit for performance
    
    return response.text

def answer_question(question, transcript_text):
    """Answer questions about the video using RAG"""
    prompt = f"""You are an intelligent AI assistant analyzing a YouTube video.
    
    Instructions:
    1. Answer the user's question primarily based on the provided Video Transcript.
    2. If the exact answer is not found in the transcript, use your own general knowledge to provide a relevant and helpful compatible answer.
    3. Do NOT say "I cannot answer this from the summary". Instead, provide the best possible answer derived from the context or your knowledge base.
    4. Keep the tone helpful, professional, and engaging.
    
    Video Transcript:
    {transcript_text}
    
    User Question: {question}
    
    Answer:"""
    
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    return response.text

def generate_mind_map_code(transcript_text):
    """Generate Graphviz DOT code for a mind map"""
def generate_mind_map_code(transcript_text):
    """Generate Graphviz DOT code for a mind map"""
    prompt = """
    Create a clean, simple Mind Map for this video. Output ONLY valid Graphviz DOT code.
    
    Layout Rules:
    1. Use 'rankdir=LR' (Left to Right) for easy reading.
    2. Central Node: The main topic (Shape: Double Circle, Color: Gold).
    3. Level 1 Nodes: Main Concepts (Shape: Box, Color: LightBlue).
    4. Level 2 Nodes: Key Details (Shape: Plain Text, Color: None).
    5. LIMIT LABELS: Maximum 2-3 words per node. No long sentences.
    6. Limit complexity: Max 5 main branches, max 3 sub-branches each.
    
    Structure:
    digraph MindMap {
        rankdir=LR;
        node [fontname="Arial"];
        edge [color="#B0BEC5"];
        // Nodes and Edges here...
    }
    
    Transcript:
    """
    
    model = genai.GenerativeModel("gemini-2.5-flash")
    # Use more context but rely on the model instructions for simplicity
    response = model.generate_content(prompt + transcript_text[:15000])
    
    # Clean up
    code = response.text.replace("```dot", "").replace("```graphviz", "").replace("```", "").strip()
    return code

def format_timestamp(seconds):
    """Convert seconds to MM:SS format"""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins:02d}:{secs:02d}"

# ==================== EXPORT FUNCTIONS ====================
def create_pdf(summary, video_url, language, timestamps_text=""):
    """Create PDF export"""
    if not PDF_AVAILABLE:
        return None
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    
    # Title
    pdf.cell(0, 10, "YouTube Video Summary", ln=True, align='C')
    pdf.ln(5)
    
    # Video URL
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 10, f"Video: {video_url}", ln=True)
    pdf.cell(0, 10, f"Language: {language}", ln=True)
    pdf.cell(0, 10, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
    pdf.ln(5)
    
    # Summary
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Summary:", ln=True)
    pdf.set_font("Arial", '', 10)
    
    # Handle text encoding
    summary_clean = summary.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 5, summary_clean)
    
    if timestamps_text:
        pdf.ln(5)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "Key Timestamps:", ln=True)
        pdf.set_font("Arial", '', 10)
        timestamps_clean = timestamps_text.encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 5, timestamps_clean)
    
    return pdf.output(dest='S').encode('latin-1')

def create_txt(summary, video_url, language, timestamps_text=""):
    """Create TXT export"""
    content = f"""YouTube Video Summary
{'='*50}

Video URL: {video_url}
Language: {language}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}

{'='*50}
SUMMARY
{'='*50}

{summary}
"""
    
    if timestamps_text:
        content += f"""
{'='*50}
KEY TIMESTAMPS
{'='*50}

{timestamps_text}
"""
    
    return content

def create_markdown(summary, video_url, language, timestamps_text=""):
    """Create Markdown export"""
    content = f"""# YouTube Video Summary

**Video URL:** {video_url}  
**Language:** {language}  
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

---

## Summary

{summary}
"""
    
    if timestamps_text:
        content += f"""
---

## Key Timestamps

{timestamps_text}
"""
    
    return content

def get_download_link(content, filename, file_label):
    """Generate download link"""
    if isinstance(content, str):
        b64 = base64.b64encode(content.encode()).decode()
        mime = "text/plain"
    else:
        b64 = base64.b64encode(content).decode()
        mime = "application/pdf"
    
    href = f'<a href="data:{mime};base64,{b64}" download="{filename}">{file_label}</a>'
    return href

# ==================== STREAMLIT UI ====================
def main():
    # Page config
    st.set_page_config(
        page_title="YouTube Summarizer Pro",
        page_icon="🎥",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize database
    init_database()
    
    # Custom CSS
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

        /* Force Dark Theme & Font */
        .stApp {
            background-color: #0F172A;
            font-family: 'Inter', sans-serif;
            color: #F8FAFC;
        }
        
        /* Sidebar Beautification */
        [data-testid="stSidebar"] {
            background-color: #1E293B;
            border-right: 1px solid #334155;
        }
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] label, [data-testid="stSidebar"] .stRadio div, [data-testid="stSidebar"] p {
            color: #F8FAFC !important;
        }

        /* Inputs & Selectboxes */
        .stTextInput input, .stSelectbox div[data-baseweb="select"] > div, div[data-baseweb="input"] > div {
            color: #F8FAFC !important;
            background-color: #334155 !important;
            border-color: #475569 !important;
        }
        /* Buttons - Fix Visibility */
        .stButton button {
            color: #FFFFFF !important;
            border-color: #475569 !important; 
        }
        .stButton button:hover {
            border-color: #3B82F6 !important;
            color: #FFFFFF !important;
        }

        /* Main Header */
        .main-header {
            font-family: 'Inter', sans-serif;
            font-size: 3.5rem;
            font-weight: 800;
            background: linear-gradient(120deg, #60A5FA, #2DD4BF);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-align: center;
            margin-bottom: 2rem;
            letter-spacing: -1px;
            text-shadow: 0 4px 10px rgba(96, 165, 250, 0.2);
        }

        /* Stats Box */
        .stats-box {
            background: #1E293B;
            padding: 1.5rem;
            border-radius: 16px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            text-align: center;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            border: 1px solid #334155;
            margin-bottom: 1rem;
        }
        .stats-box:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
            border-color: #3B82F6;
        }
        .stats-box h3 {
            margin: 0;
            color: #94A3B8;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-weight: 600;
        }
        .stats-box p {
            font-size: 1.5rem;
            font-weight: 700;
            color: #F8FAFC;
            margin: 0.5rem 0 0 0;
        }

        /* Timestamp Box */
        .timestamp-box {
            background: #1E293B;
            padding: 1.25rem;
            border-radius: 12px;
            margin: 0.75rem 0;
            border-left: 4px solid #3B82F6;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            font-size: 0.95rem;
            line-height: 1.6;
            color: #F8FAFC;
        }

        /* Chat Message */
        .chat-message {
            background: #1E293B;
            padding: 1.5rem;
            border-radius: 16px;
            margin: 1rem 0;
            border: 1px solid #334155;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            position: relative;
            color: #F8FAFC;
        }
        .chat-message::before {
            content: '🤖 AI Assistant';
            position: absolute;
            top: -10px;
            left: 20px;
            background: #3B82F6;
            color: white;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        
        /* User Message */
        .user-message {
            background: #334155;
            padding: 1.5rem;
            border-radius: 16px;
            margin: 1rem 0;
            border: 1px solid #475569;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            position: relative;
            color: #F8FAFC;
        }
        .user-message::before {
            content: '👤 You';
            position: absolute;
            top: -10px;
            left: 20px;
            background: #64748B;
            color: white;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.title("🎥 Navigation")
        
        pages = ["📝 Summarize", "🗺️ Mind Map", "💬 Chat with Video", "📚 History", "ℹ️ About"]
        
        # Initialize page selection state
        if 'page_selection' not in st.session_state:
            st.session_state['page_selection'] = "📝 Summarize"
            
        # Determine current index
        try:
            current_index = pages.index(st.session_state['page_selection'])
        except ValueError:
            current_index = 0
            
        # Render sidebar navigation
        selected_page = st.radio("Go to", pages, index=current_index)
        
        # specific logic to handle manual navigation
        if selected_page != st.session_state['page_selection']:
            st.session_state['page_selection'] = selected_page
            st.rerun()
            
        page = st.session_state['page_selection']
        
        st.markdown("---")
        st.markdown("### ⚙️ Settings")
        summary_length = st.selectbox("Summary Length", ["Brief (150 words)", "Medium (250 words)", "Detailed (400 words)", "Extensive (800 words)"])
        summary_format = st.radio("Summary Format", ["Bullet Points", "Paragraphs"])
        show_timestamps = st.checkbox("Show Key Timestamps", value=True)
        
    # ==================== PAGE: SUMMARIZE ====================
    # ==================== PAGE: SUMMARIZE ====================
    if page == "📝 Summarize":
        st.markdown('<h1 class="main-header">🎥 YouTube Summarizer Pro</h1>', unsafe_allow_html=True)
        st.markdown("### Transform any YouTube video into detailed notes instantly!")
        
        # Use session state to persist input
        if 'url_input' not in st.session_state:
            st.session_state['url_input'] = ""
            
        youtube_link = st.text_input("🔗 Enter YouTube Video Link:", key="url_input", placeholder="https://www.youtube.com/watch?v=...")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            if youtube_link:
                try:
                    video_id = extract_video_id(youtube_link)
                    st.image(f"http://img.youtube.com/vi/{video_id}/0.jpg", use_column_width=True)
                except:
                    st.warning("Could not load video thumbnail")
        
        with col2:
            if youtube_link:
                st.markdown("### 📊 Quick Stats")
                st.markdown("""
                <div class="stats-box">
                    <h3>Status</h3>
                    <p>🎬 Video Ready</p>
                </div>
                """, unsafe_allow_html=True)
        
        if st.button("✨ Generate Summary", type="primary", use_container_width=True):
            if not youtube_link:
                st.error("Please enter a YouTube URL")
            else:
                try:
                    with st.spinner("🔄 Extracting transcript..."):
                        transcript_text, detected_language, timestamps_data = extract_transcript_details(youtube_link)
                    
                    # Determine word count based on selection
                    # Determine word count based on selection
                    word_counts = {
                        "Brief (150 words)": 150, 
                        "Medium (250 words)": 250, 
                        "Detailed (400 words)": 400,
                        "Extensive (800 words)": 800
                    }
                    word_count = word_counts[summary_length]
                    
                    # Format instruction
                    format_instruction = "in bullet points" if summary_format == "Bullet Points" else "in detailed paragraphs"
                    
                    prompt = f"""You are a YouTube video summarizer. Summarize the entire video and provide 
                    the important summary {format_instruction} within {word_count} words. The summary should always be in English, 
                    regardless of the original language. Please provide the summary of the text given here: """
                    
                    with st.spinner("🤖 Generating AI summary..."):
                        summary = generate_gemini_content(transcript_text, prompt)
                    
                    # Extract key timestamps if enabled
                    timestamps_text = ""
                    if show_timestamps:
                        with st.spinner("⏱️ Extracting key moments..."):
                            timestamps_text = extract_key_timestamps(transcript_text, timestamps_data)
                    
                    # Store results in session state for persistence
                    st.session_state['current_summary_data'] = {
                        'summary': summary,
                        'transcript_text': transcript_text,
                        'detected_language': detected_language,
                        'timestamps_data': timestamps_data,
                        'timestamps_text': timestamps_text,
                        'video_id': video_id,
                        'youtube_link': youtube_link,
                        'generated_at': datetime.now()
                    }
                    
                    # Also update chat context
                    st.session_state['current_transcript'] = transcript_text
                    st.session_state['current_video_url'] = youtube_link
                    
                    st.success("✅ Summary generated successfully!")
                    st.rerun() # Rerun to display data from state
                    
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
                    st.info("💡 Tips:\n- Ensure the video has captions/subtitles\n- Check the YouTube URL\n- Try a different video")

        # Display results from Session State if they exist
        if 'current_summary_data' in st.session_state and st.session_state['current_summary_data']['youtube_link'] == youtube_link:
            data = st.session_state['current_summary_data']
            
            # Stats
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(f"""
                <div class="stats-box">
                    <h3>Language</h3>
                    <p>{data['detected_language']}</p>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                word_count_actual = len(data['summary'].split())
                st.markdown(f"""
                <div class="stats-box">
                    <h3>Word Count</h3>
                    <p>{word_count_actual}</p>
                </div>
                """, unsafe_allow_html=True)
            with col3:
                read_time = max(1, word_count_actual // 200)
                st.markdown(f"""
                <div class="stats-box">
                    <h3>Read Time</h3>
                    <p>{read_time} min</p>
                </div>
                """, unsafe_allow_html=True)
            with col4:
                transcript_words = len(data['transcript_text'].split())
                st.markdown(f"""
                <div class="stats-box">
                    <h3>Transcript</h3>
                    <p>{transcript_words} words</p>
                </div>
                """, unsafe_allow_html=True)
            
            # Summary
            st.markdown("## 📋 Summary")
            st.write(data['summary'])
            
            # Timestamps
            if show_timestamps and data['timestamps_text']:
                st.markdown("## ⏱️ Key Timestamps")
                st.markdown(f'<div class="timestamp-box">{data["timestamps_text"]}</div>', unsafe_allow_html=True)
            
            # Export options
            st.markdown("## 📥 Export Options")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                txt_content = create_txt(data['summary'], data['youtube_link'], data['detected_language'], data['timestamps_text'])
                st.download_button(
                    label="📄 Download TXT",
                    data=txt_content,
                    file_name=f"summary_{data['video_id']}.txt",
                    mime="text/plain"
                )
            
            with col2:
                md_content = create_markdown(data['summary'], data['youtube_link'], data['detected_language'], data['timestamps_text'])
                st.download_button(
                    label="📝 Download Markdown",
                    data=md_content,
                    file_name=f"summary_{data['video_id']}.md",
                    mime="text/markdown"
                )
            
            with col3:
                if PDF_AVAILABLE:
                    pdf_content = create_pdf(data['summary'], data['youtube_link'], data['detected_language'], data['timestamps_text'])
                    if pdf_content:
                        st.download_button(
                            label="📕 Download PDF",
                            data=pdf_content,
                            file_name=f"summary_{data['video_id']}.pdf",
                            mime="application/pdf"
                        )
                else:
                    st.info("PDF export unavailable")
            
            with col4:
                if st.button("💾 Save to History"):
                    save_to_history(
                        data['video_id'], data['youtube_link'], f"Video {data['video_id']}", 
                        data['summary'], data['transcript_text'], data['detected_language'], data['timestamps_data']
                    )
                    st.success("Saved to history!")
    
    # ==================== PAGE: MIND MAP ====================
    elif page == "🗺️ Mind Map":
        st.markdown('<h1 class="main-header">🗺️ Visual Mind Map</h1>', unsafe_allow_html=True)
        st.markdown("### Visualize the key concepts and connections")
        
        if 'current_transcript' not in st.session_state:
            st.warning("⚠️ Please summarize a video first to generate a mind map!")
            st.info("Go to the 'Summarize' page and process a video.")
        else:
            if st.button("✨ Generate Mind Map", type="primary"):
                try:
                    with st.spinner("🧠 Visualizing content..."):
                        dot_code = generate_mind_map_code(st.session_state['current_transcript'])
                        st.session_state['mind_map_code'] = dot_code
                except Exception as e:
                    st.error(f"Failed to generate mind map: {e}")
            
            if 'mind_map_code' in st.session_state:
                st.graphviz_chart(st.session_state['mind_map_code'], use_container_width=True)
                
                st.info("💡 You can zoom and pan the diagram if it's large.")

    # ==================== PAGE: CHAT ====================
    elif page == "💬 Chat with Video":
        st.markdown('<h1 class="main-header">💬 Chat with Video</h1>', unsafe_allow_html=True)
        st.markdown("### Ask questions about the video content!")
        
        if 'current_transcript' not in st.session_state:
            st.warning("⚠️ Please summarize a video first to enable chat!")
            st.info("Go to the 'Summarize' page and process a video.")
        else:
            st.success(f"✅ Ready to chat about: {st.session_state.get('current_video_url', 'Current video')}")
            
            # Chat interface
            if 'chat_history' not in st.session_state:
                st.session_state['chat_history'] = []
            
            question = st.text_input("🤔 Ask a question about the video:", placeholder="What is the main topic of this video?")
            
            if st.button("🚀 Get Answer", type="primary"):
                if question:
                    with st.spinner("🤖 Thinking..."):
                        answer = answer_question(question, st.session_state['current_transcript'])
                        st.session_state['chat_history'].append({"q": question, "a": answer})
            
            # Display chat history
            if st.session_state['chat_history']:
                st.markdown("### 💭 Conversation History")
                for i, chat in enumerate(reversed(st.session_state['chat_history'])):
                    st.markdown(f'<div class="user-message">{chat["q"]}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="chat-message">{chat["a"]}</div>', unsafe_allow_html=True)
                    st.markdown("<br>", unsafe_allow_html=True)
                
                if st.button("🗑️ Clear Chat History"):
                    st.session_state['chat_history'] = []
                    st.rerun()
    
    # ==================== PAGE: HISTORY ====================
    elif page == "📚 History":
        st.markdown('<h1 class="main-header">📚 Summary History</h1>', unsafe_allow_html=True)
        
        history = get_history()
        
        if not history:
            st.info("📭 No summaries in history yet. Start by summarizing a video!")
        else:
            st.markdown(f"### Total Summaries: {len(history)}")
            
            for row in history:
                summary_id, video_id, video_url, title, summary, transcript, language, timestamps, created_at, is_favorite = row
                
                with st.expander(f"{'⭐' if is_favorite else '📹'} {title} - {created_at}"):
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        st.markdown(f"**URL:** {video_url}")
                        st.markdown(f"**Language:** {language}")
                        st.markdown(f"**Created:** {created_at}")
                    
                    with col2:
                        if st.button(f"{'⭐ Unfavorite' if is_favorite else '☆ Favorite'}", key=f"fav_{summary_id}"):
                            toggle_favorite(summary_id)
                            st.rerun()
                        
                        if st.button("🗑️ Delete", key=f"del_{summary_id}"):
                            delete_from_history(summary_id)
                            st.rerun()
                    
                    st.markdown("**Summary:**")
                    st.write(summary)
                    
                    # Load to chat
                    if st.button("💬 Load for Chat", key=f"chat_{summary_id}"):
                        st.session_state['current_transcript'] = transcript
                        st.session_state['current_video_url'] = video_url
                        st.session_state['chat_history'] = [] # Reset chat history for new video
                        st.session_state['page_selection'] = "💬 Chat with Video" # Switch page safe method
                        st.rerun()
    
    # ==================== PAGE: ABOUT ====================
    elif page == "ℹ️ About":
        st.markdown('<h1 class="main-header">ℹ️ About YouTube Summarizer Pro</h1>', unsafe_allow_html=True)
        
        st.markdown("""
        ### 🚀 Features
        
        - **📝 AI-Powered Summaries**: Get concise summaries of any YouTube video
        - **💬 Interactive Q&A**: Ask questions about video content
        - **⏱️ Key Timestamps**: Automatically extract important moments
        - **📥 Multiple Export Formats**: Download as PDF, TXT, or Markdown
        - **📚 History Management**: Save and organize your summaries
        - **🌍 Multi-Language Support**: Handles videos in any language
        - **⭐ Favorites**: Bookmark important summaries
        
        ### 🛠️ Technology Stack
        
        - **AI Model**: Google Gemini 2.5 Flash
        - **Framework**: Streamlit
        - **Database**: SQLite
        - **Transcript API**: YouTube Transcript API
        
        ### 📖 How to Use
        
        1. **Summarize**: Enter a YouTube URL and generate a summary
        2. **Chat**: Ask questions about the video content
        3. **Export**: Download summaries in your preferred format
        4. **Save**: Store summaries in history for later reference
        
        ### 💡 Tips
        
        - Ensure videos have captions/subtitles enabled
        - Use the chat feature for deeper understanding
        - Organize summaries with favorites
        - Export summaries for offline access
        
        ---
        
        Made with ❤️ using Google Gemini AI
        """)

if __name__ == "__main__":
    main()
