# Security policy

## Supported version

Security fixes are provided for the latest published release.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting feature instead of opening a public issue.
Include the affected version, reproduction steps, expected impact, and any relevant logs with
secrets and business data removed.

## Automation safety model

SoftAuto exposes named, saved elements through MCP. It does not expose arbitrary shell execution
or unrestricted coordinate clicking. Desktop actions can be disabled with
`SOFTAUTO_ALLOW_ACTIONS=0`. Review element libraries before sharing them because locators can
contain application titles, URLs, and control metadata.
