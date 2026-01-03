"""
Configuration for Hong Kong Judiciary scraper.
"""

from pydantic import BaseModel


class JudiciaryConfig(BaseModel):
    """Configuration specific to Judiciary scraper."""

    base_url: str = "https://legalref.judiciary.hk"
    request_delay: float = 3.0
    max_concurrent: int = 2
    timeout: int = 60000
    max_retries: int = 3
    headless: bool = True

    # Scraping parameters
    start_year: int = 2000
    end_year: int = 2027
    courts: list[str] = None

    def __init__(self, **data):
        super().__init__(**data)
        if self.courts is None:
            self.courts = list(COURTS.keys())


# Court codes and their full names
COURTS = {
    "CFA": "Court of Final Appeal",
    "CA": "Court of Appeal",
    "CFI": "Court of First Instance",
    "DC": "District Court",
    "FC": "Family Court",
    "LT": "Lands Tribunal",
    "LAB": "Labour Tribunal",
    "SCT": "Small Claims Tribunal",
    "KCCC": "Kowloon City Magistrates' Courts",
    "ESCC": "Eastern Magistrates' Courts",
    "KTCC": "Kwun Tong Magistrates' Courts",
    "STCC": "Sha Tin Magistrates' Courts",
    "FLCC": "Fanling Magistrates' Courts",
    "TMCC": "Tuen Mun Magistrates' Courts",
    "TWCC": "Tsuen Wan Magistrates' Courts",
    "WKCC": "West Kowloon Magistrates' Courts",
}

# Court hierarchy (1 = highest)
COURT_HIERARCHY = {
    "CFA": 1,
    "CA": 2,
    "CFI": 3,
    "DC": 4,
    "FC": 4,
    "LT": 4,
    "LAB": 5,
    "SCT": 5,
    "KCCC": 5,
    "ESCC": 5,
    "KTCC": 5,
    "STCC": 5,
    "FLCC": 5,
    "TMCC": 5,
    "TWCC": 5,
    "WKCC": 5,
}

# Citation code mapping (neutral citation prefix)
CITATION_CODES = {
    "CFA": "HKCFA",
    "CA": "HKCA",
    "CFI": "HKCFI",
    "DC": "HKDC",
    "FC": "HKFC",
    "LT": "HKLT",
    "LAB": "HKLAB",
    "SCT": "HKSCT",
}

# Case number prefixes by court
CASE_NUMBER_PREFIXES = {
    "CFA": ["FACV", "FACC", "FAMV", "FAMC", "FAMP"],
    "CA": ["CACV", "CACC", "CAAR", "CAMP", "CAQL"],
    "CFI": [
        "HCAL", "HCMP", "HCCT", "HCCL", "HCSD", "HCPI", "HCMC", "HCCW",
        "HCAJ", "HCAP", "HCBD", "HCBI", "HCBS", "HCCM", "HCCP", "HCCV",
        "HCEA", "HCLA", "HCMA", "HCMH", "HCOA", "HCRC", "HCSA", "HCWS",
    ],
    "DC": ["DCCC", "DCEC", "DCMP", "DCPI", "DCCJ", "DCEO", "DCTC"],
    "FC": ["FCMC", "FCMP", "FCJA", "FCRE"],
    "LT": ["LDBM", "LDMR", "LDCS", "LDPD", "LDRT", "LDLA", "LDLR", "LDMT"],
}
