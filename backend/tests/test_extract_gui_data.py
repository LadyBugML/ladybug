from utils.extract_gui_data import extract_sc_terms, extract_gs_terms, build_corpus, get_boosted_files
from tests.constants import TEST_EXECUTION_JSON_STRING

def test_extract_SC_terms():
    json_string = TEST_EXECUTION_JSON_STRING

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

    extracted_terms = sorted(extract_sc_terms(json_string))

    assert extracted_terms == expected_sc_terms, f"Mismatch: {extracted_terms}"

def test_extract_GS_terms():
    json_string = TEST_EXECUTION_JSON_STRING

    expected_gs_terms = [
        'AddFeedFragment',
        'DashboardActivity',
        'SubscriptionFragment',
        'TemplateActivity'
    ]

    extracted_terms = sorted(extract_gs_terms(json_string))

    assert extracted_terms == expected_gs_terms, f"Mismatch: {extracted_terms}"

def test_build_corpus():
    repo_info = {
        "repo_name": "some-repo",
        "owner": "someone"
    }
    sc_terms = [
        'add_expense',
        'content',
        'select_account',
        'toolbar'
    ]

    source_code_files = [
        ('repos/someone/some-repo/path/to/Expenses.java', 'Expenses.java', 'public static void main(String[] args) { int add_expense = 5;}'),
        ('repos/someone/some-repo/path/to/file1', 'file1', 'mock code'),
        ('repos/someone/some-repo/path/to/file2', 'file1', 'mock code'),
        ('repos/someone/some-repo/path/to/ToolbarScreen.java', 'ToolbarScreen.java', 'public static void main(String[] args) { int toolbar = 5;}'),
        ('repos/someone/some-repo/path/to/file3', 'file1', 'mock code'),
        ('repos/someone/some-repo/path/to/file1', 'file1', 'mock code'),
    ]

    expected_corpus_files = [
        'path/to/Expenses.java',
        'path/to/ToolbarScreen.java'
    ]

    corpus_files = build_corpus(source_code_files, sc_terms, repo_info)

    assert corpus_files == expected_corpus_files, f"Mismatch: {corpus_files}"

def test_get_boosted_files():
    gs_terms = [
        'AddFeedFragment',
        'DashboardActivity',
        'SubscriptionFragment',
        'TemplateActivity'
    ]

    source_code_files = [
        ('path/to/AddFeedFragment.java', 'AddFeedFragment.java', 'mock code'),
        ('path/to/file1', 'file1', 'mock code'),
        ('path/to/file2', 'file1', 'mock code'),
        ('path/to/DashboardActivity.java', 'DashboardActivity.java', 'mock code'),
        ('path/to/file3', 'file1', 'mock code'),
        ('path/to/file1', 'file1', 'mock code'),
    ]

    expected_boosted_files = [
        'path/to/AddFeedFragment.java',
        'path/to/DashboardActivity.java'
    ]

    boosted_files = get_boosted_files(source_code_files, gs_terms)

    assert boosted_files == expected_boosted_files, f"Mismatch: {boosted_files}"