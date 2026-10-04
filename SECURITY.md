# Security and privacy

Please avoid publishing real diagnostic evidence in issues. Raw crash dumps may contain private memory. Hashes and redaction reduce some disclosure, but do not guarantee anonymity.

The project runs local PowerShell queries and, only when explicitly invoked, an existing local CDB executable. Reports do not fetch remote assets. CDB's symbol lookup contacts Microsoft's symbol server; that side effect is documented separately.

For a suspected vulnerability, use the repository's private vulnerability-reporting feature if available, or contact the repository owner privately. Provide a minimal synthetic reproducer without credentials, dumps or personal data. Public bug reports should not include exploitable private details.
