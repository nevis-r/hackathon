import pikepdf
from lxml import etree
from flask import Flask, render_template, request, send_file
from google import genai
import os
import sys
import tempfile


from system_prompts import SYSTEM_PROMPT_1 


app = Flask(__name__)

class AwardWriter:
    """Writes awards in the DAF 1206 format."""

    # Using a relative path for the template; make sure 'official.pdf' is in the same directory.
    def __init__(self, template_path="official.pdf"):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.template_path = os.path.join(base_dir, template_path)
        self.MODEL = os.environ.get("MODEL", "gemini-2.5-flash")
        self.API_KEY = os.environ.get("API_KEY")
        if not self.API_KEY:
            raise ValueError("API_KEY not found in environment variables.")
        self.client = genai.Client(api_key=self.API_KEY)

    def query_api(self, user_prompt):
        """Query Gemini for text to put into the accomplishments section of the DAF1206 form"""
    
        full_prompt = f"{SYSTEM_PROMPT_1}\n\n{user_prompt}"

        try:
            response = self.client.models.generate_content(
                model=self.MODEL,
                contents=full_prompt,
            )
            
            if response.text:
                return response.text
            else:
                # Handle case where AI returns an empty response
                print("[ERROR] AI returned no text content.")
                return "Error: AI returned no accomplishment text."
        except Exception as e:
            print(f"[ERROR] AI API call failed: {e}")
            return f"Error querying AI: {e}"

    def check_length(self, accomplishments):
        """Splits the accomplishments text into two paragraphs, prioritizing a user-defined 'BREAK' tag."""
        
        break_tag = "BREAK"
        if break_tag in accomplishments:
            # Split the text exactly once based on the user-defined break
            parts = accomplishments.split(break_tag, 1)
            accomplishments_1 = parts[0].strip()
            accomplishments_2 = parts[1].strip()
            
            # Ensure both parts are non-empty after stripping
            if accomplishments_1 and accomplishments_2:
                print("[DEBUG] Split using 'BREAK' tag.")
                return accomplishments_1, accomplishments_2
            
        return accomplishments_1, accomplishments_2

    def format_1206(self, award, category, period, nom_rank, nom_first_name, nom_middle_initial, nom_last_name, agency, duty_title, nom_telephone, address, com_rank, com_first_name, com_middle_initial, com_last_name, com_telephone, accomplishments_1, accomplishments_2, output_path):
        """Create a DAF 1206 PDF from the template, saving it to output_path."""
        
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
            
            # Map form data to XFA fields
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


# Flask Routes

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
        # Use a temporary file path to store the PDF securely before sending
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
        # Handle configuration or file-not-found errors
        return f"Configuration Error: {e}", 500
    except Exception as e:
        # Catch other errors
        return f"An unexpected error occurred: {e}", 500