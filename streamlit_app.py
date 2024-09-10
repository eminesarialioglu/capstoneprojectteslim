import streamlit as st
import requests

# Page settings
st.set_page_config(layout="wide", page_title="Video/Audio Transcription and Translation")

# Custom CSS for styling
st.markdown("""
<style>
    .title {
        font-size: 40px;
        font-weight: bold;
        text-align: center;
        color: #333;
    }
    .instructions {
        background-color: #f0f8ff;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    .button {
        background-color: #4CAF50;  /* Green background */
        color: white;  /* White text color */
        font-size: 20px;
        padding: 10px 20px;
        border-radius: 5px;
    }
    .results {
        background-color: #e6f7ff;
        padding: 20px;
        border-radius: 10px;
        margin-top: 20px;
    }
    .stMultiSelect > div {
        background-color: #4CAF50;  /* Green background for multiselect */
        color: white;  /* White text color */
    }
</style>
""", unsafe_allow_html=True)

st.title("🎥 Video/Audio Transcription and Translation")

# Instructions on the sidebar
st.sidebar.header("Instructions")
st.sidebar.write("""
1. Upload a video or audio file (mp4, avi, mov, mp3, wav, or m4a format).
2. Select the languages for translation.
3. Click 'Transcribe and Translate' to process the file.
4. Records have been saved to the database.
""")

# File uploader
audio_files = st.file_uploader("Upload a video or audio file", type=["mp4", "avi", "mov", "mp3", "wav", "m4a"], accept_multiple_files=True)

# Language selection
languages = st.multiselect("Select languages for translation", [
    "English", "Spanish", "French", "German", "Italian", 
    "Portuguese", "Russian", "Chinese", "Japanese", "Korean", 
    "Arabic", "Turkish", "Hindi", "Bengali", "Vietnamese", 
    "Thai", "Polish", "Dutch", "Swedish", "Danish", 
    "Finnish", "Norwegian", "Czech", "Hungarian", "Romanian"
])

# List to store translations
current_translations = []

# Process button
if st.button("Transcribe and Translate", key="transcribe_button"):
    with st.spinner("Processing..."):
        progress_bar = st.progress(0)  # Start progress bar
        for idx, audio_file in enumerate(audio_files):
            files = {"videos": (audio_file.name, audio_file.getvalue(), audio_file.type)}
            data = {"languages": languages}

            # Send request to FastAPI
            response = requests.post("http://localhost:8000/process_video", files=files, data=data)

            # Update progress bar
            progress_bar.progress((idx + 1) / len(audio_files))

            if response.status_code == 200:
                st.success(f"{audio_file.name} translated successfully!")
                # Add translation to the list
                current_translations.append(response.json())
            else:
                st.error(f"Error occurred: {response.json()['detail']}")

# Display translations directly after processing
if current_translations:
    st.markdown("<div class='results'>", unsafe_allow_html=True)
    for translation in current_translations:
        st.write(f"**Video Name:** {translation['video_name']}")
        st.write(f"**Language:** {translation['language']}")
        st.write(f"**Translation:** {translation['translation']}")
        st.write(f"**SRT Link:** {translation['srt_link']}")
        st.write("---")  # Separator line
    st.markdown("</div>", unsafe_allow_html=True)
else:
    st.info("No current translations available.")
