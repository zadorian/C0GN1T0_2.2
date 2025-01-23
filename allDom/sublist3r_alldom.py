import sys
import os
import sublist3r

if __name__ == "__main__":
    target_domain = input("Enter domain (e.g., example.com): ").strip()
    
    # Run sublist3r with minimal output
    subdomains = sublist3r.main(
        target_domain,
        threads=40,
        savefile=None,
        ports=None,
        silent=True,  # Keep True to minimize output
        verbose=False,
        enable_bruteforce=False,
        engines="ssl,virustotal,threatcrowd,netcraft,google,bing,baidu"  # Engines as comma-separated string
    ) or []  # Handle None return
    
    # Print clean list of subdomains
    cleaned_subdomains = set()
    for subdomain in subdomains:
        if subdomain:  # Check if subdomain is not None or empty
            cleaned = subdomain.replace('https://', '').replace('http://', '').replace('www.', '')
            if cleaned:
                cleaned_subdomains.add(cleaned)
    
    # Print sorted results
    for subdomain in sorted(cleaned_subdomains):
        print(subdomain)
