import streamlit as st  # Web app builder library
import pandas as pd     # Data handling library
from pathlib import Path
from decimal import Decimal, InvalidOperation

# Keep database lookup independent of the directory used to launch Streamlit.
DATA_DIR = Path(__file__).resolve().parent
# The consolidated workbook must be stored next to this script.
DATABASE_PATH = DATA_DIR / "Cross Reference Database.xlsx"


def voltage_number(value):
    """Return a finite decimal voltage, or None for missing/non-numeric data."""
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def voltage_ranges_equal(target, candidate, minimum_column, maximum_column):
    """Keep the original exact-range scoring rule using two numeric limits.

    Missing, non-numeric or inverted ranges never earn voltage match points.
    This checks equality; it does not certify electrical compatibility.
    """
    limits = [voltage_number(row.get(column))
              for row in (target, candidate)
              for column in (minimum_column, maximum_column)]
    if any(value is None for value in limits):
        return False
    target_min, target_max, candidate_min, candidate_max = limits
    return (target_min <= target_max and candidate_min <= candidate_max
            and target_min == candidate_min and target_max == candidate_max)


def load_cross_reference_sheet(sheet_name):
    """Read one consolidated worksheet; keep the existing schema validation."""
    # Text values preserve the original comparison rules and part-number suffixes.
    frame = pd.read_excel(DATABASE_PATH, sheet_name=sheet_name, engine="openpyxl",
                          dtype=str, keep_default_na=False)
    frame.columns = frame.columns.str.strip()
    # The competitor Muxes sheet uses "range" in its voltage headers.
    if sheet_name.startswith("Muxes"):
        frame = frame.rename(columns={
            "Supply voltage range [Min] (V)": "Supply voltage [Min] (V)",
            "Supply voltage range [Max] (V)": "Supply voltage [Max] (V)",
        })
    frame = frame.apply(lambda column: column.str.strip())
    if sheet_name.startswith("GPIO"):
        stems = ["Supply Voltage Side A", "Supply Voltage Side B"]
    elif sheet_name.startswith("RTC"):
        stems = ["Supply Voltage"]
    elif sheet_name.startswith("Muxes"):
        stems = ["Supply voltage"]
    else:
        stems = ["Port A Supply Voltage", "Port B Supply Voltage"]
    required = ["Part number"] + [f"{stem} [{limit}] (V)"
                for stem in stems for limit in ("Min", "Max")]
    if sheet_name.startswith("Muxes"):
        required += ["Type", "Interface", "Frequency (kHz)", "Number of Inputs",
                     "Number of Outputs", "Reset input pin", "Interrupt inputs",
                     "Interrupt outputs", "Number of Addresses", "Package type"]
        if sheet_name.endswith("NXP"):
            required.append("Datasheet")
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"{sheet_name}: missing columns: {', '.join(missing)}")
    return frame



# ==============================================================================
# 1. GLOBAL PAGE CONFIG
# MUST be the very first Streamlit command called in your script.
# ==============================================================================
st.set_page_config(
    page_title="NXP Engineering & Longevity Hub", 
    layout="wide", 
    page_icon="nxp_logo.png"
)

# ==============================================================================
# 2. PASSWORD GATE / ACCESS CONTROL
# ==============================================================================
MASTER_PASSWORD = "1511" 

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    try:
        st.image("nxp_logo.png", width=120)
    except FileNotFoundError:
        st.write("🖼️ Logo")

    st.title("🔒 Restricted Access")
    st.write("Welcome. Please enter the password to continue.")

    user_input = st.text_input("Password:", type="password")

    if st.button("Log In"):
        if user_input == MASTER_PASSWORD:
            st.session_state["authenticated"] = True
            st.success("✅ Password correct!")
            st.rerun()  
        else:
            st.error("❌ Incorrect password. Please try again.")

    st.stop()

# ==============================================================================
# 3. SIDEBAR NAVIGATION (2 MAIN OPTIONS ONLY)
# ==============================================================================
st.sidebar.image("nxp_logo.png", width=100)
st.sidebar.title("Navigation Hub")

nav_options = ["🔄 Cross Reference Tool", "📅 Longevity Request"]

selected_nav = st.sidebar.selectbox("Select Tool:", options=nav_options)

# Sub-navigation only if Cross Reference Tool is active
selected_sub_tool = None
if selected_nav == "🔄 Cross Reference Tool":
    st.sidebar.divider()
    st.sidebar.subheader("Cross-Reference Families")
    selected_sub_tool = st.sidebar.radio(
        "Select Component Type:",
        options=["GPIO Expanders", "RTC (Real-Time Clocks)", "I2C Buffers", "I2C Muxes & Switches"]
    )

st.sidebar.divider()
if st.sidebar.button("🔒 Log Out"):
    st.session_state["authenticated"] = False
    st.rerun()


# ==============================================================================
# TOOL 1.1: GPIO EXPANDERS
# ==============================================================================
def render_gpio_tool():
    st.header("GPIO Expander Cross-Reference")
    st.write("Enter a competitor part number below to find the best NXP equivalent.")

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

    @st.cache_data
    def load_gpio_data():
        df_competitor = load_cross_reference_sheet('GPIO Competitors')
        df_nxp = load_cross_reference_sheet('GPIO NXP')
        df_competitor.columns = df_competitor.columns.str.strip()
        df_nxp.columns = df_nxp.columns.str.strip()
        return df_competitor, df_nxp

    try:
        df_competitor, df_nxp = load_gpio_data()
    except (ValueError, pd.errors.ParserError) as error:
        st.error(f"Database format error: {error}")
        return
    except FileNotFoundError:
        st.error("⚠️ Cross Reference Database.xlsx not found. Please place it in the same folder as this script.")
        return

    part_list = df_competitor['Part number'].dropna().astype(str).str.strip().sort_values().tolist()

    search_query = st.selectbox(
        "Search Competitor Part (Start typing to auto-complete):",
        options=[""] + part_list, 
        index=0,
        key="gpio_search_selectbox"
    )

    if search_query != "":
        search_query = search_query.strip().upper() 
        match_part = df_competitor[df_competitor['Part number'].str.strip().str.upper() == search_query]
        
        if match_part.empty:
            st.warning(f"Could not find '{search_query}' in the competitor database.")
        else:
            target_part = match_part.iloc[0]
            st.success(f"✅ Found Competitor Part: **{target_part['Part number']}**")
            
            results = []
            target_type = str(target_part['AEC-Q100 compliant']).strip().upper()
            target_bits = str(target_part['Number of bits']).strip()
            target_agile = str(target_part.get('Agile', 'N')).strip().upper()
            
            for index, nxp_part in df_nxp.iterrows():
                nxp_type = str(nxp_part['AEC-Q100 compliant']).strip().upper()
                nxp_bits = str(nxp_part['Number of bits']).strip()
                nxp_agile = str(nxp_part.get('Agile', 'N')).strip().upper()
                
                if target_type != nxp_type:
                    continue 

                if target_bits != nxp_bits:
                    continue

                # Filter strictly by Agile status matching the competitor part
                if target_agile != nxp_agile:
                    continue

                score = 30
                target_pkg = str(target_part['Package Type']).strip()
                nxp_pkg = str(nxp_part['Package Type']).strip()
                if target_pkg == nxp_pkg:
                    score += 15
                    
                target_protocol = str(target_part['Interface']).strip()
                nxp_protocol = str(nxp_part['Interface']).strip()
                if target_protocol in nxp_protocol or nxp_protocol in target_protocol: 
                    score += 15
                    
                if voltage_ranges_equal(target_part, nxp_part, 'Supply Voltage Side A [Min] (V)', 'Supply Voltage Side A [Max] (V)'):
                    score += 5
                if voltage_ranges_equal(target_part, nxp_part, 'Supply Voltage Side B [Min] (V)', 'Supply Voltage Side B [Max] (V)'):
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
                    
                if score == 100: 
                    grade = 'Grade A - Functional Replacement 🟢'
                elif score >= 60: 
                    grade = 'Grade B - Near Replacement 🟡'
                elif score >= 30: 
                    grade = 'Grade C - Partial Replacement 🔴'
                else: 
                    grade = 'No Match'
                    
                agile_val = nxp_agile
                    
                if score >= 30:
                    results.append({
                        'NXP Replacement': nxp_part['Part number'],
                        'Datasheet': nxp_part['Datasheet'],
                        'Compatibility': grade,
                        'Number of bits': nxp_part['Number of bits'],
                        'Agile': agile_val,
                        'Match Score': score,
                        'Package': nxp_pkg,
                        'Supply Voltage Side A [Min] (V)': nxp_part['Supply Voltage Side A [Min] (V)'],
                        'Supply Voltage Side A [Max] (V)': nxp_part['Supply Voltage Side A [Max] (V)'],
                        'Supply Voltage Side B [Min] (V)': nxp_part['Supply Voltage Side B [Min] (V)'],
                        'Supply Voltage Side B [Max] (V)': nxp_part['Supply Voltage Side B [Max] (V)'],
                        'Operating Temp (C)': nxp_part['Operating Temperature (Min-Max) (℃)']
                    })           
            
            if results:
                results_df = pd.DataFrame(results)
                results_df['Is_Agile'] = results_df['Agile'].str.upper() == 'Y'
                results_df = results_df.sort_values(by=['Is_Agile', 'Match Score'], ascending=[False, False]).drop(columns=['Is_Agile'])
                
                if target_type == 'N':
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
                    "Supplier", "Number of bits", "Package", "Interface", "Frequency (KHz)", 
                    "Supply Voltage Side A [Min] (V)", "Supply Voltage Side A [Max] (V)", "Supply Voltage Side B [Min] (V)", "Supply Voltage Side B [Max] (V)","Number of address pins", "Max sink current per bit (mA)",
                    "Max source current per bit (mA)", "Interrupt", "Reset input pin", "Operating Temperature (Min-Max) (℃)"
                ]
                
                comp_data = {
                    "Feature": features_list,
                    f"{target_part['Part number']} (Competitor)": [
                        str(target_part.get('Supplier', '-')),
                        str(target_part.get('Number of bits', '-')),
                        str(target_part.get('Package Type', '-')),
                        str(target_part.get('Interface', '-')),
                        str(target_part.get('Baudrate (KHz)', '-')).split('-')[0],
                        str(target_part.get('Supply Voltage Side A [Min] (V)', '-')),
                        str(target_part.get('Supply Voltage Side A [Max] (V)', '-')),
                        str(target_part.get('Supply Voltage Side B [Min] (V)', '-')),
                        str(target_part.get('Supply Voltage Side B [Max] (V)', '-')),
                        str(target_part.get('Number of Address pins', '-')),
                        str(target_part.get('Max Sink Current per bit (mA)', '-')),
                        str(target_part.get('Max Source Current per bit (mA)', '-')),
                        str(target_part.get('Interrupt', '-')),
                        str(target_part.get('Reset input pin', '-')),
                        str(target_part.get('Operating Temperature (Min-Max) (℃)', '-')),
                    ]
                }
                
                top1_nxp_name = results_df.iloc[0]['NXP Replacement']
                top1_nxp_part = df_nxp[df_nxp['Part number'] == top1_nxp_name].iloc[0]
                
                comp_data[f"{top1_nxp_part['Part number']} (Top 1)"] = [
                    str(top1_nxp_part.get('Supplier', '-')),
                    str(top1_nxp_part.get('Number of bits', '-')),
                    str(top1_nxp_part.get('Package Type', '-')),
                    str(top1_nxp_part.get('Interface', '-')),
                    str(top1_nxp_part.get('Baudrate (KHz)', '-')).split('-')[0],
                    str(top1_nxp_part.get('Supply Voltage Side A [Min] (V)', '-')),
                        str(top1_nxp_part.get('Supply Voltage Side A [Max] (V)', '-')),
                    str(top1_nxp_part.get('Supply Voltage Side B [Min] (V)', '-')),
                        str(top1_nxp_part.get('Supply Voltage Side B [Max] (V)', '-')),
                    str(top1_nxp_part.get('Number of Address pins', '-')),
                    str(top1_nxp_part.get('Max Sink Current per bit (mA)', '-')),
                    str(top1_nxp_part.get('Max Source Current per bit (mA)', '-')),
                    str(top1_nxp_part.get('Interrupt', '-')),
                    str(top1_nxp_part.get('Reset input pin', '-')),
                    str(top1_nxp_part.get('Operating Temperature (Min-Max) (℃)', '-')),
                ]
                
                if len(results_df) > 1:
                    top2_nxp_name = results_df.iloc[1]['NXP Replacement']
                    top2_nxp_part = df_nxp[df_nxp['Part number'] == top2_nxp_name].iloc[0]
                    
                    comp_data[f"{top2_nxp_part['Part number']} (Top 2)"] = [
                        str(top2_nxp_part.get('Supplier', '-')),
                        str(top2_nxp_part.get('Number of bits', '-')),
                        str(top2_nxp_part.get('Package Type', '-')),
                        str(top2_nxp_part.get('Interface', '-')),
                        str(top2_nxp_part.get('Baudrate (KHz)', '-')).split('-')[0],
                        str(top2_nxp_part.get('Supply Voltage Side A [Min] (V)', '-')),
                        str(top2_nxp_part.get('Supply Voltage Side A [Max] (V)', '-')),
                        str(top2_nxp_part.get('Supply Voltage Side B [Min] (V)', '-')),
                        str(top2_nxp_part.get('Supply Voltage Side B [Max] (V)', '-')),
                        str(top2_nxp_part.get('Number of Address pins', '-')),
                        str(top2_nxp_part.get('Max Sink Current per bit (mA)', '-')),
                        str(top2_nxp_part.get('Max Source Current per bit (mA)', '-')),
                        str(top2_nxp_part.get('Interrupt', '-')),
                        str(top2_nxp_part.get('Reset input pin', '-')),
                        str(top2_nxp_part.get('Operating Temperature (Min-Max) (℃)', '-')),
                    ]
                
                comp_df = pd.DataFrame(comp_data)
                st.dataframe(comp_df, use_container_width=True, hide_index=True)
            else:
                st.info(f"No suitable NXP replacements found for this part with {target_bits} bits and Agile status '{target_agile}'.")

    st.divider()
    st.caption("⚠️ **Cross-Reference Disclaimer:** The matching scores and recommendations provided are for engineering guidance only. Final qualification and verification remain the responsibility of the system designer.")


# ==============================================================================
# TOOL 1.2: RTC (REAL-TIME CLOCKS)
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
        df_competitor = load_cross_reference_sheet('RTC Competitors')
        df_nxp = load_cross_reference_sheet('RTC NXP')
        df_competitor.columns = df_competitor.columns.str.strip()
        df_nxp.columns = df_nxp.columns.str.strip()
        return df_competitor, df_nxp

    try:
        df_competitor, df_nxp = load_rtc_data()
    except (ValueError, pd.errors.ParserError) as error:
        st.error(f"Database format error: {error}")
        return
    except FileNotFoundError:
        st.error("⚠️ Cross Reference Database.xlsx not found. Please place it in the same folder as this script.")
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
                    
                if voltage_ranges_equal(target_part, nxp_part, 'Supply Voltage [Min] (V)', 'Supply Voltage [Max] (V)'):
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
                        'Supply Voltage [Min] (V)': nxp_part['Supply Voltage [Min] (V)'],
                        'Supply Voltage [Max] (V)': nxp_part['Supply Voltage [Max] (V)'],
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
                    "Supply Voltage [Min] (V)", "Supply Voltage [Max] (V)", "Low Supply Current (uA)", "Battery Back Up",
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
                        str(target_part.get('Baudrate', '-')),
                        str(target_part.get('Supply Voltage [Min] (V)', '-')),
                        str(target_part.get('Supply Voltage [Max] (V)', '-')),
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
                        str(top1_nxp_part.get('Baudrate', '-')),
                        str(top1_nxp_part.get('Supply Voltage [Min] (V)', '-')),
                        str(top1_nxp_part.get('Supply Voltage [Max] (V)', '-')),
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
                        str(top2_nxp_part.get('Baudrate', '-')),
                        str(top2_nxp_part.get('Supply Voltage [Min] (V)', '-')),
                        str(top2_nxp_part.get('Supply Voltage [Max] (V)', '-')),
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

    st.divider()
    st.caption("⚠️ **Cross-Reference Disclaimer:** The matching scores and recommendations provided are for engineering guidance only. Final qualification and verification remain the responsibility of the system designer.")


# ==============================================================================
# TOOL 1.3: I2C BUFFERS 
# ==============================================================================
def render_buffer_tool():
    st.header("I2C Buffer Cross-Reference Search")
    st.write("Enter a competitor part number below to find the best NXP equivalent.")

    st.subheader("Definition of the Cross-Grade")
    col1, col2 = st.columns([1, 4])
    with col1:
        st.badge("Grade A 🟢: Functional Replacement", color="green")
    with col2:
        st.caption("Best match on interface, package, type of offset, capacitive strength, supply voltages, and core features.")

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
    def load_buffer_data():
        df_competitor = load_cross_reference_sheet('Buffers Competitors')
        df_nxp = load_cross_reference_sheet('Buffers NXP')
        df_competitor.columns = df_competitor.columns.str.strip()
        df_nxp.columns = df_nxp.columns.str.strip()
        return df_competitor, df_nxp

    try:
        df_competitor, df_nxp = load_buffer_data()
    except (ValueError, pd.errors.ParserError) as error:
        st.error(f"Database format error: {error}")
        return
    except FileNotFoundError:
        st.error("⚠️ Cross Reference Database.xlsx not found. Please place it in the same folder as this script.")
        return

    part_list = df_competitor['Part number'].dropna().astype(str).str.strip().sort_values().tolist()

    search_query = st.selectbox(
        "Search Competitor Buffer Part (Start typing to auto-complete):",
        options=[""] + part_list,
        index=0,
        key="buffer_search_selectbox"
    )

    if search_query != "":
        search_query = search_query.strip().upper() 
        match_part = df_competitor[df_competitor['Part number'].str.strip().str.upper() == search_query]
        
        if match_part.empty:
            st.warning(f"Could not find '{search_query}' in the competitor database.")
        else:
            target_part = match_part.iloc[0]
            st.success(f"✅ Found Competitor Part: **{target_part['Part number']}**")
            
            results = []
            target_bits = str(target_part['Number of bits']).replace('.0', '').strip()
            target_offset = str(target_part.get('Type of Offset', '')).strip().upper()
            
            for index, nxp_part in df_nxp.iterrows():
                nxp_bits = str(nxp_part['Number of bits']).replace('.0', '').strip()
                nxp_offset = str(nxp_part.get('Type of Offset', '')).strip().upper()
                
                if target_bits != nxp_bits:
                    continue 

                if target_offset and nxp_offset and target_offset != nxp_offset:
                    continue

                score = 30
                
                target_pkg = str(target_part['Package type']).strip()
                nxp_pkg = str(nxp_part['Package type']).strip()
                if target_pkg == nxp_pkg:
                    score += 30
                    
                target_protocol = str(target_part['Interface']).strip()
                nxp_protocol = str(nxp_part['Interface']).strip()
                if target_protocol in nxp_protocol or nxp_protocol in target_protocol: 
                    score += 20
                    
                if str(target_part['Frequency (KHz)']).strip() == str(nxp_part['Frequency (KHz)']).strip():
                    score += 10
                if voltage_ranges_equal(target_part, nxp_part, 'Port A Supply Voltage [Min] (V)', 'Port A Supply Voltage [Max] (V)'):
                    score += 5
                if voltage_ranges_equal(target_part, nxp_part, 'Port B Supply Voltage [Min] (V)', 'Port B Supply Voltage [Max] (V)'):
                    score += 5
                if str(target_part['Hot swappable']).strip() == str(nxp_part['Hot swappable']).strip():
                    score += 5
                if str(target_part['Operating temperature range (°C)']).strip() == str(nxp_part['Operating temperature range (°C)']).strip():
                    score += 5
                if target_offset == nxp_offset and target_offset != '':
                    score += 10
                if str(target_part['Capacitive strength']).strip() == str(nxp_part['Capacitive strength']).strip():
                    score += 10
                    
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
                        'Compatibility': grade,
                        'Match Score': score,
                        'Package': nxp_pkg,
                        'Capacitive strength': nxp_part['Capacitive strength'], 
                        'Port A Supply Voltage [Min] (V)': nxp_part['Port A Supply Voltage [Min] (V)'],
                        'Port A Supply Voltage [Max] (V)': nxp_part['Port A Supply Voltage [Max] (V)'],
                        'Port B Supply Voltage [Min] (V)': nxp_part['Port B Supply Voltage [Min] (V)'],
                        'Port B Supply Voltage [Max] (V)': nxp_part['Port B Supply Voltage [Max] (V)'],
                        'Operating Temp (°C)': nxp_part['Operating temperature range (°C)']
                    })           
            
            if results:
                results_df = pd.DataFrame(results).sort_values(by='Match Score', ascending=False).head(5)
                
                st.write("### Recommended NXP Replacements")
                
                display_df = results_df.drop(columns=['Match Score'])
                
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
                    "Supplier", "Type", "Package", "Interface", "Frequency (KHz)", "Type of Offset", "Capacitive strength",
                    "Port A Supply Voltage [Min] (V)", "Port A Supply Voltage [Max] (V)", "Port B Supply Voltage [Min] (V)", "Port B Supply Voltage [Max] (V)", 
                    "Hot swappable", "Automotive grade", "Operating Temp (°C)"
                ]
                
                comp_data = {
                    "Feature": features_list,
                    f"{target_part['Part number']} (Competitor)": [
                        str(target_part.get('Supplier', '-')),
                        str(target_part.get('Type', '-')),
                        str(target_part.get('Package type', '-')),
                        str(target_part.get('Interface', '-')),
                        str(target_part.get('Frequency (KHz)', '-')),
                        str(target_part.get('Type of Offset', '-')),
                        str(target_part.get('Capacitive strength', '-')),
                        str(target_part.get('Port A Supply Voltage [Min] (V)', '-')),
                        str(target_part.get('Port A Supply Voltage [Max] (V)', '-')),
                        str(target_part.get('Port B Supply Voltage [Min] (V)', '-')),
                        str(target_part.get('Port B Supply Voltage [Max] (V)', '-')),
                        str(target_part.get('Hot swappable', '-')),
                        str(target_part.get('Automotive grade', '-')),
                        str(target_part.get('Operating temperature range (°C)', '-')),
                    ]
                }
                
                top1_nxp_name = results_df.iloc[0]['NXP Replacement']
                top1_nxp_part = df_nxp[df_nxp['Part number'] == top1_nxp_name].iloc[0]
                
                comp_data[f"{top1_nxp_part['Part number']} (Top 1)"] = [
                    "NXP",
                    str(top1_nxp_part.get('Type', '-')),
                    str(top1_nxp_part.get('Package type', '-')),
                    str(top1_nxp_part.get('Interface', '-')),
                    str(top1_nxp_part.get('Frequency (KHz)', '-')),
                    str(top1_nxp_part.get('Type of Offset', '-')),
                    str(top1_nxp_part.get('Capacitive strength', '-')),
                    str(top1_nxp_part.get('Port A Supply Voltage [Min] (V)', '-')),
                        str(top1_nxp_part.get('Port A Supply Voltage [Max] (V)', '-')),
                    str(top1_nxp_part.get('Port B Supply Voltage [Min] (V)', '-')),
                        str(top1_nxp_part.get('Port B Supply Voltage [Max] (V)', '-')),
                    str(top1_nxp_part.get('Hot swappable', '-')),
                    str(top1_nxp_part.get('Automotive grade', '-')),
                    str(top1_nxp_part.get('Operating temperature range (°C)', '-')),
                ]
                
                if len(results_df) > 1:
                    top2_nxp_name = results_df.iloc[1]['NXP Replacement']
                    top2_nxp_part = df_nxp[df_nxp['Part number'] == top2_nxp_name].iloc[0]
                    
                    comp_data[f"{top2_nxp_part['Part number']} (Top 2)"] = [
                        "NXP",
                        str(top2_nxp_part.get('Type', '-')),
                        str(top2_nxp_part.get('Package type', '-')),
                        str(top2_nxp_part.get('Interface', '-')),
                        str(top2_nxp_part.get('Frequency (KHz)', '-')),
                        str(top2_nxp_part.get('Type of Offset', '-')),
                        str(top2_nxp_part.get('Capacitive strength', '-')),
                        str(top2_nxp_part.get('Port A Supply Voltage [Min] (V)', '-')),
                        str(top2_nxp_part.get('Port A Supply Voltage [Max] (V)', '-')),
                        str(top2_nxp_part.get('Port B Supply Voltage [Min] (V)', '-')),
                        str(top2_nxp_part.get('Port B Supply Voltage [Max] (V)', '-')),
                        str(top2_nxp_part.get('Hot swappable', '-')),
                        str(top2_nxp_part.get('Automotive grade', '-')),
                        str(top2_nxp_part.get('Operating temperature range (°C)', '-')),
                    ]
                
                comp_df = pd.DataFrame(comp_data)
                st.dataframe(comp_df, use_container_width=True, hide_index=True)
            else:
                st.info(f"No suitable NXP replacements found for this part.")

    st.divider()
    st.caption("⚠️ **Cross-Reference Disclaimer:** The matching scores and recommendations provided are for engineering guidance only. Final qualification and verification remain the responsibility of the system designer.")


# ==============================================================================
# TOOL 1.4: I2C MUXES & SWITCHES
# ==============================================================================
def render_mux_tool():
    """Search the two Muxes worksheets without changing the other families."""
    st.header("I2C Muxes & Switches Cross-Reference")
    st.write("Enter a competitor part number below to find NXP candidates.")


    st.subheader("Definition of the Cross-Grade")
    col1, col2 = st.columns([1, 4])
    with col1:
        st.badge("Grade A 🟢: Functional Replacement", color="green")
    with col2:
        st.caption("Best match on device type, interface, package, supply voltages, and core features.")

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
    def load_mux_data():
        return (load_cross_reference_sheet("Muxes Competitors"),
                load_cross_reference_sheet("Muxes NXP"))

    try:
        df_competitor, df_nxp = load_mux_data()
    except FileNotFoundError:
        st.error("Cross Reference Database.xlsx not found. Please place it next to this script.")
        return
    except ValueError as error:
        st.error(f"Muxes database format error: {error}")
        return

    # Normalize local text values only; source worksheet values are not modified.
    def normalized(value):
        return str(value).strip().upper().replace("²", "2").replace("³", "3")

    def count_value(value):
        # The Muxes worksheets use N/No to mean zero interrupt pins.
        return Decimal(0) if normalized(value) in {"N", "NO"} else voltage_number(value)

    def same_known_value(left, right):
        missing = {"", "-", "—", "NA", "N/A", "NAN"}
        a, b = normalized(left), normalized(right)
        return a not in missing and b not in missing and a == b

    options = df_competitor["Part number"].dropna().astype(str).str.strip().drop_duplicates().sort_values().tolist()
    query = st.selectbox("Search Competitor Mux / Switch Part:", [""] + options,
                         key="mux_search_selectbox")
    if not query:
        return
    variants = df_competitor[
        df_competitor["Part number"].str.strip().str.upper() == query.strip().upper()
    ].drop_duplicates()
    # One part number can represent multiple packages. Ask only when necessary.
    if len(variants) > 1:
        selected_index = st.selectbox(
            "Select competitor variant:", variants.index.tolist(),
            format_func=lambda index: (
                f"{variants.loc[index, 'Package type']} | "
                f"{variants.loc[index, 'Interface']} | source row {index + 2}"
            ), key="mux_variant_selectbox",
        )
        target_part = variants.loc[selected_index]
    else:
        target_part = variants.iloc[0]
    st.success(f"Found Competitor Part: **{target_part['Part number']}**")

    # These parameters define a usable search. Unknown values cannot establish
    # interface, topology or supply compatibility, so do not guess their values.
    target_type = normalized(target_part["Type"])
    target_interface = normalized(target_part["Interface"])
    target_inputs = count_value(target_part["Number of Inputs"])
    target_outputs = count_value(target_part["Number of Outputs"])
    target_min = voltage_number(target_part["Supply voltage [Min] (V)"])
    target_max = voltage_number(target_part["Supply voltage [Max] (V)"])
    if (not target_type or not target_interface
            or any(value is None for value in (target_inputs, target_outputs, target_min, target_max))
            or target_min > target_max):
        st.warning("The source record has missing or invalid type, interface, topology or voltage data. "
                   "Complete these fields before searching for a replacement.")
        return

    results = []
    for index, nxp_part in df_nxp.drop_duplicates().iterrows():
        # Gate the essential properties before awarding similarity points.
        if normalized(nxp_part["Type"]) != target_type:
            continue
        if normalized(nxp_part["Interface"]) != target_interface:
            continue
        if (count_value(nxp_part["Number of Inputs"]) != target_inputs
                or count_value(nxp_part["Number of Outputs"]) != target_outputs):
            continue
        nxp_min = voltage_number(nxp_part["Supply voltage [Min] (V)"])
        nxp_max = voltage_number(nxp_part["Supply voltage [Max] (V)"])
        if (nxp_min is None or nxp_max is None or nxp_min > nxp_max
                or nxp_min > target_min or nxp_max < target_max):
            continue
        target_frequency = voltage_number(target_part["Frequency (kHz)"])
        nxp_frequency = voltage_number(nxp_part["Frequency (kHz)"])
        if (target_frequency is not None and nxp_frequency is not None
                and nxp_frequency < target_frequency):
            continue
        if normalized(target_part["Reset input pin"]) in {"Y", "YES"} and normalized(nxp_part["Reset input pin"]) in {"N", "NO"}:
            continue

        # Weights total 100: type 15, interface 20, inputs 5, outputs 10,
        # voltage coverage 10, package 20, frequency 10, reset 3,
        # interrupt inputs 2, interrupt outputs 2, available addresses 3.
        score = 60  # Essential matching properties plus full supply coverage.
        differences = []
        if same_known_value(target_part["Package type"], nxp_part["Package type"]):
            score += 20
        else:
            differences.append("Different or unknown package; verify footprint and pinout")
        if target_frequency is not None and nxp_frequency is not None and nxp_frequency >= target_frequency:
            score += 10
        else:
            differences.append("Bus frequency requires verification")
        if same_known_value(target_part["Reset input pin"], nxp_part["Reset input pin"]):
            score += 3
        else:
            differences.append("Reset input differs or is unknown")
        rejected = False
        for column, weight in (("Interrupt inputs", 2), ("Interrupt outputs", 2),
                               ("Number of Addresses", 3)):
            target_count, nxp_count = count_value(target_part[column]), count_value(nxp_part[column])
            if target_count is not None and nxp_count is not None:
                if nxp_count < target_count:
                    rejected = True
                    break
                score += weight
                if nxp_count != target_count:
                    differences.append(f"{column} differs; verify behavior")
            else:
                differences.append(f"{column} requires verification")
        if rejected:
            continue
        grade = ("Grade A - Parametric Candidate 🟢" if score == 100 and not differences
                 else "Grade B - Near Replacement 🟡" if score >= 60
                 else "Grade C - Partial Replacement 🔴")
        results.append({
            "NXP Replacement": nxp_part["Part number"], "Datasheet": nxp_part["Datasheet"],
            "Compatibility": grade, "Match Score": score,
            "Package": nxp_part["Package type"], "Interface": nxp_part["Interface"],
            "Supply voltage [Min] (V)": nxp_part["Supply voltage [Min] (V)"],
            "Supply voltage [Max] (V)": nxp_part["Supply voltage [Max] (V)"],
            "Review notes": "; ".join(differences) or "Verify pinout, registers and operating conditions",
            "Source index": index,
        })

    if not results:
        st.info("No suitable NXP candidates found for the recorded interface, topology and voltage requirements.")
    else:
        results_df = pd.DataFrame(results).sort_values("Match Score", ascending=False, kind="stable").head(5)
        st.write("### Recommended NXP Replacements")
        st.dataframe(results_df.drop(columns=["Match Score", "Source index"]),
                     use_container_width=True, hide_index=True,
                     column_config={"Datasheet": st.column_config.LinkColumn(
                         "Datasheet", display_text="View PDF")})
        st.divider()
        st.write("### Comparison Table (Top 2 Matches)")
        features = ["Supplier", "Type", "Interface", "Package type", "Frequency (kHz)",
                    "Supply voltage [Min] (V)", "Supply voltage [Max] (V)",
                    "Number of Inputs", "Number of Outputs", "Reset input pin",
                    "Interrupt inputs", "Interrupt outputs", "Number of Addresses",
                    "Operating Temperature (Min-Max) (℃)"]
        comparison = {"Feature": features,
                      f"{target_part['Part number']} (Competitor)": [str(target_part.get(key, "-")) for key in features]}
        for position, (_, result) in enumerate(results_df.head(2).iterrows(), start=1):
            # Retain the exact ranked variant, rather than looking it up by name.
            candidate = df_nxp.loc[result["Source index"]]
            comparison[f"{candidate['Part number']} (Top {position})"] = [
                "NXP" if key == "Supplier" else str(candidate.get(key, "-")) for key in features]
        st.dataframe(pd.DataFrame(comparison), use_container_width=True, hide_index=True)
    st.divider()
    st.caption("Cross-reference guidance only. Verify pinout, register map and electrical operating conditions before qualification.")


# ==============================================================================
# TOOL 2: LONGEVITY REQUEST
# ==============================================================================
def render_longevity_tool():
    st.header("Product Longevity & Lifecycle Lookup")
    st.write("Search for a product part number below to check its projected longevity date (Next Gen List).")

    @st.cache_data
    def load_longevity_data():
        file_path = 'PL-PAI - Longevity requests _ responses.xlsx'
        xls = pd.ExcelFile(file_path)
        sheet_to_use = 'Next Gen List' if 'Next Gen List' in xls.sheet_names else xls.sheet_names[0]
        df = pd.read_excel(file_path, sheet_name=sheet_to_use)
        df.columns = df.columns.str.strip()
        return df

    try:
        df_longevity = load_longevity_data()
    except FileNotFoundError:
        st.error("⚠️ Longevity database file 'PL-PAI - Longevity requests _ responses.xlsx' not found in the working directory.")
        return
    except Exception as e:
        st.error(f"⚠️ Error loading Longevity database: {e}")
        return

    col_product = df_longevity.columns[0]
    col_4tg = df_longevity.columns[1] if len(df_longevity.columns) > 1 else None
    col_package = df_longevity.columns[3] if len(df_longevity.columns) > 3 else None
    col_longevity = df_longevity.columns[28] if len(df_longevity.columns) > 28 else df_longevity.columns[-1]
    col_date = df_longevity.columns[10] if len(df_longevity.columns) > 10 else None

    df_longevity['clean_product'] = df_longevity[col_product].astype(str).str.strip()
    product_list = df_longevity['clean_product'].dropna().unique().tolist()
    product_list.sort()

    search_query = st.selectbox(
        "Search Product (Start typing to auto-complete):",
        options=[""] + product_list,
        index=0,
        key="longevity_search_selectbox"
    )

    if search_query != "":
        search_query_clean = search_query.strip()
        match_rows = df_longevity[df_longevity['clean_product'].str.upper() == search_query_clean.upper()]
        
        if match_rows.empty:
            st.warning(f"Could not find '{search_query}' in the Next Gen List database.")
        else:
            if col_date is not None and len(match_rows) > 1:
                match_rows = match_rows.copy()
                match_rows['temp_date'] = pd.to_datetime(match_rows[col_date], errors='coerce')
                match_rows = match_rows.sort_values(by='temp_date', ascending=False)
                product_data = match_rows.iloc[0]
            else:
                product_data = match_rows.iloc[0]

            prod_val = str(product_data[col_product]) if col_product else "-"
            tg4_val = str(product_data[col_4tg]) if col_4tg and col_4tg in product_data else "-"
            pkg_val = str(product_data[col_package]) if col_package and col_package in product_data else "-"
            
            raw_longevity_date = product_data[col_longevity]
            
            formatted_date = str(raw_longevity_date)
            parsed_date = pd.to_datetime(raw_longevity_date, errors='coerce')
            if pd.notnull(parsed_date):
                formatted_date = parsed_date.strftime('%m-%Y')

            st.success(f"✅ Found Product Record: **{search_query}**")
            
            summary_df = pd.DataFrame([{
                "Product": prod_val,
                "4TG": tg4_val,
                "Package": pkg_val,
                "Longevity Date": formatted_date
            }])

            st.dataframe(summary_df, use_container_width=True, hide_index=True)

            st.markdown(
                f"""
                <div style="padding: 15px; border-radius: 8px; background-color: #f0f2f6; text-align: center; margin-top: 10px;">
                    <span style="font-size: 16px; font-weight: bold; color: #31333F;">Longevity Date: </span>
                    <span style="font-size: 26px; font-weight: bold; color: #0066cc;">{formatted_date}</span>
                </div>
                """,
                unsafe_allow_html=True
            )

    st.divider()
    st.caption("📅 **Longevity Disclaimer:** Product availability commitments and lifecycle forecasts are subject to change based on manufacturing capacity and market conditions. Please consult with your NXP representative for official commitments.")


# ==============================================================================
# 4. MAIN ROUTER (DIRECT RENDER BASED ON SIDEBAR SELECTION)
# ==============================================================================
try:
    st.image("nxp_logo.png", width=120)
except FileNotFoundError:
    st.write("🖼️ Logo")

if selected_nav == "🔄 Cross Reference Tool":
    if selected_sub_tool == "GPIO Expanders":
        render_gpio_tool()
    elif selected_sub_tool == "RTC (Real-Time Clocks)":
        render_rtc_tool()
    elif selected_sub_tool == "I2C Buffers":
        render_buffer_tool()
    elif selected_sub_tool == "I2C Muxes & Switches":
        render_mux_tool()

elif selected_nav == "📅 Longevity Request":
    render_longevity_tool()
