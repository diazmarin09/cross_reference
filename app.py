import streamlit as st  # Web app builder library
import pandas as pd     # Data handling library

# ==============================================================================
# 1. GLOBAL PAGE CONFIG
# MUST be the very first Streamlit command called in your script.
# ==============================================================================
st.set_page_config(
    page_title="NXP Cross-Reference Hub", 
    layout="wide", 
    page_icon="nxp_logo.png"
)

# ==============================================================================
# 2. PASSWORD GATE / ACCESS CONTROL
# Blocks unauthorized users from viewing or running any part of the app below.
# ==============================================================================

# 🔑 STEP 1: Set your master password here (change this to whatever you like)
MASTER_PASSWORD = "1511" 

# 🔑 STEP 2: Initialize login session status
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# 🔑 STEP 3: Render login screen if the user has not logged in yet
if not st.session_state["authenticated"]:
    try:
        st.image("nxp_logo.png", width=120)
    except FileNotFoundError:
        st.write("🖼️ Logo")

    st.title("🔒 Restricted Access")
    st.write("Welcome to the **NXP Cross-Reference Hub**. Please enter the password to continue.")

    # Password input field (masks characters as typed)
    user_input = st.text_input("Password:", type="password")

    if st.button("Log In"):
        if user_input == MASTER_PASSWORD:
            st.session_state["authenticated"] = True
            st.success("✅ Password correct!")
            st.rerun()  # Reloads the app page to unlock full access
        else:
            st.error("❌ Incorrect password. Please try again.")

    # IMPORTANT: st.stop() prevents any code below this line from executing!
    # No CSV files or data will be loaded until the password is valid.
    st.stop()


# ==============================================================================
# 3. APP BRANDING & HEADER (Visible only AFTER successful login)
# ==============================================================================
try:
    st.image("nxp_logo.png", width=120)
except FileNotFoundError:
    st.write("🖼️ Logo")

st.title("NXP Cross-Reference Hub")

# Add a subtle logout button in the top right sidebar
if st.sidebar.button("🔒 Log Out"):
    st.session_state["authenticated"] = False
    st.rerun()


# ==============================================================================
# 4. SIDEBAR MENU NAVIGATION
# ==============================================================================
st.sidebar.title("Product Family")
selected_tool = st.sidebar.radio(
    "Select a Cross-Reference Tool:",
    options=["GPIO Expanders", "RTC (Real-Time Clocks)"]
)

st.sidebar.divider()
st.sidebar.caption("Use the menu above to switch between component search engines.")


# ==============================================================================
# 5. TOOL 1: GPIO EXPANDERS
# ==============================================================================
def render_gpio_tool():
    st.header("GPIO Expander Cross-Reference")
    st.write("Enter a competitor part number below to find the best NXP equivalent.")

    # Display key color explanations (Badges) using columns
    st.subheader("Definition of the Cross-Grade")
    col1, col2 = st.columns([1, 4])
    with col1:
        st.badge("Grade A 🟢: Functional Replacement", color="green")
    with col2:
        st.caption("Best match on Interface, package, number of bits, pin count, supply voltage, and core features.")

    col1, col2 = st.columns([1, 4])
    with col1:
        st.badge("Grade B 🟡: Near Replacement", color="orange")
    with col2:
        st.caption("Minor differences that may require validation.")

    col1, col2 = st.columns([1, 4])
    with col1:
        st.badge("Grade C 🔴: Partial Replacement", color="red")
    with col2:
        st.caption("Significant differences requiring redesign or qualification.")

    # ⚡ DATA LOADING FUNCTION WITH CACHING
    # @st.cache_data prevents reloading CSV files every single time a user clicks a button.
    @st.cache_data
    def load_gpio_data():
        df_competitor = pd.read_csv('GPIO Cross Reference - Competitors.csv')
        df_nxp = pd.read_csv('GPIO Cross Reference - NXP.csv')
        
        # Clean column headers (removes accidental leading/trailing spaces in header names)
        df_competitor.columns = df_competitor.columns.str.strip()
        df_nxp.columns = df_nxp.columns.str.strip()
        return df_competitor, df_nxp

    # Safely load the data and handle missing files gracefully
    try:
        df_competitor, df_nxp = load_gpio_data()
    except FileNotFoundError:
        st.error("⚠️ GPIO Databases not found. Please ensure the CSV files are in the working directory.")
        return

    # Extract part numbers, remove empty values, convert to text, strip spaces, sort alphabetically
    part_list = df_competitor['Part number'].dropna().astype(str).str.strip().sort_values().tolist()

    # Dropdown menu with text auto-complete
    search_query = st.selectbox(
        "Search Competitor Part (Start typing to auto-complete):",
        options=[""] + part_list,  # Add empty default option at top
        index=0,
        key="gpio_search_selectbox"
    )

    # Trigger processing only when a part has been selected
    if search_query != "":
        search_query = search_query.strip().upper() 
        
        # Look for matching part number in competitor dataset (case-insensitive)
        match_part = df_competitor[df_competitor['Part number'].str.strip().str.upper() == search_query]
        
        if match_part.empty:
            st.warning(f"Could not find '{search_query}' in the competitor database.")
        else:
            # Get the first row matching the selected competitor part
            target_part = match_part.iloc[0]
            st.success(f"✅ Found Competitor Part: **{target_part['Part number']}**")
            
            results = []
            
            # 🎯 EXTRACT MANDATORY REQUIREMENTS FROM THE COMPETITOR PART
            target_type = str(target_part['AEC-Q100 compliant']).strip().upper()
            target_bits = str(target_part['Number of bits']).strip()
            
            # 🔍 SCORING LOOP: Compare selected competitor part against every NXP part
            for index, nxp_part in df_nxp.iterrows():
                nxp_type = str(nxp_part['AEC-Q100 compliant']).strip().upper()
                nxp_bits = str(nxp_part['Number of bits']).strip()
                
                # 🛑 MANDATORY FILTER 1: Skip NXP part if Automotive qualification (AEC-Q100) doesn't match
                if target_type != nxp_type:
                    continue 

                # 🛑 MANDATORY FILTER 2: Skip NXP part if Number of Bits doesn't match exactly
                # (e.g., A 4-bit competitor part will ONLY look at 4-bit NXP parts)
                if target_bits != nxp_bits:
                    continue

                # Start score at 30 points (since bit count is mandatory and already matched above)
                score = 30
                
                # Feature Comparison 1: Package Type (15 pts)
                target_pkg = str(target_part['Package Type']).strip()
                nxp_pkg = str(nxp_part['Package Type']).strip()
                if target_pkg == nxp_pkg:
                    score += 15
                    
                # Feature Comparison 2: Interface / Protocol (15 pts)
                target_protocol = str(target_part['Interface']).strip()
                nxp_protocol = str(nxp_part['Interface']).strip()
                if target_protocol in nxp_protocol or nxp_protocol in target_protocol: 
                    score += 15
                    
                # Secondary Features comparison (+5 pts each)
                if str(target_part['Supply Voltage Side A [Min to Max] (V)']).strip() == str(nxp_part['Supply Voltage Side A [Min to Max] (V)']).strip():
                    score += 5
                if str(target_part['Supply Voltage Side B [Min to Max] (V)']).strip() == str(nxp_part['Supply Voltage Side B [Min to Max] (V)']).strip():
                    score += 5
                if str(target_part['Number of Address pins']).strip() == str(nxp_part['Number of Address pins']).strip():
                    score += 5
                if str(target_part['Max Sink Current per bit (mA)']).strip() == str(nxp_part['Max Sink Current per bit (mA)']).strip():
                    score += 5
                if str(target_part['Max Source Current per bit (mA)']).strip() == str(nxp_part['Max Source Current per bit (mA)']).strip():
                    score += 5
                if str(target_part['Interrupt']).strip() == str(nxp_part['Interrupt']).strip():
                    score += 5
                if str(target_part['Reset input pin']).strip() == str(nxp_part['Reset input pin']).strip():
                    score += 5
                if str(target_part['AEC-Q100 compliant']).strip() == str(nxp_part['AEC-Q100 compliant']).strip():
                    score += 5
                    
                # Assign grade based on total cumulative score
                if score == 100: 
                    grade = 'Grade A - Functional Replacement 🟢'
                elif score >= 60: 
                    grade = 'Grade B - Near Replacement 🟡'
                elif score >= 30: 
                    grade = 'Grade C - Partial Replacement 🔴'
                else: 
                    grade = 'No Match'
                    
                # Check for NXP proprietary 'Agile' feature
                agile_val = str(nxp_part.get('Agile', nxp_part.get('Agile I/O', 'N'))).strip().upper()
                    
                # Include in results if score is at least 30 (Grade C or higher)
                if score >= 30:
                    results.append({
                        'NXP Replacement': nxp_part['Part number'],
                        'Datasheet': nxp_part['Datasheet'],
                        'Compatibility': grade,
                        'Number of bits': nxp_part['Number of bits'],
                        'Agile': agile_val,
                        'Match Score': score,
                        'Package': nxp_pkg,
                        'Supply Voltage Side A (V)': nxp_part['Supply Voltage Side A [Min to Max] (V)'],
                        'Supply Voltage Side B (V)': nxp_part['Supply Voltage Side B [Min to Max] (V)'],
                        'Operating Temp (C)': nxp_part['Operating Temperature (Min-Max) (℃)']
                    })           
            
            if results:
                # Convert list of matched dictionaries into a clean Pandas DataFrame
                results_df = pd.DataFrame(results)
                
                # Sort matches: Prioritize 'Agile' parts first (True/False sorting), then highest score
                results_df['Is_Agile'] = results_df['Agile'].str.upper() == 'Y'
                results_df = results_df.sort_values(by=['Is_Agile', 'Match Score'], ascending=[False, False]).drop(columns=['Is_Agile'])
                
                # Limit non-automotive parts to top 5 recommendations
                if target_type == 'N':
                    results_df = results_df.head(5)
                    
                st.write("### Recommended NXP Replacements")
                
                # Hide numerical score column from user-facing UI
                SHOW_INTERNAL_SCORE = False 
                display_df = results_df.copy()
                if not SHOW_INTERNAL_SCORE:
                    display_df = display_df.drop(columns=['Match Score'])
                
                # Render results table with clickable URL links to PDF datasheets
                st.dataframe(
                    display_df, 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={
                        "Datasheet": st.column_config.LinkColumn(
                            "Datasheet",
                            help="Click to open the NXP datasheet",
                            display_text="View PDF" 
                        )
                    }
                )
                
                st.divider()
                st.write("### Comparison Table (Top 2 Matches)")
                
                # 📊 GENERATE SIDE-BY-SIDE FEATURE COMPARISON TABLE
                features_list = [
                    "Supplier", "Number of bits", "Package", "Interface", "Frequency (KHz)", 
                    "Supply Voltage Side A [Min to Max] (V)", "Supply Voltage Side B [Min to Max] (V)","Number of address pins", "Max sink current per bit (mA)",
                    "Max source current per bit (mA)", "Interrupt", "Reset input pin", "Operating Temperature (Min-Max) (℃)"
                ]
                
                # Populate competitor values into table column dictionary
                comp_data = {
                    "Feature": features_list,
                    f"{target_part['Part number']} (Competitor)": [
                        str(target_part.get('Supplier', '-')),
                        str(target_part.get('Number of bits', '-')),
                        str(target_part.get('Package Type', '-')),
                        str(target_part.get('Interface', '-')),
                        str(target_part.get('Baudrate (KHz)', '-')).split('-')[0],
                        str(target_part.get('Supply Voltage Side A [Min to Max] (V)', '-')),
                        str(target_part.get('Supply Voltage Side B [Min to Max] (V)', '-')),
                        str(target_part.get('Number of Address pins', '-')),
                        str(target_part.get('Max Sink Current per bit (mA)', '-')),
                        str(target_part.get('Max Source Current per bit (mA)', '-')),
                        str(target_part.get('Interrupt', '-')),
                        str(target_part.get('Reset input pin', '-')),
                        str(target_part.get('Operating Temperature (Min-Max) (℃)', '-')),
                    ]
                }
                
                # Fetch full data row for Top 1 NXP match
                top1_nxp_name = results_df.iloc[0]['NXP Replacement']
                top1_nxp_part = df_nxp[df_nxp['Part number'] == top1_nxp_name].iloc[0]
                
                comp_data[f"{top1_nxp_part['Part number']} (Top 1)"] = [
                    str(top1_nxp_part.get('Supplier', '-')),
                    str(top1_nxp_part.get('Number of bits', '-')),
                    str(top1_nxp_part.get('Package Type', '-')),
                    str(top1_nxp_part.get('Interface', '-')),
                    str(top1_nxp_part.get('Baudrate (KHz)', '-')).split('-')[0],
                    str(top1_nxp_part.get('Supply Voltage Side A [Min to Max] (V)', '-')),
                    str(top1_nxp_part.get('Supply Voltage Side B [Min to Max] (V)', '-')),
                    str(top1_nxp_part.get('Number of Address pins', '-')),
                    str(top1_nxp_part.get('Max Sink Current per bit (mA)', '-')),
                    str(top1_nxp_part.get('Max Source Current per bit (mA)', '-')),
                    str(top1_nxp_part.get('Interrupt', '-')),
                    str(top1_nxp_part.get('Reset input pin', '-')),
                    str(top1_nxp_part.get('Operating Temperature (Min-Max) (℃)', '-')),
                ]
                
                # Fetch full data row for Top 2 NXP match (if available)
                if len(results_df) > 1:
                    top2_nxp_name = results_df.iloc[1]['NXP Replacement']
                    top2_nxp_part = df_nxp[df_nxp['Part number'] == top2_nxp_name].iloc[0]
                    
                    comp_data[f"{top2_nxp_part['Part number']} (Top 2)"] = [
                        str(top2_nxp_part.get('Supplier', '-')),
                        str(top2_nxp_part.get('Number of bits', '-')),
                        str(top2_nxp_part.get('Package Type', '-')),
                        str(top2_nxp_part.get('Interface', '-')),
                        str(top2_nxp_part.get('Baudrate (KHz)', '-')).split('-')[0],
                        str(top2_nxp_part.get('Supply Voltage Side A [Min to Max] (V)', '-')),
                        str(top2_nxp_part.get('Supply Voltage Side B [Min to Max] (V)', '-')),
                        str(top2_nxp_part.get('Number of Address pins', '-')),
                        str(top2_nxp_part.get('Max Sink Current per bit (mA)', '-')),
                        str(top2_nxp_part.get('Max Source Current per bit (mA)', '-')),
                        str(top2_nxp_part.get('Interrupt', '-')),
                        str(top2_nxp_part.get('Reset input pin', '-')),
                        str(top2_nxp_part.get('Operating Temperature (Min-Max) (℃)', '-')),
                    ]
                
                # Display side-by-side comparison table
                comp_df = pd.DataFrame(comp_data)
                st.dataframe(comp_df, use_container_width=True, hide_index=True)
            else:
                st.info(f"No suitable NXP replacements found for this part with {target_bits} bits.")


# ==============================================================================
# 6. TOOL 2: RTC (REAL-TIME CLOCKS)
# ==============================================================================
def render_rtc_tool():
    st.header("RTC Cross-Reference Search")
    st.write("Enter a competitor part number or an NXP EOL part number below to find the best NXP equivalent.")

    st.subheader("Definition of the Cross-Grade")
    col1, col2 = st.columns([1, 4])
    with col1:
        st.badge("Grade A 🟢: Functional Replacement", color="green")
    with col2:
        st.caption("Best match on Interface, package, pin count, supply voltage, and core features.")

    col1, col2 = st.columns([1, 4])
    with col1:
        st.badge("Grade B 🟡: Near Replacement", color="orange")
    with col2:
        st.caption("Minor differences that may require validation.")

    col1, col2 = st.columns([1, 4])
    with col1:
        st.badge("Grade C 🔴: Partial Replacement", color="red")
    with col2:
        st.caption("Significant differences requiring redesign or qualification.")

    @st.cache_data
    def load_rtc_data():
        df_competitor = pd.read_csv('RTC Cross Reference - Competitors.csv')
        df_nxp = pd.read_csv('RTC Cross Reference - NXP.csv')
        df_competitor.columns = df_competitor.columns.str.strip()
        df_nxp.columns = df_nxp.columns.str.strip()
        return df_competitor, df_nxp

    try:
        df_competitor, df_nxp = load_rtc_data()
    except FileNotFoundError:
        st.error("⚠️ RTC Databases not found. Please ensure the CSV files are in the same folder as this script.")
        return

    part_list = df_competitor['Part number'].dropna().astype(str).str.strip().sort_values().tolist()

    search_query = st.selectbox(
        "Search Competitor RTC Part (Start typing to auto-complete):",
        options=[""] + part_list,
        index=0,
        key="rtc_search_selectbox"
    )

    if search_query != "":
        search_query = search_query.strip().upper() 
        match_part = df_competitor[df_competitor['Part number'].str.strip().str.upper() == search_query]
        
        if match_part.empty:
            st.warning(f"Could not find '{search_query}' in the competitor database. Please check the spelling.")
        else:
            target_part = match_part.iloc[0]
            st.success(f"✅ Found Competitor Part: **{target_part['Part number']}**")
            
            results = []
            target_type = str(target_part['RTC Type']).strip().upper()
            
            for index, nxp_part in df_nxp.iterrows():
                nxp_type = str(nxp_part['RTC Type']).strip().upper()
                
                if target_type != nxp_type:
                    continue 
                    
                score = 0
                target_pkg = str(target_part['Package type']).strip()
                nxp_pkg = str(nxp_part['Package type']).strip()
                if target_pkg == nxp_pkg:
                    score += 40
                    
                target_protocol = str(target_part['Communication Protocol']).strip()
                nxp_protocol = str(nxp_part['Communication Protocol']).strip()
                if target_protocol in nxp_protocol or nxp_protocol in target_protocol: 
                    score += 30
                    
                if str(target_part['Supply Voltage [Min to Max] (V)']).strip() == str(nxp_part['Supply Voltage [Min to Max] (V)']).strip():
                    score += 4
                if str(target_part['Low supply current (uA)']).strip() == str(nxp_part['Low supply current (uA)']).strip():
                    score += 4
                if str(target_part['Battery Back Up']).strip() == str(nxp_part['Battery Back Up']).strip():
                    score += 4
                if str(target_part['SRAM']).strip() == str(nxp_part['SRAM']).strip():
                    score += 10
                if str(target_part['Programmable alarm']).strip() == str(nxp_part['Programmable alarm']).strip():
                    score += 4
                if str(target_part['Operating Temperature (℃)']).strip() == str(nxp_part['Operating Temperature (℃)']).strip():
                    score += 4
                    
                if score == 100: 
                    grade = 'Grade A - Functional Replacement 🟢'
                elif score >= 70: 
                    grade = 'Grade B - Near Replacement 🟡'
                elif score >= 30: 
                    grade = 'Grade C - Partial Replacement 🔴'
                else: 
                    grade = 'No Match'
                    
                if score >= 30:
                    results.append({
                        'NXP Replacement': nxp_part['Part number'],
                        'Datasheet': nxp_part['Datasheet'],
                        'Type': nxp_part['RTC Type'],
                        'Compatibility': grade,
                        'Match Score': score,
                        'Package': nxp_pkg,
                        'Supply Voltage (V)': nxp_part['Supply Voltage [Min to Max] (V)'],
                        'Supply Current (uA)': nxp_part['Low supply current (uA)'],
                        'Interface': nxp_protocol, 
                        'Operating Temp (C)': nxp_part['Operating Temperature (℃)']
                    })           
            
            if results:
                results_df = pd.DataFrame(results).sort_values(by='Match Score', ascending=False)
                
                if target_type == 'IC':
                    results_df = results_df.head(5)
                    
                st.write("### Recommended NXP Replacements")
                
                SHOW_INTERNAL_SCORE = False 
                display_df = results_df.copy()
                if not SHOW_INTERNAL_SCORE:
                    display_df = display_df.drop(columns=['Match Score'])
                
                st.dataframe(
                    display_df, 
                    use_container_width=True, 
                    hide_index=True,
                    column_config={
                        "Datasheet": st.column_config.LinkColumn(
                            "Datasheet",
                            help="Click to open the NXP datasheet",
                            display_text="View PDF" 
                        )
                    }
                )
                
                st.divider()
                st.write("### Comparison Table (Top 2 Matches)")
                
                features_list = [
                    "Supplier", "Type", "Package", "Interface", "Frequency (KHz)",
                    "Voltage [Min-Max] (V)", "Low Supply Current (uA)", "Battery Back Up",
                    "SRAM", "Watchdog timer", "Tamper inputs", "Programmable Alarm",
                    "Automotive grade", "Operating Temp (℃)"
                ]
                
                comp_data = {
                    "Feature": features_list,
                    f"{target_part['Part number']} (Competitor)": [
                        str(target_part.get('Supplier', '-')),
                        str(target_part.get('RTC Type', '-')),
                        str(target_part.get('Package type', '-')),
                        str(target_part.get('Communication Protocol', '-')),
                        str(target_part.get('Baudrate (KHz)', '-')).split('-')[0],
                        str(target_part.get('Supply Voltage [Min to Max] (V)', '-')),
                        str(target_part.get('Low supply current (uA)', '-')),
                        str(target_part.get('Battery Back Up', '-')),
                        str(target_part.get('SRAM', '-')),
                        str(target_part.get('Watchdog Timer', '-')),
                        str(target_part.get('Tamper input', '-')),
                        str(target_part.get('Programmable alarm', '-')),
                        str(target_part.get('AEC-Q100 compliant', '-')),
                        str(target_part.get('Operating Temperature (℃)', '-'))
                    ]
                }
                
                top1_nxp_name = results_df.iloc[0]['NXP Replacement']
                top1_nxp_part = df_nxp[df_nxp['Part number'] == top1_nxp_name].iloc[0]
                
                comp_data[f"{top1_nxp_part['Part number']} (Top 1)"] = [
                        str(top1_nxp_part.get('Supplier', '-')),
                        str(top1_nxp_part.get('RTC Type', '-')),
                        str(top1_nxp_part.get('Package type', '-')),
                        str(top1_nxp_part.get('Communication Protocol', '-')),
                        str(top1_nxp_part.get('Baudrate (KHz)', '-')).split('-')[0],
                        str(top1_nxp_part.get('Supply Voltage [Min to Max] (V)', '-')),
                        str(top1_nxp_part.get('Low supply current (uA)', '-')),
                        str(top1_nxp_part.get('Battery Back Up', '-')),
                        str(top1_nxp_part.get('SRAM', '-')),
                        str(top1_nxp_part.get('Watchdog Timer', '-')),
                        str(top1_nxp_part.get('Tamper input', '-')),
                        str(top1_nxp_part.get('Programmable alarm', '-')),
                        str(top1_nxp_part.get('AEC-Q100 compliant', '-')),
                        str(top1_nxp_part.get('Operating Temperature (℃)', '-'))
                ]
                
                if len(results_df) > 1:
                    top2_nxp_name = results_df.iloc[1]['NXP Replacement']
                    top2_nxp_part = df_nxp[df_nxp['Part number'] == top2_nxp_name].iloc[0]
                    
                    comp_data[f"{top2_nxp_part['Part number']} (Top 2)"] = [
                        str(top2_nxp_part.get('Supplier', '-')),
                        str(top2_nxp_part.get('RTC Type', '-')),
                        str(top2_nxp_part.get('Package type', '-')),
                        str(top2_nxp_part.get('Communication Protocol', '-')),
                        str(top2_nxp_part.get('Baudrate (KHz)', '-')).split('-')[0],
                        str(top2_nxp_part.get('Supply Voltage [Min to Max] (V)', '-')),
                        str(top2_nxp_part.get('Low supply current (uA)', '-')),
                        str(top2_nxp_part.get('Battery Back Up', '-')),
                        str(top2_nxp_part.get('SRAM', '-')),
                        str(top2_nxp_part.get('Watchdog Timer', '-')),
                        str(top2_nxp_part.get('Tamper input', '-')),
                        str(top2_nxp_part.get('Programmable alarm', '-')),
                        str(top2_nxp_part.get('AEC-Q100 compliant', '-')),
                        str(top2_nxp_part.get('Operating Temperature (℃)', '-'))
                    ]
                
                comp_df = pd.DataFrame(comp_data)
                st.dataframe(comp_df, use_container_width=True, hide_index=True)
                
            else:
                st.info(f"No suitable NXP {target_type.title()} replacements found for this part.")


# ==============================================================================
# 7. EXECUTION ROUTER
# ==============================================================================
if selected_tool == "GPIO Expanders":
    render_gpio_tool()
elif selected_tool == "RTC (Real-Time Clocks)":
    render_rtc_tool()

# ==============================================================================
# 8. GLOBAL DISCLAIMER
# ==============================================================================
st.divider()
st.caption("Disclaimer: The cross-reference information provided by this tool is intended for reference purposes only. Customers are responsible for performing their own evaluation and comparison of the suggested devices to ensure suitability for their specific application. It is strongly recommended to review the latest datasheets, specifications, and technical documentation for each device before making any replacement or design decision. Compatibility, performance, and functionality should be independently verified by the customer.")