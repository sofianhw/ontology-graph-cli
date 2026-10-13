"""Built-in, organization-neutral PRD template spec used when no template is supplied."""
from __future__ import annotations

from typing import Any


JUSTIFY_NOTE = "If you think this sub-section isn't applicable for your feature/product, provide a comment or justification of why it's not applicable. Do not leave it blank."


def _section(identifier: str, label: str, rule: str, guidance: list[str], number: str | None = None, aliases: list[str] | None = None) -> dict[str, Any]:
    return {"id": identifier, "label": label, "number": number, "rule": rule, "aliases": aliases or [], "guidance": guidance + ([JUSTIFY_NOTE] if rule == "justify" else []), "source_refs": []}


DEFAULT_TEMPLATE: dict[str, Any] = {
    "template_spec_version": 1,
    "name": "default PRD template",
    "source": "built-in",
    "sections": [
        _section("change_log", "Change Log", "required", ["Version", "Date", "Changes & Justification"], aliases=["Version History", "Revision History"]),
        _section("sign_offs", "Sign offs/Acknowledgements", "required", [
            "Please state the version the stakeholders are signing off on", "Version", "[please identify required relevant stakeholders for review]",
            "Disusun oleh", "Prepared by", "[Name]", "Product Manager", "Tanggal / Date", "Ditinjau oleh", "Reviewed by", "Head of Product",
            "Engineering Manager [Stream]", "Risk [Stream]", "Ops [Stream]", "Information Security [Stream]", "Relevant Stakeholders",
            "Disetujui oleh", "Approved by", "management", "Approved"], aliases=["Sign-off", "Sign offs", "Approvals", "Acknowledgements"]),
        _section("general_overview", "General Overview", "heading", [], aliases=["Overview"]),
        _section("background", "Background", "required", ["[Please give a high level description of the current situation and context, what the product is about, and how the product will work]"], aliases=["Context"]),
        _section("problem_statement", "Problem Statement", "required", ["[What is the problem you're trying to solve? This should be an end user-facing problem. This can be expanded to the corresponding stakeholders that it will impact]"], aliases=["Problem"]),
        _section("key_assumptions", "Key Assumptions", "required", ["[You can put assumptions in the phase of discovery on potential behaviors, usage, gaps that might be found with the implementation]"], aliases=["Assumptions"]),
        _section("impact_analysis", "Impact Analysis", "required", [
            "[what is the outcome from delivering this product, this will include:", "Qualitative", "(i.e) Customer Delight, Speed of use, Hygiene, Regulatory, Strategic direction etc.",
            "Quantitative", "(i.e) Revenue, User count, Cost optimization,etc.", "If any financial impacts, Revenue/ cost optimization please include any measurements and metrics associated to delivering this project by following the below table",
            "Financial Projections", "Users", "# new users", "# Existing Users", "# Total Users", "Cost", "Capital Expense", "Operating Expense", "License/ Maintenance Cost", "Income", "Interest Income", "Fee-based Income"],
            aliases=["Impact", "Success Metrics", "Expected Impact"]),
        _section("constraints", "Constraints", "required", ["[What are known limitations that we have today to overcome or rely on, to be able to deliver this product]"], aliases=["Limitations"]),
        _section("main_requirements", "Main Requirement section", "heading", [], aliases=["Main Requirements"]),
        _section("requirements", "Requirements", "heading", ["[What are you trying to accomplish? Be specific on impact and timeline]"]),
        _section("business_requirements", "Business Requirements", "required", ["This sub-section is mandatory"], "6.1", aliases=["Functional Requirements"]),
        _section("regulatory_requirements", "Regulatory Requirements (if any)", "justify", ["Please include Regulatory Requirements here, i.e. if needed by regulators or financial authorities, any standards to follow (e.g. open-banking API standards, ISO, etc.)"], "6.2", aliases=["Regulatory", "Compliance Requirements"]),
        _section("audit_trail", "Audit Trail (if any)", "justify", ["Please include Audit Trail requirements here, i.e. tracking user change requests, time of change, justification of change, storage of change, etc."], "6.3", aliases=["Audit Requirements"]),
        _section("feature_flag", "Feature Flag (if any)", "justify", ["Please include Feature Flag requirements here, i.e. to be able to turn features on/off at certain times, or if any need to hide features for any reasons."], "6.4", aliases=["Feature Flags", "Feature Toggle"]),
        _section("operational_requirements", "Operational requirements (if any)", "justify", ["Please include Operational requirements here, i.e. requirements requiring support from ops, BA teams as part of process of the product, additions to internal ops portals or customer-support tools"], "6.5", aliases=["Operations Requirements"]),
        _section("risk_requirements", "Risk requirements (if any)", "justify", ["Please include Risk requirements here, i.e. limits on product parameters, added security of user experience or during transactions, added authentication for money movement, etc."], "6.6"),
        _section("fraud_requirements", "Fraud Requirements (if any)", "justify", ["Please include Fraud requirements here, i.e. liveness check, multifactor authentication, rules implementations, etc."], "6.7"),
        _section("data_protection", "Data Protection (if any)", "justify", [
            "Include any data protection requirements applicable to your product or feature.", "If this section is not applicable, provide a short comment or justification — do not leave it blank.",
            "If your project processes personal data, please review and document the following:", "Types of Personal Data Processed", "(e.g., full name, National ID, phone number, email, location data, transaction data, biometrics, etc.)",
            "Legal Basis for Processing (if any)", "(explicit consent, contract, legal obligation, Data sharing agreement)", "Purpose of Processing", "(e.g., identity verification, service provision, analytics, regulatory compliance,etc.)",
            "Data Processing and Storage Location", "(onshore/offshore, vendor/cloud provider, data center location, encryption)", "If your project fill the additional requirement written here, please request for PIA assessment from DPO team"],
            "6.8", aliases=["Data Privacy", "Privacy Requirements"]),
        _section("privacy_impact_assessment", "Privacy Impact Assessment (PIA)", "optional", [
            "Please involve DPO team to conduct PIA if any one of the requirement below is checked for your current project", "Project involves large amount of personal data processing or collection.",
            "Personal data will be processed or stored outside of the home country (offshore).", "Project is a new product, feature, or platform, or involves major changes to an existing system or process of PII processing."],
            "6.8.2", aliases=["PIA"]),
        _section("reconciliation_requirements", "Reconciliation Requirements (if any)", "justify", ["Please include Reconciliation requirements here, i.e. reporting on daily transaction processing, internal account money movement general ledger balance reporting."], "6.9", aliases=["Reconciliation"]),
        _section("rollout_plan", "Roll-out Plan (if any)", "justify", ["Please include a Roll-out plan here, i.e. backward compatibility to prior mobile versions, GTM planning to align with product release, phased roll out based on users segments."], "6.10", aliases=["Rollout Plan", "Release Plan", "Go-to-market Plan"]),
        _section("event_trackers", "Event Trackers (if any)", "justify", ["Please include Event Tracker requirements here, i.e. mobile app behavior tracking, back end tracking for rewards, marketing tracker for user identification."], "6.11", aliases=["Event Tracking", "Analytics Events", "Tracking Requirements"]),
        _section("crm_brief", "CRM brief", "required", [
            "Please include planned nudges, reactivations, reminders to users once the product has been launched. What are the key events to be tracked and expected communications that will be pushed to users. This is NOT a notifications list, rather for marketing experimentation.",
            "Do not leave it blank", "Sample table of list of CRM", "Product", "Product, Validated by MKT Team", "User Type", "Lifecycle", "User Journey", "CTA to be activated", "Event Tracking", "Specific Requirement"],
            "6.12", aliases=["CRM", "CRM Plan", "Marketing Communications"]),
        _section("dependency_requests", "Dependency Requests", "justify", ["[What other streams will be required to complete this project, and what functions will other streams need to accomplish] IF APPLICABLE PLEASE LINK YOUR DR PRD HERE", "Supporting Squads", "Requirement", "Mock up/other supplementary information", "Any other relevant streams"], aliases=["Dependencies"]),
        _section("non_functional_requirements", "Non Functional Requirement", "required", ["[Non-Functional Requirement (NFR) specifies the quality attribute of a software system. They judge the software system based on Responsiveness, Usability, Security, Portability and other non-functional standards that are critical to the success of the software system.]"], aliases=["Non-Functional Requirements", "NFR"]),
        _section("flow_diagram", "Flow Diagram", "required", ["[Please outline how the product will be interacted with from either internal or external facing standpoint dependent on the product being launched]"], aliases=["User Flow", "Process Flow"]),
        _section("out_of_scope", "Out of scope", "required", ["[what functions will not be part of this product feature]"]),
        _section("user_stories", "User Stories / Acceptance Criteria", "required", ["No", "User Story", "Acceptance Criteria", "Priority", "Remarks", "As", "I want", "So", "Acceptance Criteria #1", "Acceptance Criteria #2", "Given", "When", "Then", "P0/P1/P2", "[This can be anything relevant to stories, including UI/UX screen, or other notes]"], aliases=["User Stories", "Acceptance Criteria"]),
        _section("others", "Others", "heading", []),
        _section("security_assessment", "Security assessment", "required", [
            "[to be filled by product with consultation with Infosec team]", "Area", "Description", "Is it applicable ?", "Infrastructure security", "If not using company infrastructure, information about Data center and DRC location",
            "Data Security & Integrity", "Product requirements should cover the need for parameter changes. Changes should not be performed directly on the backend (data patching)", "Data points involved and data transferred outside the company",
            "List of PII or sensitive data and Data Protection implemented", "User Access", "Frontend support for integration with the company identity provider (e.g. SSO, Radius, LDAP)", "Requirements of user roles that need to be implemented (checker, maker)",
            "Password policy (must follow the company password policy)", "Application Security", "Penetration testing plan", "For outsourced development or SaaS product: penetration testing report, security certifications and compliance standards on Application (if applicable, e.g. ISO 27001, SOC2,3)"],
            aliases=["Security", "Security Review"]),
        _section("references", "References", "optional", []),
    ],
    "tables": [
        {"id": "change_log_table", "label": "Change log table", "rule": "required", "columns": ["Version", "Date", "Changes & Justification"], "source_refs": []},
        {"id": "user_stories_table", "label": "User stories table", "rule": "required", "columns": ["No", "User Story", "Acceptance Criteria", "Priority", "Remarks"], "source_refs": []},
        {"id": "security_assessment_table", "label": "Security assessment table", "rule": "required", "columns": ["Area", "Description", "Is it applicable ?"], "source_refs": []},
        {"id": "crm_table", "label": "CRM table", "rule": "optional", "columns": ["User Type", "Lifecycle", "User Journey", "CTA to be activated", "Event Tracking", "Specific Requirement"], "source_refs": []},
        {"id": "dependency_table", "label": "Dependency requests table", "rule": "optional", "columns": ["Supporting Squads", "Requirement", "Mock up/other supplementary information"], "source_refs": []},
    ],
    "entity_types": {},
}
