import os
import time
from google import genai
from google.genai import types 


# --- VAŠE NASTAVENIA ---
API_KEY = "PASTE_YOUR_KEY" # Získajte na aistudio.google.com
PDF_FILENAME = "policy.pdf" # Názov súboru s politikou banky
OUTPUT_FILENAME = "risks.csv"   # Názov výstupného súboru
TH_FILENAME = "analysis.txt" # Názov súboru z analyzou

# Nastavenie prístupu
client = genai.Client(api_key=API_KEY)

def read_file_content(filename):
    """Prečíta textový súbor a vráti jeho obsah."""
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Upozornenie: Súbor '{filename}' nebol nájdený. Preskakujem.")
        return ""
    except Exception as e:
        print(f"Chyba pri čítaní '{filename}': {e}")
        return ""


def analyze_security_risks():
    print(f"--- Spúšťam analyzátor na báze Gemini modelu (s myslením) ---")

    # 1. Načítanie pomocných súborov (katalógy)
    print("1. Čítam CSV a inštrukcie...")

    context_data = ""
    files_to_read = [
        ("hrozby.csv", "KATALÓG_HROZIEB"),
        ("majetok.csv", "KATALÓG_MAJETKU"),
        ("zranitelnosti.csv", "KATALÓG_ZRANITEĽNOSTÍ"),
        ("iso_norma.csv", "ISO_POŽIADAVKY"),
        ("metodika.md", "METODIKA_POSÚDENIA_RIZÍK"),
        ("instruction.txt", "POUŽÍVATEĽSKÁ_INŠTRUKCIA")
    ]

    for fname, tag in files_to_read:
        content = read_file_content(fname)
        if content:
            context_data += f"\n--- REFERENCE START: {tag} ({fname}) ---\n{content}\n--- REFERENCE END ---\n"

    # 2. Načítanie PDF do Google cloudu (cacheovanie)
    print(f"2. Nahrávam PDF '{PDF_FILENAME}' do Gemini...")
    try:
        pdf_file = client.files.upload(file=PDF_FILENAME)

        while pdf_file.state.name == "PROCESSING":
            print("   Spracovávam PDF...", end='\r')
            time.sleep(2)
            pdf_file = client.files.get(name=pdf_file.name)

        if pdf_file.state.name == "FAILED":
            raise ValueError("Google nedokázal spracovať tento PDF.")

        print(f"   PDF pripravené: {pdf_file.uri}")

    except Exception as e:
        print(f"\nKritická chyba s PDF: {e}")
        return

    # 3. Príprava požiadavky pre model
    print("3. Posielam požiadavku do Gemini modelu (s myslením)...")

    system_prompt = """
    You are an expert Security Risk Analyst meant to automate ISO 27001 compliance checks.
    You have access to a set of reference catalogs (Threats, Assets, Vulnerabilities) and a Methodology.

    YOUR GOAL:
    1. Read the provided PDF with the organization security Policy.
    2. Read the ISO requirements from the provided CSV data.
    3. Identify gaps where the Policy fails to meet ISO requirements.
    4. For each gap, generate a Risk Assessment strictly following the format in 'instruction.txt'.
    5. Use ONLY the terms found in the provided CSV files (Hrozby, Majetok, Zranitelnosti) for filling those fields.
    6. Output MUST be ONLY the CSV in the format like in instruction.txt, in Slovak, with NO additional explanations, headers, or markdown/JSON wrappers.
    7. You have to output at least 100 vulnerabilities
    8. All text data in CSV must be in quotes to keep CSV format
    9. Try to not overestimate risks: try to keep not more than 10 very high and not more than 20 high risks.
    """

    full_contents = [
        pdf_file,
        system_prompt,
        context_data,
        "Task: Perform the analysis now. Identify not less than risks and generate the output exactly as requested in the instruction.txt format. Do not include any introductory or concluding text in your final output."
    ]

    # 4. Získanie odpovede s konfiguráciou myslenia
    try:
        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=full_contents,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(
                    include_thoughts=True
                ),
                max_output_tokens=99999999
            )
        )

        # 5. Spracovanie a výpis výsledkov
        print("\n" + "="*50)
        print("VÝSLEDOK ANALÝZY:")
        print("="*50)

        report_output = []
        thoughts_output = []

        # Prechádzame časti odpovede
        for candidate in response.candidates:
            for part in candidate.content.parts:
                if part.text:
                    if part.thought:
                        # Ak je to myslenie (iba výpis na konzolu)
                        print("\n--- Premyšľanie Gemini ---")
                        print(part.text.strip())
                        print("-------------------------------------------------")
                        thoughts_output.append(part.text.strip())
                    else:
                        # Ak je to finálny report (uložíme)
                        report_output.append(part.text.strip()) # Iba tento obsah pôjde do súboru

        # Uložíme výstup
        with open(TH_FILENAME, "w", encoding="utf-8") as f:
            f.write("\n---\n".join(thoughts_output))
        with open(OUTPUT_FILENAME, "w", encoding="utf-8") as f:
            f.write("\n---\n".join(report_output)) # Pridávame oddeľovač medzi rizikami

        print(f"\nHotovo, výstup modelu bol uložený.")

    except Exception as e:
        print(f"\nChyba pri generovaní: {e}")

if __name__ == "__main__":
    analyze_security_risks()