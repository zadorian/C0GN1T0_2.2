import requests
from datetime import datetime
from urllib.parse import urlparse

def get_whois_data(domain):
    """
    Fetches WHOIS data for the given domain using the WhoisXML API.

    Args:
        domain (str): The domain name to query.

    Returns:
        str: Formatted creation date or an error message.
    """
    # Endpoint for the Whois service
    url = "https://www.whoisxmlapi.com/whoisserver/WhoisService"

    # Parameters for the API request
    params = {
        "apiKey": "at_7uD0skEoBXIy7jn5LXSzgTFxsPmfd",
        "domainName": domain,
        "outputFormat": "JSON"
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        whois_record = data.get('WhoisRecord', {})
        created_date = whois_record.get('createdDate')

        if created_date:
            # Extract date part and format
            created_dt = datetime.strptime(created_date.split('T')[0], "%Y-%m-%d")
            return f"Domain registered: {created_dt.strftime('%d %B %Y')}"
        else:
            return "Domain registration date not available"

    except requests.RequestException as e:
        return f"An error occurred while fetching WHOIS data: {e}"
    except ValueError as ve:
        return f"Error parsing date: {ve}"
    except Exception as ex:
        return f"An unexpected error occurred: {ex}"

def main():
    """
    Main function to execute the WHOIS data retrieval.
    """
    url = input("Enter the domain to analyze (e.g., example.com): ").strip()

    # Validate and add scheme if missing
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    # Extract the domain
    parsed_url = urlparse(url)
    domain = parsed_url.netloc if parsed_url.netloc else parsed_url.path

    if not domain:
        print("Invalid domain. Please enter a valid domain.")
        return

    result = get_whois_data(domain)
    print(result)

if __name__ == "__main__":
    main()