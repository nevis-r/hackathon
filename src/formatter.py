
# Latest Guidance
# https://static.e-publishing.af.mil/production/1/af_a1/form/daf1206/daf1206.pdf
# https://static.e-publishing.af.mil/production/1/af_a1/publication/dafman36-2806/dafman36_2806.pdf
#
# Guidance for accomplishments section:
# - No Bullet Points
# - Use Narrative Style Performance Statements
# - Use 1 page unless otherwise specified for the award

import pikepdf
from lxml import etree
from google import genai
from dotenv import load_dotenv
import os
import sys
from system_prompts import SYSTEM_PROMPT_1

class AwardWriter:
    """Writes awards in the DAF 1206 format."""

    def __init__(self):
        self.template_path = "official.pdf"
        self.output_path = "generated.pdf"

    # Untested
    def query_api(self, prompt):
        """Query Ask Sage for text to put into the accomplishments section of the DAF1206 form"""
        load_dotenv()
        MODEL = os.environ.get("MODEL")
        API_KEY = os.environ.get("API_KEY")

        # Get user prompt from CLI
        args = []
        for arg in sys.argv[1:]:
            if not arg.startswith("--"):
                args.append(arg)

        if not args:
            print("Unofficial AF Award Writer AI\n")
            print('Usage: python main.py "your prompt here"\n')
            print("NO CUI\n")
            sys.exit(1)

        system_prompt = SYSTEM_PROMPT_1
        user_prompt = " ".join(args)
        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        client = genai.Client(api_key=API_KEY)
        
        response = client.models.generate_content(
        model=MODEL,
        contents=full_prompt,
        )

        print(response)

        # Check if the response contains text before returning
        if response.text:
            return response.text
        else:
            # Handle case where AI returns an empty response
            print("[ERROR] AI returned no text content.")
            sys.exit(1)

    # NOT IMPLEMENTED
    def check_length(self, accomplishments):
        """Checks how many lines the accomplishments text is and splits it into two appropriately sized paragraphs for the DAF1206 form. Error if too long"""
        return (accomplishments, "")

    def format_1206(self, award, category, period, nom_rank, nom_first_name, nom_middle_initial, nom_last_name, agency, duty_tile, nom_telephone, address, com_rank, com_first_name, com_middle_initial, com_last_name, com_telephone, accomplishments_1, accomplishments_2, output_path = "1206output.pdf"):
        """Create a DAF 1206 PDF

        Keyword arguments:
        award -- the name of the award nominated for
        category -- ???
        period -- ???
        nom_rank -- the rank of the nominee
        nom_first_name -- the first name of the nominee
        nom_middle_initial -- the middle initial of the nominee
        nom_last_name -- the last name of the nominee
        agency -- the MAJCOM, FLDCOM, DOA, or DRU of the nominee
        duty_tile -- the nominee's DAFSC or Duty Title
        nom_telephone -- The nominee's telephone number (DSN & Commercial)
        address -- the unit's office symbols/street address including the base, state, and zipcode
        com_rank -- the unit commander's rank
        com_first_name -- the unit commander's first name
        com_middle_initial -- the unit commander's middle initial
        com_last_name -- the unit commander's last name
        com_telephone -- the unit commander's telephone number (DSN & Commercial)
        accomplishments -- the accomplishments of the nominee. This is the primary paragraph which 
            represents the content of the awards package.
        output_path -- the path and filename of the saved pdf
        """

        # Open the template PDF
        with pikepdf.open(self.template_path) as pdf:

            # Access the AcroForm dictionary
            acroform = pdf.Root.get("/AcroForm", None)
            if acroform is None:
                raise ValueError("No AcroForm found in this PDF")

            # Get the XFA entry
            xfa = acroform.get("/XFA", None)
            if xfa is None:
                raise ValueError("No XFA data found")

            # Locating the dataset of the XFA (where the text for the fields is stored)
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

            # Update each field 
            for elem in root.iter():
                if elem.tag == "award":
                    elem.text = award
                elif elem.tag == "category":  
                    elem.text = category
                elif elem.tag == "nomineeTelephone":
                    elem.text = nom_telephone
                elif elem.tag == "awardPeriod":
                    elem.text = period
                elif elem.tag == "majcom_foa_dru":
                    elem.text = agency
                elif elem.tag == "rankName":
                    elem.text = f"{nom_rank} {nom_first_name} {nom_middle_initial} {nom_last_name}"
                elif elem.tag == "DAFSC":
                    elem.text = duty_tile
                elif elem.tag == "officeAddress":
                    elem.text = address
                elif elem.tag == "rank":
                    elem.text = f"{com_rank} {com_first_name} {com_middle_initial} {com_last_name} {com_telephone}"
                elif elem.tag == "specificAccomplishments":
                    elem.text = accomplishments_1
                elif elem.tag == "p2Name":
                    elem.text = f"{nom_rank} {nom_first_name} {nom_middle_initial} {nom_last_name}"
                elif elem.tag == "p2SpecificAccomplishments":
                    elem.text = accomplishments_2 

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
            pdf.save(self.output_path)

    def run(self):

        accomplishments = self.query_api(r"Tell me I'm pretty.")
        accomplishments_1, accomplishments_2 = self.check_length(accomplishments)

        self.format_1206(
            award="Being the Best",
            category="17",
            period="Right Here Right Now",
            nom_rank="A1C",
            nom_first_name="The",
            nom_middle_initial="Mr.",
            nom_last_name="Rumi",
            agency="Pink Pony Club",
            duty_tile="Boss Man",
            nom_telephone="555-555-5555",
            address="500 Here St",
            com_rank="N/A",
            com_first_name="N/A",
            com_middle_initial="N/A",
            com_last_name="N/A",
            com_telephone="555-555-5555",
            accomplishments_1=accomplishments_1,
            accomplishments_2=accomplishments_2
        )


if __name__ == "__main__":
    app = AwardWriter()
    app.run()