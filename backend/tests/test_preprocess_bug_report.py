import pytest
from pathlib import Path
from services.preprocess_bug_report import preprocess_bug_report

# Sample bug report content for testing
sample_bug_report_content = """
App crashes if incorrect secret is entered

General information
App version: 0.7.0
App source: built from sources
Android Version: Android 9
Custom ROM: emulator
Same crash on actual devices with app 0.7.0 and 0.6.3.1 from F-Droid.

Expected result

What is expected?
An error message is displayed.

What does happen instead?
App crashes.

Logcat
org.shadowice.flocke.andotp.dev E/AndroidRuntime: FATAL EXCEPTION: main
    Process: org.shadowice.flocke.andotp.dev, PID: 3414
    java.lang.IllegalArgumentException: Last encoded character (before the paddings if any) is a valid base 32 alphabet but not a possible value. Expected the discarded bits to be zero.
        at org.apache.commons.codec.binary.Base32.validateCharacter(Base32.java:577)
        at org.apache.commons.codec.binary.Base32.decode(Base32.java:404)
        at org.apache.commons.codec.binary.BaseNCodec.decode(BaseNCodec.java:482)
        at org.apache.commons.codec.binary.BaseNCodec.decode(BaseNCodec.java:465)
        at org.shadowice.flocke.andotp.Database.Entry.<init>(Entry.java:90)
        at org.shadowice.flocke.andotp.Dialogs.ManualEntryDialog$7.onClick(ManualEntryDialog.java:210)
        at com.android.internal.app.AlertController$ButtonHandler.handleMessage(AlertController.java:172)
        at android.os.Handler.dispatchMessage(Handler.java:106)
        at android.os.Looper.loop(Looper.java:193)
        at android.app.ActivityThread.main(ActivityThread.java:6669)
        at java.lang.reflect.Method.invoke(Native Method)
        at com.android.internal.os.RuntimeInit$MethodAndArgsCaller.run(RuntimeInit.java:493)
        at com.android.internal.os.ZygoteInit.main(ZygoteInit.java:858)

Steps to reproduce
1. Open entry creation dialog ("+" -> Enter details).
2. Enter "test" in the "Secret" field (and fill other required fields).
3. Press "Save".
"""

@pytest.fixture
def setup_bug_report_file(tmp_path):
    """
    Creates a temporary bug report file.
    """
    # Create a sample bug report file
    bug_report_file = tmp_path / "sample_bug_report.txt"
    bug_report_file.write_text(sample_bug_report_content)

    return bug_report_file

def test_preprocess_bug_report(setup_bug_report_file):
    # Set up paths
    bug_report_path = setup_bug_report_file
    result = preprocess_bug_report(bug_report_path)

    # Define expected preprocessed result after stop word removal, lowercasing, and lemmatization
    expected_result = "app crash incorrect secret enter general information app version app source built from source android version android custom rom emulator same crash actual device with app and from droid expect result what expect error message displayed what happen instead app crash logcat org shadowice flocke andotp dev android runtime fatal exception main process org shadowice flocke andotp dev pid java lang illegal argument exception last encode character before the padding any valid base alphabet but not possible value expect the discard bit zero org apache common codec binary base validate character base java org apache common codec binary base decode base java org apache common codec binary base codec decode base codec java org apache common codec binary base codec decode base codec java org shadowice flocke andotp database entry init entry java org shadowice flocke andotp dialog manual entry dialog click manual entry dialog java com android internal app alert controller button handler handle message alert controller java android handler dispatch message handler java android looper loop looper java android app activity thread main activity thread java java lang reflect method invoke native method com android internal runtime init method and args caller run runtime init java com android internal zygote init main zygote init java step reproduce open entry creation dialog enter detail enter test the secret field and fill other require field press save"
    assert result == expected_result, f"Expected '{expected_result}' but got '{result}'"

def test_bug_report_file_not_found(tmp_path):
    # Provide a nonexistent path for bug report file
    non_existent_file = tmp_path / "non_existent_bug_report.txt"
    
    result = preprocess_bug_report(non_existent_file)
    assert result is None, "Expected None when bug report file is not found"

