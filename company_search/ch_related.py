import os
import requests
import openai
import sys

# -------------------------------------------------------------------
# NOTES:
# 1) This script is an example of an interactive CLI that uses
#    the Companies House API to search for companies by name,
#    fetch detailed information, and then find related companies
#    (address, name, directors), with an option to analyze via ChatGPT.
# 2) To run, install necessary libraries:
#       pip install requests openai
# 3) By default, it reads API keys from environment variables:
#       COMPANIES_HOUSE_API_KEY
#       OPENAI_API_KEY
#    If they are not set, the script will prompt for them.
# 4) Use your valid API keys or you'll get HTTP 401 Unauthorized errors.
# 5) This example includes minimal error handling and is meant as a
#    starting point. Handle edge cases, rate limits, etc., as needed.
# -------------------------------------------------------------------

COMPANIES_HOUSE_API_KEY = "13ed03e4-3d0b-447e-95c2-b2f397cf1e04"
OPENAI_API_KEY = "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"

# Set up environment variables or directly assign keys
os.environ["COMPANIES_HOUSE_API_KEY"] = COMPANIES_HOUSE_API_KEY
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# Configure OpenAI
openai.api_key = os.environ["OPENAI_API_KEY"]

CH_BASE_URL = "https://api.company-information.service.gov.uk"

def search_companies_by_name(company_name, items_per_page=5):
    """
    Searches Companies House for companies by name.
    Returns a list of basic search results.
    """
    url = f"{CH_BASE_URL}/search/companies"
    params = {
        "q": company_name,
        "items_per_page": items_per_page
    }
    response = requests.get(
        url,
        params=params,
        auth=(os.environ["CH_API_KEY"], '')
    )
    response.raise_for_status()
    data = response.json()
    return data.get("items", [])


def fetch_company_details(company_number):
    """
    Fetches company details (registered address, director info, etc.)
    for a given company_number.
    Returns a dictionary with relevant details.
    """
    profile_url = f"{CH_BASE_URL}/company/{company_number}"
    profile_res = requests.get(
        profile_url,
        auth=(os.environ["COMPANIES_HOUSE_API_KEY"], '')
    )
    profile_res.raise_for_status()
    profile_data = profile_res.json()

    address = profile_data.get("registered_office_address", {})

    officers_url = f"{CH_BASE_URL}/company/{company_number}/officers"
    officers_res = requests.get(
        officers_url,
        auth=(os.environ["COMPANIES_HOUSE_API_KEY"], '')
    )
    officers_res.raise_for_status()
    officers_data = officers_res.json()
    officers_items = officers_data.get("items", [])

    directors = []
    for officer in officers_items:
        if officer.get("officer_role", "").lower() == "director":
            name = officer.get("name", "")
            if name:
                directors.append(name)

    return {
        "company_number": company_number,
        "company_name": profile_data.get("company_name", ""),
        "address": address,
        "directors": directors
    }


def search_related_companies(detail_value, items_per_page=5):
    """
    Uses the Companies House search endpoint with detail_value
    (could be part of an address, a director name, or partial name).
    Returns a list of matches.
    """
    if not detail_value:
        return []

    url = f"{CH_BASE_URL}/search/companies"
    params = {
        "q": detail_value,
        "items_per_page": items_per_page
    }
    response = requests.get(
        url,
        params=params,
        auth=(os.environ["COMPANIES_HOUSE_API_KEY"], '')
    )
    response.raise_for_status()
    data = response.json()
    return data.get("items", [])


def analyze_with_chatgpt(data_for_analysis):
    """
    Sends data to ChatGPT API for analysis of related companies
    and ranking based on matches/similarities.
    """
    prompt = f"""
Given the following data about potential related companies, analyze the similarities
based on name matches, director names, and addresses. Then rank them from most likely
related to least likely. Return a concise JSON structure with each company's
'company_number' and a numeric 'score' (higher means more likely related).

Data:
{data_for_analysis}
    """

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a data analysis assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    return response.choices[0].message["content"]


def main():
    print("\nWelcome to the Interactive Companies House Search and Analysis Tool.\n")

    while True:
        try:
            company_name_input = input("Enter a company name to search (or 'quit' to exit): ").strip()
            if company_name_input.lower() in ("quit", "exit"):
                print("Exiting.")
                sys.exit(0)

            if not company_name_input:
                print("No company name entered. Please try again.\n")
                continue

            # Search for companies by name
            initial_results = search_companies_by_name(company_name_input, items_per_page=3)
            if not initial_results:
                print("No companies found. Please try another search.\n")
                continue

            # Fetch details for each matched company
            detailed_results = []
            for item in initial_results:
                cn = item.get("company_number")
                if cn:
                    details = fetch_company_details(cn)
                    detailed_results.append(details)

            # For each detailed result, search again by address, name, and directors
            related_companies_info = []
            for detail in detailed_results:
                address_str = " ".join(str(v) for v in detail["address"].values() if v)
                company_name = detail["company_name"]
                director_names = detail["directors"]

                address_matches = search_related_companies(address_str)
                name_matches = search_related_companies(company_name)
                director_matches = []
                for d in director_names:
                    director_matches.extend(search_related_companies(d))

                related_companies_info.append({
                    "source_company_number": detail["company_number"],
                    "source_company_name": detail["company_name"],
                    "searched_address": address_str,
                    "searched_directors": director_names,
                    "address_matches": address_matches,
                    "name_matches": name_matches,
                    "director_matches": director_matches
                })

            # Use ChatGPT to analyze and rank
            chatgpt_response = analyze_with_chatgpt(related_companies_info)
            print("\nChatGPT Analysis and Ranking:\n")
            print(chatgpt_response)
            print("\n-------------------------------------------\n")

        except requests.exceptions.HTTPError as http_err:
            if http_err.response.status_code == 401:
                print("HTTP Error 401: Unauthorized. Check your API key.")
                sys.exit(1)
            else:
                print(f"HTTP Error: {http_err}")
                sys.exit(1)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()