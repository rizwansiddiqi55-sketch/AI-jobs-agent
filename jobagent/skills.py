"""Skill / certification / location vocabulary used to read job descriptions.

Canonical skill -> regex aliases. The profile lists which canonical skills the
candidate actually has; nothing here asserts experience by itself.
"""
import re

SKILLS = {
    "routing": [r"\brouting\b", r"\brouters?\b"],
    "switching": [r"\bswitching\b", r"\bswitches\b", r"\blayer ?2\b", r"\bl2\b", r"\bvlans?\b"],
    "layer 3": [r"\blayer ?3\b", r"\bl3\b"],
    "ospf": [r"\bospf\b"],
    "bgp": [r"\bbgp\b"],
    "eigrp": [r"\beigrp\b"],
    "mpls": [r"\bmpls\b"],
    "hsrp": [r"\bhsrp\b", r"\bvrrp\b", r"\bglbp\b"],
    "etherchannel": [r"\betherchannel\b", r"\bport-?channels?\b", r"\blacp\b", r"\bvpc\b"],
    "stp": [r"\bstp\b", r"\bspanning[- ]tree\b", r"\brstp\b"],
    "sd-wan": [r"\bsd-?wan\b"],
    "cisco": [r"\bcisco\b"],
    "cisco catalyst": [r"\bcatalyst\b", r"\bcat ?9[0-9]{3}\b"],
    "cisco wlc": [r"\bwlc\b", r"\b9800\b", r"wireless lan controller"],
    "cisco asa": [r"\bcisco asa\b", r"\basa\b(?! ?\d{4})"],
    "cisco ftd": [r"\bftd\b", r"\bfirepower\b", r"\bfmc\b"],
    "cisco ise": [r"\bcisco ise\b", r"\bise\b", r"identity services engine"],
    "catalyst center": [r"catalyst center", r"\bdna center\b", r"\bdnac\b"],
    "cisco aci": [r"\baci\b", r"\bnexus\b"],
    "fortinet": [r"\bfortinet\b", r"\bfortigate\b", r"\bfortimanager\b", r"\bfortianalyzer\b"],
    "palo alto": [r"palo ?alto", r"\bpan-os\b", r"\bpanorama\b"],
    "checkpoint": [r"check ?point"],
    "juniper": [r"\bjuniper\b", r"\bjunos\b", r"\bsrx\b"],
    "f5": [r"\bf5\b", r"\bbig-?ip\b"],
    "arista": [r"\barista\b"],
    "aruba": [r"\baruba\b"],
    "clearpass": [r"\bclearpass\b"],
    "nac": [r"\bnac\b", r"network access control", r"\b802\.1x\b"],
    "firewall": [r"\bfirewalls?\b"],
    "network security": [r"network security", r"\bsecurity hardening\b", r"\bhardening\b"],
    "vpn": [r"\bvpn\b", r"\bipsec\b", r"\bssl vpn\b"],
    "wireless": [r"\bwireless\b", r"\bwi-?fi\b", r"\bwlan\b"],
    "load balancer": [r"load[- ]balanc"],
    "dns/dhcp": [r"\bdns\b", r"\bdhcp\b", r"\bipam\b"],
    "troubleshooting": [r"troubleshoot", r"root cause"],
    "network monitoring": [r"\bsolarwinds\b", r"\bprtg\b", r"\bnagios\b", r"network monitoring", r"\bnetflow\b"],
    "siem/soc": [r"\bsiem\b", r"\bsoc\b", r"\bsplunk\b", r"\bqradar\b"],
    "zero trust": [r"zero[- ]trust", r"\bztna\b"],
    "sase/casb": [r"\bsase\b", r"\bcasb\b", r"\bswg\b", r"\bfwaas\b", r"\bdlp\b", r"\bzscaler\b", r"\bnetskope\b", r"prisma access"],
    "infoblox": [r"\binfoblox\b"],
    "vmware vsphere": [r"\bvsphere\b", r"\bvcd\b", r"cloud director", r"\bvmware\b"],
    "forescout": [r"\bforescout\b"],
    "sonicwall": [r"\bsonicwall\b"],
    "windows server": [r"windows server", r"active directory administration"],
    "cctv/pabx": [r"\bcctv\b", r"\bpabx\b"],
    "alcatel": [r"\balcatel\b"],
    "presales": [r"pre-?sales", r"\brfp\b", r"\bbom\b"],
    "python automation": [r"\bpython\b", r"\bansible\b", r"\bnetmiko\b", r"\bnapalm\b", r"\bterraform\b"],
    "cloud networking": [r"\baws\b", r"\bazure\b", r"\bgcp\b", r"cloud networking", r"\bvpc\b(?=.*cloud)"],
    "vmware nsx": [r"\bnsx\b"],
    "itil": [r"\bitil\b", r"service management", r"\bservicenow\b"],
}

CERTS = {
    "CCNA": [r"\bccna\b"],
    "CCNP": [r"\bccnp\b"],
    "CCIE": [r"\bccie\b"],
    "CCNP Security": [r"ccnp security", r"\bscor\b"],
    "CCNP Enterprise": [r"ccnp enterprise", r"\bencor\b"],
    "CCNP Data Center": [r"ccnp data ?cent"],
    "Fortinet NSE4": [r"\bnse ?4\b"],
    "Fortinet NSE5+": [r"\bnse ?[5-8]\b"],
    "PCNSA/PCNSE": [r"\bpcnsa\b", r"\bpcnse\b"],
    "JNCIA/JNCIP": [r"\bjncia\b", r"\bjncip\b", r"\bjncis\b"],
    "CISSP": [r"\bcissp\b"],
    "CEH": [r"\bceh\b"],
    "CompTIA Security+": [r"security\+", r"\bsec\+"],
    "ITIL": [r"\bitil\b"],
    "AWS cert": [r"aws certified"],
    "Azure cert": [r"\baz-\d{3}\b", r"azure certified"],
}

# A cert the candidate is deemed to cover through a higher one he holds.
CERT_COVERED_BY = {"CCNA": "CCNP", "Fortinet NSE4": "Fortinet NSE7"}

UAE_PRIMARY = ["dubai", "abu dhabi"]
UAE_OTHER = ["sharjah", "ajman", "ras al khaimah", "rak", "fujairah", "umm al quwain", "al ain",
             "uae", "united arab emirates"]
OTHER_COUNTRIES = ["singapore", "united kingdom", "uk", "london", "usa", "united states", "thailand",
                   "bangkok", "australia", "sydney", "melbourne", "ireland", "dublin", "netherlands",
                   "amsterdam", "saudi", "riyadh", "qatar", "doha", "kuwait", "bahrain", "oman",
                   "india", "canada", "germany"]

INDUSTRY_KEYWORDS = {
    "healthcare": [r"health", r"hospital", r"medical", r"clinic"],
    "government": [r"government", r"ministry", r"federal", r"authority", r"public sector"],
    "oil & gas": [r"oil", r"gas\b", r"petro", r"energy", r"adnoc", r"upstream"],
    "critical infrastructure": [r"critical infrastructure", r"utilit", r"\bot\b", r"scada", r"transport", r"aviation"],
    "financial services": [r"\bbank", r"financ", r"fintech", r"insurance"],
    "enterprise": [r"enterprise", r"corporate", r"campus", r"data ?cent"],
}


def find(patterns: dict, text: str) -> set:
    t = text.lower()
    return {name for name, pats in patterns.items() if any(re.search(p, t) for p in pats)}


def find_skills(text: str) -> set:
    return find(SKILLS, text)


def find_certs(text: str) -> set:
    return find(CERTS, text)
