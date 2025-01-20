from services.extract_gui_data import extract_sc_terms

def test_extract_SC_terms():
    json_path = "temp_testing/Execution-1.json" # Replace with the actual path to your test file

    expected_sc_terms = [
        "action_bar_root",
        "add_expense",
        "add_income",
        "add_transfer",
        "content",
        "dashboard_layout",
        "entity_fragment",
        "material_drawer_divider",
        "material_drawer_icon",
        "material_drawer_layout",
        "material_drawer_name",
        "material_drawer_recycler_view",
        "material_drawer_slider_layout",
        "navigationBarBackground",
        "recycler_view",
        "select_account",
        "select_charts",
        "select_expenses",
        "select_flow_of_funds",
        "select_income",
        "select_sms_patterns",
        "select_templates",
        "select_transfers",
        "statusBarBackground",
        "toolbar",
    ]

    extracted_terms = sorted(extract_sc_terms(json_path))

    assert extracted_terms == expected_sc_terms, f"Mismatch: {extracted_terms}"