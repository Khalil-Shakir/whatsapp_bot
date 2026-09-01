import sqlite3
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Malik Property - Lead Intelligence", layout="wide")

# -----------------------------------------------------------------------------
# 1. CUSTOM MODERN CSS INJECTION
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    /* Card Container Base */
    .lead-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    
    /* Dynamic Badges */
    .badge-hot {
        background-color: #FEE2E2;
        color: #991B1B;
        padding: 4px 10px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-warm {
        background-color: #FEF3C7;
        color: #92400E;
        padding: 4px 10px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-active {
        background-color: #DCFCE7;
        color: #166534;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-stopped {
        background-color: #F3F4F6;
        color: #4B5563;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .tag-spec {
        background-color: #F1F5F9;
        color: #334155;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 0.85rem;
        margin-right: 6px;
    }
    
    /* Clean Divider inside Cards */
    .card-divider {
        margin: 14px 0;
        border-bottom: 1px solid #F1F5F9;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. DATABASE & MOCK DATA SETUP
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
            ("923335557788", "Dr. Salman", "BUYER", "Negotiation", 0)
        ]
        cursor.executemany("INSERT INTO leads (phone_number, client_name, intent, lead_stage, bot_active) VALUES (?, ?, ?, ?, ?)", mock_leads)
        
        mock_prefs = [
            (1, "Wapda Town", "RESIDENTIAL_PLOT", "5 Marla", 4500000, "IMMEDIATE", "FULL_CASH", "CORNER", "PERSONAL", 85),
            (2, "DHA Phase 1", "HOUSE", "1 Kanal", 35000000, "1-3_MONTHS", "INSTALLMENTS", "MAIN_BOULEVARD", "INVESTMENT", 70),
            (3, "City Housing", "COMMERCIAL", "4 Marla", 18000000, "IMMEDIATE", "FULL_CASH", "PARK_FACING", "INVESTMENT", 92)
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

# -----------------------------------------------------------------------------
# 3. DATA RETRIEVAL
# -----------------------------------------------------------------------------
def get_buyer_leads():
    conn = sqlite3.connect("test_leads.db")
    query = """
        SELECT 
            l.id as lead_id,
            l.client_name,
            l.phone_number,
            l.lead_stage,
            l.bot_active,
            bp.preferred_location,
            bp.property_type,
            bp.land_area,
            bp.budget_range,
            bp.purchase_timeline,
            bp.payment_type,
            bp.plot_category,
            bp.purpose,
            bp.lead_score
        FROM leads l
        JOIN buyer_preferences bp ON l.id = bp.lead_id
        WHERE l.intent = 'BUYER'
        ORDER BY bp.lead_score DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

df_buyers = get_buyer_leads()

# -----------------------------------------------------------------------------
# 4. MODAL POPUP DIALOG
# -----------------------------------------------------------------------------
@st.dialog("📋 Lead Profile Overview", width="large")
def show_lead_details_popup(lead_data):
    score_badge = "🔥" if lead_data['lead_score'] >= 80 else "🟡"
    st.subheader(f"{score_badge} {lead_data['client_name']} — Score: {lead_data['lead_score']}/100")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 👤 Client Profile")
        st.write(f"📞 **Phone:** `{lead_data['phone_number']}`")
        st.write(f"📌 **Pipeline Stage:** `{lead_data['lead_stage']}`")
        st.write(f"🤖 **Bot Automation:** {'🟢 Active' if lead_data['bot_active'] == 1 else '🔴 Handover Active'}")
        st.write(f"📍 **Preferred Location:** {lead_data['preferred_location']}")
        st.write(f"🏠 **Property Type:** {lead_data['property_type']}")
        st.write(f"📏 **Land Area:** {lead_data['land_area']}")
        st.write(f"🏷️ **Plot Specs:** {lead_data['plot_category']}")
        
    with col2:
        st.markdown("#### 💰 Budget & Readiness")
        st.write(f"💵 **Budget Max:** PKR {lead_data['budget_range']:,}")
        st.write(f"💳 **Payment Terms:** {lead_data['payment_type']}")
        st.write(f"⏱️ **Buying Timeline:** {lead_data['purchase_timeline']}")
        st.write(f"🎯 **Intent Purpose:** {lead_data['purpose']}")
    
    st.divider()
    
    wa_text = f"AoA {lead_data['client_name']}, Malik Property se update hai. Aap ke required budget (PKR {lead_data['budget_range']:,}) aur location ({lead_data['preferred_location']}) ke mutabiq naye options available hain."
    wa_url = f"https://wa.me/{lead_data['phone_number']}?text={wa_text.replace(' ', '%20')}"
    
    c_btn1, c_btn2 = st.columns([2, 1])
    with c_btn1:
        st.link_button("💬 Launch WhatsApp Web", wa_url, use_container_width=True)
    with c_btn2:
        if st.button("Close Window", use_container_width=True):
            st.rerun()

# -----------------------------------------------------------------------------
# 5. MAIN DASHBOARD UI
# -----------------------------------------------------------------------------
st.title("🏡 Malik Property — Buyer Intelligence Engine")
st.caption("Real-time lead scoring, dynamic profile parameters, and AI bot intervention control.")

# Top Metric Cards
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Active Buyers", len(df_buyers))
col2.metric("🔥 Hot Leads (Score ≥ 80)", len(df_buyers[df_buyers['lead_score'] >= 80]))
col3.metric("💰 Full Cash Ready", len(df_buyers[df_buyers['payment_type'] == 'FULL_CASH']))
col4.metric("🤖 Active Bot Sessions", len(df_buyers[df_buyers['bot_active'] == 1]))

st.divider()

st.subheader("📋 Priority Buyer Feed")

# Modern Card-based Table Iteration
for _, row in df_buyers.iterrows():
    bot_badge_html = (
        '<span class="badge-active">🤖 Bot Active</span>' 
        if row['bot_active'] == 1 
        else '<span class="badge-stopped">🛑 Human Control</span>'
    )
    
    score_class = "badge-hot" if row['lead_score'] >= 80 else "badge-warm"
    score_badge_html = f'<span class="{score_class}">Score: {row["lead_score"]}/100</span>'

    # Outer Container Block
    with st.container():
        # Top Header of Card
        c_head1, c_head2 = st.columns([3, 1])
        with c_head1:
            st.markdown(
                f"### {row['client_name']} &nbsp;&nbsp; {bot_badge_html}", 
                unsafe_allow_html=True
            )
        with c_head2:
            st.markdown(
                f"<div style='text-align: right;'>{score_badge_html}</div>", 
                unsafe_allow_html=True
            )
            
        # Specs Row
        s1, s2, s3, s4 = st.columns([1.5, 1.5, 1.5, 1.5])
        s1.markdown(f"📍 **Location:** {row['preferred_location']}")
        s2.markdown(f"🏠 **Specs:** {row['property_type']} ({row['land_area']})")
        s3.markdown(f"💵 **Budget:** PKR {row['budget_range']:,}")
        s4.markdown(f"📌 **Stage:** `{row['lead_stage']}`")
        
        # Horizontal Action Toolbar
        a1, a2, a3, a4 = st.columns([1.2, 1.2, 1.4, 2])
        
        with a1:
            if st.button("👁️ View Profile", key=f"view_{row['lead_id']}", use_container_width=True):
                show_lead_details_popup(row)
                
        with a2:
            wa_text = f"AoA {row['client_name']}, Malik Property se update hai. Aap ke required options ke mutabiq details available hain."
            wa_url = f"https://wa.me/{row['phone_number']}?text={wa_text.replace(' ', '%20')}"
            st.link_button("💬 WhatsApp", wa_url, use_container_width=True)
            
        with a3:
            is_active = row['bot_active'] == 1
            btn_label = "🛑 Pause Bot" if is_active else "▶️ Resume Bot"
            btn_type = "secondary" if is_active else "primary"
            
            if st.button(btn_label, key=f"bot_toggle_{row['lead_id']}", use_container_width=True, type=btn_type):
                toggle_bot_status(row['lead_id'], row['bot_active'])
                st.toast(f"Updated Bot status for {row['client_name']}!", icon="⚙️")
                st.rerun()

        st.markdown('<div class="card-divider"></div>', unsafe_allow_html=True)