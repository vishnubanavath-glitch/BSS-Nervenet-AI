import streamlit as st
import httpx
import json
import sys

# Configure Premium Theme Aesthetics
st.set_page_config(
    page_title="Enterprise AI Conversation Engine",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Customize styling with HSL colors and glassmorphism elements
st.markdown("""
<style>
    .reportview-container {
        background: #0e1117;
    }
    .metric-card {
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
    }
    .token-counter {
        font-family: monospace;
        color: #00ffcc;
    }
</style>
""", unsafe_allow_html=True)

API_BASE_URL = "http://127.0.0.1:8000/api"

# Helper functions to communicate with the Django REST API endpoints
def get_sessions():
    try:
        response = httpx.get(f"{API_BASE_URL}/sessions/", timeout=5.0)
        if response.status_code == 200:
            return response.json().get("sessions", [])
    except Exception:
        pass
    return []

def create_session(title=None):
    try:
        payload = {}
        if title:
            payload["title"] = title
        response = httpx.post(f"{API_BASE_URL}/sessions/", json=payload, timeout=5.0)
        if response.status_code == 201:
            return response.json()
    except Exception as e:
        st.error(f"Error creating session: {e}")
    return None

def get_session_details(session_id):
    try:
        response = httpx.get(f"{API_BASE_URL}/sessions/{session_id}/", timeout=5.0)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"Error loading session details: {e}")
    return None

def send_message(session_id, content, memory_updates=None):
    try:
        payload = {"content": content}
        if memory_updates:
            payload["memory_updates"] = memory_updates
        response = httpx.post(f"{API_BASE_URL}/sessions/{session_id}/messages/", json=payload, timeout=60.0)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error sending message: {response.text}")
    except Exception as e:
        st.error(f"Network error: {e}")
    return None

def delete_session(session_id):
    try:
        response = httpx.delete(f"{API_BASE_URL}/sessions/{session_id}/", timeout=5.0)
        if response.status_code == 200:
            return True
    except Exception as e:
        st.error(f"Error deleting session: {e}")
    return False

# Initialize Session State
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None

# Sidebar Content
st.sidebar.title("💬 Conversation Sessions")

# Fetch and display current list of active sessions
sessions = get_sessions()

# UI to create a new session
st.sidebar.subheader("New Session")
new_title = st.sidebar.text_input("Session Title", placeholder="e.g. Project Planner, Code Buddy", key="new_session_title_input")
if st.sidebar.button("➕ Create New Chat", use_container_width=True):
    new_sess = create_session(new_title if new_title.strip() else None)
    if new_sess:
        st.session_state.current_session_id = new_sess["session_id"]
        st.rerun()

st.sidebar.markdown("---")

# Select list for active sessions
if sessions:
    session_options = {s["session_id"]: f"{s['title']} ({s['session_id'][:8]})" for s in sessions}
    
    # Match selected session key
    default_index = 0
    if st.session_state.current_session_id in session_options:
        default_index = list(session_options.keys()).index(st.session_state.current_session_id)
        
    selected_sess_id = st.sidebar.selectbox(
        "Active Chats",
        options=list(session_options.keys()),
        format_func=lambda x: session_options[x],
        index=default_index
    )
    st.session_state.current_session_id = selected_sess_id
    
    # Add a session management drawer in the sidebar
    with st.sidebar.expander("⚙️ Manage Sessions"):
        for s in sessions:
            col1, col2 = st.columns([4, 1])
            # Shorten title display if too long
            disp_title = s["title"] if len(s["title"]) <= 18 else s["title"][:15] + "..."
            col1.write(disp_title)
            if col2.button("🗑️", key=f"del_{s['session_id']}", help=f"Delete '{s['title']}'"):
                if delete_session(s["session_id"]):
                    if st.session_state.current_session_id == s["session_id"]:
                        st.session_state.current_session_id = None
                    st.toast(f"Deleted chat '{s['title']}'")
                    st.rerun()
else:
    st.sidebar.info("No active chat sessions. Create one above to begin!")
    st.session_state.current_session_id = None

# Main content dashboard based on selected session
if st.session_state.current_session_id:
    details = get_session_details(st.session_state.current_session_id)
    if details:
        # Sidebar Metadata Display
        st.sidebar.subheader("Metadata")
        st.sidebar.caption(f"Session UUID: `{details['session_id']}`")
        st.sidebar.caption(f"Created: {details['created_at'][:19].replace('T', ' ')}")
        
        # Sidebar Delete Session
        if st.sidebar.button("🗑️ Delete Chat Session", type="primary", use_container_width=True):
            if delete_session(details['session_id']):
                st.session_state.current_session_id = None
                st.rerun()
                
        st.sidebar.markdown("---")
        
        # Sidebar Memory Inspector
        st.sidebar.subheader("🧠 Temporary Memory Context")
        st.sidebar.write("Isolated runtime context stored in memory:")
        st.sidebar.json(details.get("memory", {}))
        
        # Memory Updates Input form
        st.sidebar.markdown("**Inject Memory Updates (with next message):**")
        mem_key = st.sidebar.text_input("Memory Key", placeholder="e.g. user_first_name", key="mem_key")
        mem_val = st.sidebar.text_input("Memory Value", placeholder="e.g. John", key="mem_val")
        
        st.sidebar.markdown("---")
        
        # Sidebar Summary Inspector
        st.sidebar.subheader("📝 Conversation Summary")
        summary_text = details.get("summary")
        if summary_text:
            st.sidebar.info(summary_text)
        else:
            st.sidebar.write("No summary generated yet. Old history will be condensed once the token threshold is exceeded.")
            
        # Main Panel Headers
        st.title(f"Chat Session: {details['title'] or 'Untitled Session'}")
        
        # Display existing message history chronologically
        history = details.get("history", [])
        for msg in history:
            role = msg["role"]
            with st.chat_message("user" if role == "user" else "assistant"):
                st.markdown(msg["content"])
                
        # Send user message
        if prompt := st.chat_input("Type your message here..."):
            # Setup dynamic memory updates
            memory_updates = {}
            if mem_key.strip() and mem_val.strip():
                memory_updates[mem_key.strip()] = mem_val.strip()
                
            # Render user input instantly
            with st.chat_message("user"):
                st.markdown(prompt)
                
            # Process request through Django backend
            with st.spinner("Claude is thinking..."):
                response = send_message(
                    session_id=details['session_id'],
                    content=prompt,
                    memory_updates=memory_updates if memory_updates else None
                )
                
            if response:
                st.rerun()
else:
    # Fallback view if no session is active
    st.info("Please select an active chat session from the sidebar or create a new session above to begin.")
    
    # Verify Backend Status
    try:
        res = httpx.get(f"{API_BASE_URL}/sessions/", timeout=2.0)
        st.success("✅ Connected to the Django Conversation Engine backend.")
    except Exception:
        st.warning("⚠️ Could not connect to the backend server. Make sure the Django server is running via `python manage.py runserver` on port 8000.")
