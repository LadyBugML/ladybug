import argparse
import json
import os

def process_json_file(input_path):
    """Process a JSON file, converting it to a single-line escaped JSON string."""
    with open(input_path, "r", encoding="utf-8") as file:
        json_content = json.load(file)  # Load JSON to ensure it's valid

    # Convert JSON object to a compact single-line string
    single_line_json = json.dumps(json_content, separators=(",", ":"))

    # Escape the string for use as a JSON value
    return json.dumps(single_line_json)

def process_text_file(input_path):
    """Process a plain text file, escaping it properly."""
    with open(input_path, "r", encoding="utf-8") as file:
        text_content = file.read()

    # Escape the string for use as a JSON value
    return json.dumps(text_content)

def convert_file(input_path):
    """Determine the file type and process accordingly."""
    if not os.path.isfile(input_path):
        print(f"Error: The file '{input_path}' does not exist.")
        return

    # Determine file type
    file_extension = os.path.splitext(input_path)[1].lower()

    if file_extension == ".json":
        escaped_string = process_json_file(input_path)
    elif file_extension == ".txt":
        escaped_string = process_text_file(input_path)
    else:
        print(f"Error: Unsupported file type '{file_extension}'. Please provide a .json or .txt file.")
        return

    # Generate output file path
    output_path = os.path.splitext(input_path)[0] + "-escaped.txt"

    # Write the escaped string to the output file
    with open(output_path, "w", encoding="utf-8") as output_file:
        output_file.write(escaped_string)

    print(f"Escaped single-line string saved to: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert a JSON or text file to an escaped single-line string.")
    parser.add_argument("input_path", help="Path to the JSON or text file")
    args = parser.parse_args()

    convert_file(args.input_path)
