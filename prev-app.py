import sqlite3
import pandas as pd
import streamlit as st

# -----------------------------------------------------------------------------
# 1. PAGE CONFIG & CORPORATE MODERNISM CSS THEME
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Malik Property - Lead Intelligence",
    page_icon="🏡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    /* Global Page Styling */
    .stApp {
        background-color: #F7F9FB;
        font-family: 'Inter', sans-serif;
        color: #191C1E;
    }
    
    /* Hide Default Streamlit Header Components */
    header[data-testid="stHeader"] {
        background: transparent;
    }
    
    /* Custom Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1px solid #E6E8EA;
        padding-top: 1rem;
    }
    
    /* Primary Sidebar Header & Branding */
    .brand-container {
        padding: 8px 16px 20px 16px;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .brand-logo {
        background-color: #131B2E;
        color: #FFFFFF;
        font-weight: 700;
        font-size: 14px;
        width: 38px;
        height: 38px;
        border-radius: 4px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .brand-title {
        font-weight: 700;
        font-size: 16px;
        color: #191C1E;
        line-height: 1.2;
    }
    .brand-subtitle {
        font-size: 12px;
        color: #76777D;
    }

    /* Metric Card Styling */
    .metric-card {
        background-color: #FFFFFF;
        border: 1px solid #E6E8EA;
        border-radius: 4px;
        padding: 20px;
        margin-bottom: 12px;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
    }
    .metric-label {
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        color: #76777D;
    }
    .metric-value {
        font-size: 28px;
        font-weight: 700;
        color: #191C1E;
        margin-top: 4px;
    }
    .metric-delta-pos {
        color: #006C4A;
        font-size: 12px;
        font-weight: 600;
        background-color: #E6F4EA;
        padding: 2px 6px;
        border-radius: 4px;
        margin-left: 8px;
    }
    .metric-delta-neg {
        color: #BA1A1A;
        font-size: 12px;
        font-weight: 600;
        background-color: #FFDAD6;
        padding: 2px 6px;
        border-radius: 4px;
        margin-left: 8px;
    }

    /* Table / Card Container Block */
    .lead-row-card {
        background-color: #FFFFFF;
        border: 1px solid #E6E8EA;
        border-radius: 4px;
        padding: 16px 20px;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
    }

    /* Pill Status Badges */
    .badge-pill {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.03em;
        text-transform: uppercase;
    }
    .badge-hot { background-color: #FFDAD6; color: #93000A; }
    .badge-buying { background-color: #ECEEF0; color: #131B2E; }
    .badge-selling { background-color: #82F5C1; color: #004D34; }
    .badge-new { background-color: #D3E4FE; color: #0B1C30; }

    /* Custom Input Control Override */
    .stButton > button {
        border-radius: 4px !important;
        font-weight: 600 !important;
        border: 1px solid #E6E8EA !important;
    }
    .stButton > button[kind="primary"] {
        background-color: #131B2E !important;
        color: #FFFFFF !important;
        border: none !important;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. DATABASE INITIALIZATION & LOGIC
# -----------------------------------------------------------------------------
def init_test_db():
    conn = sqlite3.connect("test_leads.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT UNIQUE,
            client_name TEXT,
            intent TEXT,
            lead_stage TEXT,
            bot_active INTEGER DEFAULT 1
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS buyer_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER UNIQUE,
            preferred_location TEXT,
            property_type TEXT,
            land_area TEXT,
            budget_range INTEGER,
            purchase_timeline TEXT,
            payment_type TEXT,
            plot_category TEXT,
            purpose TEXT,
            lead_score INTEGER,
            FOREIGN KEY (lead_id) REFERENCES leads (id)
        )
    """)
    
    cursor.execute("SELECT COUNT(*) FROM leads")
    if cursor.fetchone()[0] == 0:
        mock_leads = [
            ("923001234567", "Tariq Mahmood", "BUYER", "New Inquiry", 1),
            ("923219876543", "Chaudhry Akram", "BUYER", "Site Visit Scheduled", 1),
            ("923335557788", "Dr. Salman", "BUYER", "Negotiation", 0),
            ("923009988776", "Sarah Jenkins", "BUYER", "In Contact", 1),
            ("923112233445", "Michael Chen", "SELLER", "Valuation", 1)
        ]
        cursor.executemany("INSERT INTO leads (phone_number, client_name, intent, lead_stage, bot_active) VALUES (?, ?, ?, ?, ?)", mock_leads)
        
        mock_prefs = [
            (1, "Wapda Town", "RESIDENTIAL_PLOT", "5 Marla", 4500000, "IMMEDIATE", "FULL_CASH", "CORNER", "PERSONAL", 85),
            (2, "DHA Phase 1", "HOUSE", "1 Kanal", 35000000, "1-3_MONTHS", "INSTALLMENTS", "MAIN_BOULEVARD", "INVESTMENT", 70),
            (3, "City Housing", "COMMERCIAL", "4 Marla", 18000000, "IMMEDIATE", "FULL_CASH", "PARK_FACING", "INVESTMENT", 92),
            (4, "Gulberg Heights", "APARTMENT", "2 Bed", 12500000, "IMMEDIATE", "FULL_CASH", "STANDARD", "PERSONAL", 88),
            (5, "Canal View", "HOUSE", "10 Marla", 28000000, "FLEXIBLE", "FULL_CASH", "STANDARD", "INVESTMENT", 65)
        ]
        cursor.executemany("""
            INSERT INTO buyer_preferences (
                lead_id, preferred_location, property_type, land_area, budget_range, 
                purchase_timeline, payment_type, plot_category, purpose, lead_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, mock_prefs)
        
        conn.commit()
    conn.close()

def toggle_bot_status(lead_id, current_status):
    new_status = 0 if current_status == 1 else 1
    conn = sqlite3.connect("test_leads.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE leads SET bot_active = ? WHERE id = ?", (new_status, lead_id))
    conn.commit()
    conn.close()

init_test_db()

def get_leads_data():
    conn = sqlite3.connect("test_leads.db")
    query = """
        SELECT 
            l.id as lead_id,
            l.client_name,
            l.phone_number,
            l.intent,
            l.lead_stage,
            l.bot_active,
            bp.preferred_location,
            bp.property_type,
            bp.land_area,
            bp.budget_range,
            bp.lead_score
        FROM leads l
        LEFT JOIN buyer_preferences bp ON l.id = bp.lead_id
        ORDER BY bp.lead_score DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# -----------------------------------------------------------------------------
# 3. SIDEBAR NAVIGATION
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("""
        <div class="brand-container">
            <div class="brand-logo">MP</div>
            <div>
                <div class="brand-title">Malik Property</div>
                <div class="brand-subtitle">WhatsApp Lead Bot</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    st.button("+ New Broadcast", type="primary", use_container_width=True)
    st.write("")
    
    page = st.radio(
        "Navigation",
        ["Dashboard", "Leads", "Property Matches", "Settings"],
        label_visibility="collapsed"
    )
    
    st.divider()
    st.caption("SYSTEM STATE")
    st.markdown("🟢 **Bot Service Active**")

# -----------------------------------------------------------------------------
# 4. MODAL DIALOG
# -----------------------------------------------------------------------------
@st.dialog("📋 Lead Details & Operations", width="large")
def show_lead_dialog(lead):
    st.subheader(f"Client Profile: {lead['client_name']}")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"📞 **Phone Number:** `{lead['phone_number']}`")
        st.write(f"🎯 **Intent:** `{lead['intent']}`")
        st.write(f"📌 **Pipeline Stage:** `{lead['lead_stage']}`")
        st.write(f"🤖 **Bot Automation:** {'🟢 Active' if lead['bot_active'] == 1 else '🛑 Stopped'}")
        
    with col2:
        st.write(f"📍 **Preferred Location:** {lead['preferred_location']}")
        st.write(f"🏠 **Property Category:** {lead['property_type']}")
        st.write(f"📏 **Land Area:** {lead['land_area']}")
        st.write(f"💵 **Budget Ceiling:** PKR {lead['budget_range']:,}")

    st.divider()
    
    c1, c2 = st.columns(2)
    with c1:
        wa_text = f"AoA {lead['client_name']}, Malik Property update."
        wa_url = f"https://wa.me/{lead['phone_number']}?text={wa_text.replace(' ', '%20')}"
        st.link_button("💬 Open WhatsApp Chat", wa_url, use_container_width=True)
    with c2:
        if st.button("Close View", use_container_width=True):
            st.rerun()

# -----------------------------------------------------------------------------
# 5. MAIN ROUTING & DASHBOARD VIEWS
# -----------------------------------------------------------------------------
df_leads = get_leads_data()

# TOP APP BAR SEARCH
top_search_col, top_profile_col = st.columns([5, 1])
with top_search_col:
    search_query = st.text_input("Search", placeholder="🔍 Search leads, numbers, or parameters...", label_visibility="collapsed")
with top_profile_col:
    st.markdown("<div style='text-align: right;'><b>Admin Account</b> 🔔</div>", unsafe_allow_html=True)

st.divider()

if page == "Dashboard":
    st.markdown("## Overview Dashboard")
    st.caption("Real-time metrics and intelligence for your WhatsApp automation engine.")
    
    # METRICS ROW
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Total Leads</div>
                <div class="metric-value">{len(df_leads)} <span class="metric-delta-pos">↑12%</span></div>
            </div>
        """, unsafe_allow_html=True)
    with m2:
        st.markdown("""
            <div class="metric-card">
                <div class="metric-label">Active Chats</div>
                <div class="metric-value">85 <span class="metric-delta-pos">~0%</span></div>
            </div>
        """, unsafe_allow_html=True)
    with m3:
        st.markdown("""
            <div class="metric-card">
                <div class="metric-label">Property Matches</div>
                <div class="metric-value">42 <span class="metric-delta-pos">↑5%</span></div>
            </div>
        """, unsafe_allow_html=True)
    with m4:
        st.markdown("""
            <div class="metric-card">
                <div class="metric-label">Conversion Rate</div>
                <div class="metric-value">12% <span class="metric-delta-neg">↓2%</span></div>
            </div>
        """, unsafe_allow_html=True)

    st.write("")
    
    # MAIN CONTENT GRID
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.markdown("### Recent Bot Activity")
        st.markdown("""
            <div class="metric-card">
                <p>🟢 <b>Bot</b> sent 3 property recommendations to <b>Sarah Jenkins</b>. <small>2 MINS AGO</small></p>
                <p>🔵 <b>Michael Chen</b> initiated a new chat inquiring about <b>Downtown Lofts</b>. <small>15 MINS AGO</small></p>
                <p>🔴 <b>Bot</b> scheduled a viewing for <b>Tariq Mahmood</b> at <b>Wapda Town</b>. <small>1 HOUR AGO</small></p>
            </div>
        """, unsafe_allow_html=True)
        
    with col_right:
        st.markdown("### Lead Intent")
        st.markdown("""
            <div class="metric-card" style="text-align: center;">
                <h2 style="color: #006C4A; margin: 0;">60%</h2>
                <p><b>BUYERS</b> vs 40% Sellers</p>
            </div>
        """, unsafe_allow_html=True)

    st.divider()
    
    # HOT LEADS OVERVIEW
    st.markdown("### Priority Queue")
    
    # Table Column Headers
    h1, h2, h3, h4, h5 = st.columns([2, 1.5, 1.5, 1.2, 2.5])
    h1.markdown("**CLIENT**")
    h2.markdown("**BUDGET**")
    h3.markdown("**INTENT**")
    h4.markdown("**SCORE**")
    h5.markdown("**ACTIONS**")

    # Table Row Content
    for _, row in df_leads.iterrows():
        c1, c2, c3, c4, c5 = st.columns([2, 1.5, 1.5, 1.2, 2.5])
        
        # Name and phone
        c1.markdown(f"**{row['client_name']}**<br><small style='color:#76777D;'>{row['phone_number']}</small>", unsafe_allow_html=True)
        
        # Budget
        c2.markdown(f"PKR {row['budget_range']:,}")
        
        # Intent pill badge
        badge_type = "badge-hot" if row['lead_score'] >= 80 else "badge-buying"
        c3.markdown(f'<span class="badge-pill {badge_type}">{row["intent"]}</span>', unsafe_allow_html=True)
        
        # Score
        c4.markdown(f"**{row['lead_score']}**/100")
        
        # 3 Vertical/Horizontal Action Buttons
        with c5:
            b1, b2, b3 = st.columns(3)
            with b1:
                if st.button("👁️", key=f"v_{row['lead_id']}", help="View Details", use_container_width=True):
                    show_lead_dialog(row)
            with b2:
                wa_url = f"https://wa.me/{row['phone_number']}"
                st.link_button("💬", wa_url, help="Chat on WhatsApp", use_container_width=True)
            with b3:
                is_active = row['bot_active'] == 1
                stop_label = "🛑" if is_active else "▶️"
                if st.button(stop_label, key=f"s_{row['lead_id']}", help="Toggle Bot Automation", use_container_width=True):
                    toggle_bot_status(row['lead_id'], row['bot_active'])
                    st.toast(f"Updated Bot status for {row['client_name']}")
                    st.rerun()

elif page == "Leads":
    st.markdown("## Leads Pipeline")
    st.caption("Manage and qualify incoming inquiries from the WhatsApp bot.")
    
    # FILTERS
    f1, f2, f3 = st.columns(3)
    f1.selectbox("Lead Status", ["All Statuses", "New Inquiry", "Negotiation", "Site Visit Scheduled"])
    f2.selectbox("Intent", ["Buying & Selling", "BUYER", "SELLER"])
    f3.selectbox("Property Type", ["All Types", "RESIDENTIAL_PLOT", "HOUSE", "COMMERCIAL"])
    
    st.divider()
    
    # LEADS QUEUE TABLE
    for _, row in df_leads.iterrows():
        with st.container():
            lc1, lc2, lc3, lc4, lc5 = st.columns([2, 1.5, 1.5, 1, 2.5])
            lc1.markdown(f"**{row['client_name']}**<br><small>{row['phone_number']}</small>", unsafe_allow_html=True)
            lc2.markdown(f"**{row['property_type']}**<br><small>{row['preferred_location']}</small>", unsafe_allow_html=True)
            lc3.markdown(f"PKR {row['budget_range']:,}")
            lc4.markdown(f'<span class="badge-pill badge-hot">{row["lead_stage"]}</span>', unsafe_allow_html=True)
            
            with lc5:
                ab1, ab2, ab3 = st.columns(3)
                with ab1:
                    if st.button("View", key=f"lv_{row['lead_id']}", use_container_width=True):
                        show_lead_dialog(row)
                with ab2:
                    st.link_button("Chat", f"https://wa.me/{row['phone_number']}", use_container_width=True)
                with ab3:
                    lbl = "Stop" if row['bot_active'] == 1 else "Resume"
                    if st.button(lbl, key=f"ls_{row['lead_id']}", use_container_width=True):
                        toggle_bot_status(row['lead_id'], row['bot_active'])
                        st.rerun()
            st.divider()

elif page == "Property Matches":
    st.markdown("## Intelligence Matches")
    st.caption("Bot-curated property recommendations based on active lead conversations.")
    
    card1, card2 = st.columns(2)
    with card1:
        st.markdown("""
            <div class="metric-card">
                <span class="badge-pill badge-hot">Hot Match - 98%</span>
                <h4>Azure Marina Villa</h4>
                <p>Client: <b>James Doe</b> | Budget: $1.2M - $1.5M</p>
            </div>
        """, unsafe_allow_html=True)
        st.button("Send Proposal to WhatsApp", key="p1", type="primary")
        
    with card2:
        st.markdown("""
            <div class="metric-card">
                <span class="badge-pill badge-buying">Active Match - 85%</span>
                <h4>Skyline Residence 4B</h4>
                <p>Client: <b>Sarah Lewis</b> | Budget: Up to $800k</p>
            </div>
        """, unsafe_allow_html=True)
        st.button("Send Proposal to WhatsApp", key="p2", type="primary")

elif page == "Settings":
    st.markdown("## System Settings")
    st.caption("Manage agency profiles, bot rules, and system notifications.")
    
    tab1, tab2 = st.tabs(["Agency Profile", "Bot Configuration"])
    with tab1:
        st.text_input("Agency Name", value="Malik Property")
        st.text_input("WhatsApp Number", value="+92 300 1234567")
        st.text_area("Business Address", value="Main Boulevard, Mianwali, Pakistan")
        st.button("Save Changes", type="primary")
        
    with tab2:
        st.toggle("Auto-reply Engine", value=True)
        st.toggle("Lead Qualification Bot", value=True)
        st.toggle("Smart Property Matching", value=True)