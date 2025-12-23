# youtube_summerzier
This project is an AI-powered YouTube Video Summarizer that automatically extracts, processes, and summarizes video transcripts into clear and concise text summaries. It helps users save time by understanding long videos in just a few seconds without watching the full content.
# 🎥 End-to-End YouTube Video Transcribe & Summarizer  
### Powered by Google Gemini Pro · Streamlit · NLP · GenAI

An **end-to-end Generative AI application** that automatically **extracts transcripts from YouTube videos**, processes them, and generates **high-quality, concise summaries** using **Google Gemini Pro**.  
Built with a clean UI, persistent history tracking, and production-style architecture.

> ⚡ This project demonstrates real-world GenAI usage — not just model calls, but a complete pipeline from user input → AI reasoning → storage → UI delivery.

---

## 🚀 Demo Highlights
- Paste a YouTube video link  
- Instantly fetch transcript  
- Generate an AI-powered summary  
- Save summaries automatically  
- Revisit history anytime  

---

## 🧠 Problem Statement
Long YouTube videos (lectures, podcasts, interviews, tech talks) are **time-consuming to consume**.  
Users want **fast, accurate summaries** without watching the entire video.

This project solves that by:
- Extracting spoken content
- Cleaning & structuring raw transcripts
- Using a **large language model** to generate meaningful summaries

---

## 🏗️ System Architecture

User → Streamlit UI
↓
YouTube URL Input
↓
Transcript Extraction (YouTube API)
↓
Text Preprocessing
↓
Google Gemini Pro (LLM)
↓
AI Summary Generation
↓
SQLite Storage (History)
↓
Final Output to User

---

## ✨ Key Features

- ✅ AI-powered YouTube video summarization  
- ✅ Google Gemini Pro LLM integration  
- ✅ Automatic transcript extraction  
- ✅ Clean and interactive Streamlit UI  
- ✅ Persistent summary history using SQLite  
- ✅ Environment-variable-based API security  
- ✅ Modular and scalable codebase  
- ✅ Real-world GenAI application structure  

---

## 🧠 Tech Stack

| Category | Tools |
|--------|------|
| Language | Python |
| UI | Streamlit |
| LLM | Google Gemini Pro |
| NLP | YouTube Transcript API |
| Database | SQLite |
| Config | python-dotenv |
| Visualization | Graphviz |
| Frameworks | LangChain (custom usage) |

---

## 📂 Project Structure

youtube-video-summarizer-gemini/
│
├── app.py # Main Streamlit application
├── requirements.txt # Project dependencies
├── FEATURES.md # Detailed feature list
├── langchain/ # Custom chains & logic
├── .gitignore # Ignored sensitive files
└── README.md # Project documentation

---

## ⚙️ Installation & Setup

### 1️⃣ Clone the Repository

git clone https://github.com/your-username/youtube-video-summarizer-gemini.git
cd youtube-video-summarizer-gemini
2️⃣ Create Virtual Environment (Recommended)
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

3️⃣ Install Dependencies
pip install -r requirements.txt

4️⃣ Configure Environment Variables

Create a .env file:

GOOGLE_API_KEY=your_gemini_api_key_here

▶️ Run the Application
streamlit run app.py


The app will launch in your browser 🚀

🧪 Example Use Cases

📚 Students summarizing long lectures

🎙 Podcast listeners extracting key insights

👨‍💻 Developers saving time on tech talks

📈 Researchers reviewing video-based content

🔮 Future Enhancements

🌍 Multi-language summarization

⏱ Timestamp-based summaries

🧠 RAG over transcript for Q&A

📄 Export summaries as PDF

☁️ Cloud deployment

🧑‍💻 Author

Burhanuddin Ghadiyal
Data Science & GenAI Enthusiast

🔗 GitHub: https://github.com/brh-n5105

🔗 LinkedIn: https://www.linkedin.com/in/burhanuddin-ghadiyali-a4178a279/
