import pikepdf
from lxml import etree
from flask import Flask, render_template, request, send_file
from google import genai
import os
import sys
import tempfile
import time # Used for the exponential backoff retry logic

from system_prompts import SYSTEM_PROMPT_1 

# --- MODULE LEVEL CONFIGURATION (Reads variables directly from Vercel env) ---
# Vercel injects environment variables directly into os.environ
API_KEY = os.environ.get("API_KEY")
MODEL = os.environ.get("MODEL", "gemini-2.5-flash")

# -----------------------------------------------------------------------------

app = Flask(__name__)

class AwardWriter:
    """Writes awards in the DAF 1206 format."""

    def __init__(self, template_path="official.pdf"):
        
        # --- FIX 1: Robust Path Resolution ---
        # Get the absolute path of the directory where app.py resides.
        # This fixes the "official.pdf not found" error in serverless environments.
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.template_path = os.path.join(base_dir, template_path)
        # ------------------------------------

        self.MODEL = MODEL
        
        # --- FIX 2: Graceful Client Initialization (Prevents 500 Crash) ---
        # Only instantiate the client if the key is present. Do NOT raise an error here.
        if API_KEY:
            self.client = genai.Client(api_key=API_KEY)
        else:
            self.client = None
            # Print error to logs, but allow function to start (avoids 500)
            print("FATAL ERROR: API_KEY not set. AI functions will return error message.")
        # --------------------------------------------

    def query_api(self, user_prompt):
        """Query Gemini for text to put into the accomplishments section of the DAF1206 form"""
        
        # --- Handle Missing Key Gracefully ---
        if not self.client:
            print("[ERROR] API Client not initialized due to missing API_KEY.")
            return "Error: API_KEY is missing. Please configure Vercel environment variables."
        # -------------------------------------

        full_prompt = f"{SYSTEM_PROMPT_1}\n\n{user_prompt}"
        max_retries = 5
        base_delay = 1 # seconds

        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.MODEL,
                    contents=full_prompt,
                )
                
                if response.text:
                    return response.text
                else:
                    print(f"[WARNING] Attempt {attempt+1}: AI returned no text content.")
                    if attempt == max_retries - 1:
                        return "Error: AI returned no accomplishment text after multiple retries."

            except Exception as e:
                error_message = str(e)
                # Check for 503 UNAVAILABLE or other transient errors
                if attempt < max_retries - 1 and ("503 UNAVAILABLE" in error_message or "Internal Server Error" in error_message):
                    delay = base_delay * (2 ** attempt)
                    print(f"[WARNING] Attempt {attempt+1} failed ({e}). Retrying in {delay:.2f}s...")
                    time.sleep(delay)
                else:
                    print(f"[ERROR] AI API call failed definitively: {e}")
                    return f"Error querying AI: {e}"

        # Should be unreachable due to return statements in the loop
        return "Error: Failed to query AI after maximum retries."

    def check_length(self, accomplishments):
        """Checks for the 'BREAK' keyword and splits the accomplishments text into two paragraphs."""
        
        break_keyword = "BREAK"
        
        # 1. Check for explicit "BREAK" keyword
        if break_keyword in accomplishments:
            parts = accomplishments.split(break_keyword, 1)
            # Ensure both parts are clean and not empty
            accomplishments_1 = parts[0].strip()
            accomplishments_2 = parts[1].strip()
            
            # If the split was successful and yielded content, use it
            if accomplishments_1 and accomplishments_2:
                return accomplishments_1, accomplishments_2

        # 2. Fallback to automated midpoint splitting
        mid_point = len(accomplishments) // 2
        split_index = accomplishments.rfind('.', 0, mid_point)

        if split_index != -1 and split_index > 100:
            accomplishments_1 = accomplishments[:split_index + 1].strip()
            accomplishments_2 = accomplishments[split_index + 1:].strip()
        else:
            # If no suitable sentence break is found, just split in the middle
            accomplishments_1 = accomplishments[:mid_point].strip()
            accomplishments_2 = accomplishments[mid_point:].strip()

        return accomplishments_1, accomplishments_2

    def format_1206(self, award, category, period, nom_rank, nom_first_name, nom_middle_initial, nom_last_name, agency, duty_title, nom_telephone, address, com_rank, com_first_name, com_middle_initial, com_last_name, com_telephone, accomplishments_1, accomplishments_2, output_path):
        """Create a DAF 1206 PDF from the template, saving it to output_path."""
        
        # Ensure the template file exists before attempting to open
        if not os.path.exists(self.template_path):
             raise ValueError(f"PDF template file not found at: {self.template_path}")

        # Open the template PDF
        with pikepdf.open(self.template_path) as pdf:

            acroform = pdf.Root.get("/AcroForm", None)
            if acroform is None:
                raise ValueError("No AcroForm found in this PDF")

            xfa = acroform.get("/XFA", None)
            if xfa is None:
                raise ValueError("No XFA data found")

            # Locating the dataset of the XFA
            datasets_xml = None
            for i in range(0, len(xfa), 2):
                name = xfa[i]
                stream = xfa[i + 1]
                if name == b"datasets":
                    datasets_xml = stream.read_bytes().decode("utf-8")
                    break

            if datasets_xml is None:
                raise ValueError("No datasets section found in XFA")

            # To parse and modify the XML
            root = etree.fromstring(datasets_xml.encode("utf-8"))
            
            # --- Map form data to XFA fields ---
            data_map = {
                "award": award,
                "category": category,
                "nomineeTelephone": nom_telephone,
                "awardPeriod": period,
                "majcom_foa_dru": agency,
                "rankName": f"{nom_rank} {nom_first_name} {nom_middle_initial} {nom_last_name}",
                "DAFSC": duty_title,
                "officeAddress": address,
                "rank": f"{com_rank} {com_first_name} {com_middle_initial} {com_last_name} {com_telephone}",
                "specificAccomplishments": accomplishments_1,
                "p2Name": f"{nom_rank} {nom_first_name} {nom_middle_initial} {nom_last_name}",
                "p2SpecificAccomplishments": accomplishments_2
            }

            # Update each field
            for elem in root.iter():
                if elem.tag in data_map:
                    elem.text = data_map[elem.tag]

            # Convert back to bytes
            new_datasets = etree.tostring(root, encoding="utf-8", xml_declaration=False)

            # Replace the datasets stream in the PDF
            for i in range(0, len(xfa), 2):
                name = xfa[i]
                stream = xfa[i + 1]

                if name == b"datasets":
                    stream.write(new_datasets)
                    break

            # Save to new file
            pdf.save(output_path)
            return output_path


# --- Flask Routes ---

@app.route('/')
def index():
    """Renders the HTML form for input."""
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate_award():
    """Handles the form submission, calls the AI and PDF writer, and sends the file."""
    try:
        # Get all form data
        form_data = request.form
        
        # 1. Instantiate the Award Writer
        writer = AwardWriter()
        
        # 2. Query the AI for accomplishments using the 'prompt' from the form
        user_prompt = form_data.get('ai_prompt', 'Write an award for an outstanding Airman.')
        accomplishments = writer.query_api(user_prompt)
        
        # 3. Check length and split
        accomplishments_1, accomplishments_2 = writer.check_length(accomplishments)

        # 4. Generate the PDF and save it to a temporary file
        temp_dir = tempfile.gettempdir()
        temp_file_path = os.path.join(temp_dir, f"DAF1206_{form_data.get('nom_last_name', 'Award')}.pdf")

        writer.format_1206(
            award=form_data.get('award'),
            category=form_data.get('category'),
            period=form_data.get('period'),
            nom_rank=form_data.get('nom_rank'),
            nom_first_name=form_data.get('nom_first_name'),
            nom_middle_initial=form_data.get('nom_middle_initial'),
            nom_last_name=form_data.get('nom_last_name'),
            agency=form_data.get('agency'),
            duty_title=form_data.get('duty_title'),
            nom_telephone=form_data.get('nom_telephone'),
            address=form_data.get('address'),
            com_rank=form_data.get('com_rank'),
            com_first_name=form_data.get('com_first_name'),
            com_middle_initial=form_data.get('com_middle_initial'),
            com_last_name=form_data.get('com_last_name'),
            com_telephone=form_data.get('com_telephone'),
            accomplishments_1=accomplishments_1,
            accomplishments_2=accomplishments_2,
            output_path=temp_file_path
        )

        # 5. Send the file back to the browser for download
        return send_file(
            temp_file_path,
            as_attachment=True,
            mimetype='application/pdf',
            download_name=f"DAF1206_{form_data.get('nom_last_name', 'Award')}.pdf"
        )

    except ValueError as e:
        # Handle configuration or file-not-found errors (like the PDF template being missing)
        return f"Configuration Error: {e}", 500
    except Exception as e:
        # Catch other errors
        return f"An unexpected error occurred: {e}", 500