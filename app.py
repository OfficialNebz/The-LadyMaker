import streamlit as st
import os
import requests
import json
import time
from bs4 import BeautifulSoup
import google.generativeai as genai

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="THE LADYMAKER / INTELLIGENCE",
    page_icon="🧵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- GLOBAL CONSTANTS ---
NOTION_API_URL = "https://api.notion.com/v1/pages"

# --- 2. THE MONOCHROME ENGINE (CSS) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;600&family=Montserrat:wght@200;300;400;600&display=swap');

    html, body, .stApp { 
        background-color: #000000; 
        font-family: 'Montserrat', sans-serif !important; 
    }
    p, div, span, label, button, input, textarea, select {
        font-family: 'Montserrat', sans-serif;
    }
    h1, h2, h3, h4 { 
        font-family: 'Cormorant Garamond', serif !important; 
        letter-spacing: 1px; 
        color: #FFFFFF; 
    }
    .auth-card {
        background: transparent;
        border: 1px solid #FFFFFF;
        padding: 60px;
        text-align: center;
        margin-top: 50px;
    }
    [data-testid="stSidebar"] {
        background-color: #000000;
        border-right: 1px solid #333;
    }
    header {visibility: visible !important; background-color: transparent !important;}
    [data-testid="stDecoration"] {visibility: hidden;}

    div.stButton > button {
        width: 100%;
        background-color: transparent;
        color: #FFFFFF;
        border: 1px solid #FFFFFF;
        padding: 14px 24px;
        text-transform: uppercase;
        letter-spacing: 3px;
        transition: all 0.4s ease;
        border-radius: 0px;
    }
    div.stButton > button:hover {
        background-color: #FFFFFF;
        color: #000000;
        border: 1px solid #FFFFFF;
        transform: scale(1.01);
    }
    div[data-baseweb="input"] > div, textarea {
        background-color: #050505 !important;
        border: 1px solid #333 !important;
        color: #FFFFFF !important;
        text-align: center;
        border-radius: 0px;
    }
    div[data-baseweb="toast"] {
        background-color: #FFFFFF !important;
        color: #000000 !important;
    }
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- 3. SESSION STATE & SECRETS ---
if "authenticated" not in st.session_state: st.session_state.authenticated = False
if "results" not in st.session_state: st.session_state.results = None
if "p_name" not in st.session_state: st.session_state.p_name = ""
if "gen_id" not in st.session_state: st.session_state.gen_id = 0

api_key = st.secrets.get("GEMINI_API_KEY")
notion_token = st.secrets.get("NOTION_TOKEN")
notion_db_id = st.secrets.get("NOTION_DB_ID")

# --- 4. SIDEBAR ---
with st.sidebar:
    st.markdown("### ATELIER CONTROL")
    st.caption("The Ladymaker System v3.2 (Production)")
    if st.button("🔄 RESET SYSTEM"):
        st.session_state.clear()
        st.rerun()


# --- 5. AUTHENTICATION ---
def login_screen():
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<br><br><br><br>", unsafe_allow_html=True)
        with st.container():
            st.markdown('<div class="auth-card">', unsafe_allow_html=True)
            st.markdown("<h1 style='text-align: center; margin:0; font-size: 42px;'>THE LADYMAKER</h1>",
                        unsafe_allow_html=True)
            st.markdown(
                "<p style='text-align: center; font-size: 10px; letter-spacing: 4px; color: #888; margin-top: 10px; margin-bottom: 40px;'>INTELLIGENCE ACCESS</p>",
                unsafe_allow_html=True)

            SYSTEM_KEY = "neb123"
            password = st.text_input("PASSWORD", type="password", label_visibility="collapsed", placeholder="ENTER KEY")
            st.write("##")

            if st.button("UNLOCK ATELIER"):
                if password == SYSTEM_KEY:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("⚠️ ACCESS DENIED")
            st.markdown('</div>', unsafe_allow_html=True)


if not st.session_state.authenticated:
    login_screen()
    st.stop()


# --- 6. CORE LOGIC ---

def scrape_website(target_url):
    if "theladymaker.com" not in target_url:
        return None, "❌ ERROR: INVALID DOMAIN. Locked to The Ladymaker."

    headers = {'User-Agent': 'Mozilla/5.0'}
    clean_url = target_url.split('?')[0]
    json_url = f"{clean_url}.json"
    title = "Ladymaker Piece"
    desc_text = ""

    # Strategy 1: JSON
    try:
        # TIMEOUT OPTIMIZED TO 5S
        r = requests.get(json_url, headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json().get('product', {})
            title = data.get('title', title)
            raw_html = data.get('body_html', "")
            soup = BeautifulSoup(raw_html, 'html.parser')
            desc_text = soup.get_text(separator="\n", strip=True)
    except:
        pass

    # Strategy 2: HTML
    if not desc_text:
        try:
            # TIMEOUT OPTIMIZED TO 5S
            r = requests.get(target_url, headers=headers, timeout=5)
            if r.status_code != 200: return None, f"❌ SITE ERROR: {r.status_code}"
            soup = BeautifulSoup(r.content, 'html.parser')
            if soup.find('h1'): title = soup.find('h1').text.strip()

            main_block = soup.find('div', class_='product-description') or \
                         soup.find('div', class_='rte') or \
                         soup.find('div', id='description')

            if main_block: desc_text = main_block.get_text(separator="\n", strip=True)
        except Exception as e:
            return None, f"Scrape Error: {str(e)}"

    if not desc_text: return title, "[NO TEXT FOUND. PLEASE INPUT MANUALLY]"

    clean_lines = []
    for line in desc_text.split('\n'):
        upper = line.upper()
        if any(x in upper for x in ["SHIPPING", "DELIVERY", "RETURNS", "SIZE GUIDE", "WHATSAPP"]): continue
        if len(line) > 5: clean_lines.append(line)
    return title, "\n".join(clean_lines[:30])


def generate_campaign(product_name, description, key):
    genai.configure(api_key=key)
    # VERIFIED MODEL
    model = genai.GenerativeModel('gemini-flash-latest')

    prompt = f"""
    Role: Head of Brand Narrative for 'The Ladymaker'.
    Brand Voice: Structural elegance, architectural femininity, high-value Nigerian luxury.
    Product: {product_name}
    Specs: {description}

    TASK:
    1. Select TOP 3 DISTINCT personas.
    2. Write 3 separate captions.
    3. Write 1 "Master Hybrid" caption. 

    PERSONAS: Art Collector, Diplomat's Wife, Oil Exec, Modern Matriarch, Geneva Expat, PE Partner, Gallerist, Ikoyi Hostess.

    Output Format (JSON Array only):
    [
        {{"persona": "Persona Name 1", "post": "Caption 1..."}},
        ...
        {{"persona": "The Ladymaker Hybrid", "post": "The unified master caption..."}}
    ]
    """
    try:
        response = model.generate_content(prompt)
        txt = response.text
        if "```json" in txt: txt = txt.split("```json")[1].split("```")[0]
        return json.loads(txt.strip())
    except Exception as e:
        return [{"persona": "Error", "post": f"AI ERROR: {str(e)}"}]


def save_to_notion(p_name, post, persona, token, db_id):
    if not token or not db_id: return False, "Notion Secrets Missing"

    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    data = {
        "parent": {"database_id": db_id},
        "properties": {
            "Product Name": {"title": [{"text": {"content": str(p_name)}}]},
            "Persona": {"rich_text": [{"text": {"content": str(persona)}}]},
            "Generated Post": {"rich_text": [{"text": {"content": str(post)[:2000]}}]},
            "Status": {"status": {"name": "Draft"}}
        }
    }

    try:
        # TIMEOUT OPTIMIZED TO 5S
        response = requests.post(NOTION_API_URL, headers=headers, data=json.dumps(data), timeout=5)
        if response.status_code == 200:
            return True, "Success"
        else:
            error_msg = response.json().get('message', 'Unknown Error')
            return False, f"Notion Error {response.status_code}: {error_msg}"
    except Exception as e:
        return False, f"System Error: {str(e)}"


# --- 7. UI LAYOUT ---
st.title("THE LADYMAKER / INTELLIGENCE")

with st.expander("📖 SYSTEM MANUAL (CLICK TO OPEN)"):
    st.markdown("### OPERATIONAL GUIDE")
    st.markdown("---")
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.markdown("**STEP 1: SOURCE**\n\nGo to The Ladymaker site. Open product page.")
    with c2:
        try:
            st.image("Screenshot (455).png", use_container_width=True)
        except:
            st.warning("Image missing.")
    st.markdown("---")
    c3, c4 = st.columns([1, 1.5])
    with c3:
        st.markdown("**STEP 2: INJECT**\n\nPaste URL below.")
    with c4:
        try:
            st.image("Screenshot (457).png", use_container_width=True)
        except:
            pass

url_input = st.text_input("Product URL", placeholder="Paste Ladymaker URL...")

if st.button("GENERATE ASSETS", type="primary"):
    if not api_key:
        st.error("API Key Missing.")
    elif not url_input:
        st.error("Paste a URL first.")
    else:
        with st.spinner("Analyzing Silhouette & Structure..."):
            st.session_state.gen_id += 1
            p_name, p_desc = scrape_website(url_input)
            if p_name is None:
                st.error(p_desc)
            else:
                st.session_state.p_name = p_name
                st.session_state.results = generate_campaign(p_name, p_desc, api_key)

# --- 8. RESULTS DASHBOARD ---
if st.session_state.results:
    st.divider()
    st.subheader(st.session_state.p_name.upper())

    # --- BULK EXPORT BUTTON (OPTIMIZED) ---
    if st.button("💾 EXPORT CAMPAIGN TO NOTION", type="primary", use_container_width=True):
        if not notion_token or not notion_db_id:
            st.error("⚠️ Notion Secrets NOT configured!")
        else:
            success_count = 0
            with st.spinner("Initializing Notion Uplink..."):  # SPINNER ADDED
                progress_bar = st.progress(0)
                current_gen = st.session_state.gen_id

                for i, item in enumerate(st.session_state.results):
                    p_val = item.get('persona', '')
                    widget_key = f"editor_{i}_{current_gen}"
                    original_post = item.get('post', '')
                    final_post = st.session_state.get(widget_key, original_post)

                    if p_val and final_post:
                        s, m = save_to_notion(st.session_state.p_name, final_post, p_val, notion_token, notion_db_id)
                        if s: success_count += 1

                    # LAG REMOVED
                    progress_bar.progress((i + 1) / len(st.session_state.results))

            if success_count > 0:
                st.success(f"✅ UPLOAD COMPLETE: {success_count} Assets Sent.")
                time.sleep(1)
                st.rerun()

    st.markdown("---")

    # --- INDIVIDUAL EDITORS ---
    current_gen = st.session_state.gen_id
    for i, item in enumerate(st.session_state.results):
        persona = item.get('persona', 'Unknown')
        post = item.get('post', '')

        with st.container():
            c1, c2 = st.columns([0.75, 0.25])
            with c1:
                st.subheader(persona)
                edited_text = st.text_area(label=f"Edit {persona}", value=post, height=200,
                                           key=f"editor_{i}_{current_gen}", label_visibility="collapsed")
            with c2:
                st.write("##");
                st.write("##")
                # SPINNER ADDED TO SINGLE SAVE
                if st.button("SAVE SINGLE", key=f"btn_{i}_{current_gen}"):
                    with st.spinner("Syncing to Notion..."):
                        s, m = save_to_notion(st.session_state.p_name, edited_text, persona, notion_token, notion_db_id)
                        if s:
                            st.toast(f"✅ Saved: {persona}")
                        else:
                            st.error(f"Failed: {m}")
        st.divider()