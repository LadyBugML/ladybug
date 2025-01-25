from services.extract_gui_data import extract_sc_terms
from services.extract_gui_data import extract_gs_terms
from services.extract_gui_data import build_corpus

def test_extract_SC_terms():
    json_path = "temp_testing/Execution-1.json"

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

def test_extract_GS_terms():
    json_path = "temp_testing/Execution-1.json"

    expected_gs_terms = [
        'AddFeedFragment',
        'DashboardActivity',
        'SubscriptionFragment',
        'TemplateActivity'
    ]

    extracted_terms = sorted(extract_gs_terms(json_path))

    assert extracted_terms == expected_gs_terms, f"Mismatch: {extracted_terms}"

def test_build_corpus():
    sc_terms = [
        'add_expense',
        'content',
        'select_account',
        'toolbar'
    ]

    source_code_files = [
        ('path/to/Expenses.java', 'Expenses.java', 'public static void main(String[] args) { int add_expense = 5;}'),
        ('path/to/file1', 'file1', 'mock code'),
        ('path/to/file2', 'file1', 'mock code'),
        ('path/to/ToolbarScreen.java', 'ToolbarScreen.java', 'public static void main(String[] args) { int toolbar = 5;}'),
        ('path/to/file3', 'file1', 'mock code'),
        ('path/to/file1', 'file1', 'mock code'),
    ]

    expected_corpus_files = [
        'path/to/Expenses.java',
        'path/to/ToolbarScreen.java'
    ]

    corpus_files = build_corpus(source_code_files, sc_terms)

    assert corpus_files == expected_corpus_files, f"Mismatch: {corpus_files}"