"""Bank / institution directory (Phase 1.1).

Covers the six target markets. Code maps are demo-grade (G-8: real bank code
maps OK in demo, licensing review pending for production). Institutions not in
this directory must produce an explicit "unsupported bank" error — never a
silent pass-through.
"""

from dataclasses import dataclass


class UnsupportedBankError(Exception):
    def __init__(self, country: str, code: str) -> None:
        self.country = country
        self.code = code
        super().__init__(f"unsupported bank: {country}:{code}")


@dataclass(frozen=True)
class Institution:
    country: str
    code: str  # local bank code / short code
    name: str
    bic: str | None
    min_length: int
    max_length: int


def _i(
    country: str, code: str, name: str, bic: str | None, min_len: int, max_len: int
) -> Institution:
    return Institution(country, code, name, bic, min_len, max_len)


BANK_DIRECTORY: dict[tuple[str, str], Institution] = {
    # --- Indonesia (QRIS market, launch focus G-5) ---
    ("ID", "014"): _i("ID", "014", "BCA", "BCIDIDJA", 10, 10),
    ("ID", "002"): _i("ID", "002", "BRI", "BRINIDJA", 15, 15),
    ("ID", "008"): _i("ID", "008", "Mandiri", "BMRIIDJA", 12, 12),
    ("ID", "009"): _i("ID", "009", "BNI", "BNINIDJA", 10, 10),
    ("ID", "022"): _i("ID", "022", "CIMB Niaga", "CENAIDJA", 10, 16),
    ("ID", "011"): _i("ID", "011", "Bank Danamon", "SYNAIDJA", 10, 16),
    ("ID", "013"): _i("ID", "013", "Permata Bank", "BBBAIDJA", 10, 16),
    ("ID", "451"): _i("ID", "451", "BSI (Bank Syariah Indonesia)", "BSMDIDJA", 10, 16),
    ("ID", "016"): _i("ID", "016", "Maybank Indonesia", "IBBUIDJA", 10, 16),
    ("ID", "213"): _i("ID", "213", "BCA Syariah", "SYRBIDJA", 10, 16),
    # --- E-wallets (wallet identifiers, P1 — IDs are phone/email aliases) ---
    ("ID", "GOPAY"): _i("ID", "GOPAY", "GoPay (e-wallet)", None, 8, 16),
    ("ID", "OVO"): _i("ID", "OVO", "OVO (e-wallet)", None, 8, 16),
    ("ID", "DANA"): _i("ID", "DANA", "DANA (e-wallet)", None, 8, 16),
    # --- Malaysia ---
    ("MY", "MBB"): _i("MY", "MBB", "Maybank", "MBBEMYKL", 10, 12),
    ("MY", "CIMB"): _i("MY", "CIMB", "CIMB Bank", "CIMBMYKL", 10, 14),
    ("MY", "PBB"): _i("MY", "PBB", "Public Bank", "PBBEMYKL", 10, 12),
    ("MY", "RHB"): _i("MY", "RHB", "RHB Bank", "RHBBMYKL", 10, 14),
    ("MY", "HLB"): _i("MY", "HLB", "Hong Leong Bank", "HLBEMYKL", 10, 14),
    ("MY", "BIMB"): _i("MY", "BIMB", "Bank Islam", "BIMBMYKL", 10, 14),
    # --- Thailand ---
    ("TH", "KBANK"): _i("TH", "KBANK", "Kasikorn Bank (KBank)", "KASITHBK", 10, 10),
    ("TH", "SCB"): _i("TH", "SCB", "Siam Commercial Bank", "SICOTHBK", 10, 12),
    ("TH", "BBL"): _i("TH", "BBL", "Bangkok Bank", "BKKBTHBK", 10, 12),
    ("TH", "KTB"): _i("TH", "KTB", "Krungthai Bank", "KRTHTHBK", 10, 12),
    ("TH", "BAY"): _i("TH", "BAY", "Bank of Ayudhya (Krungsri)", "AYUDTHBK", 10, 12),
    # --- Singapore ---
    ("SG", "DBS"): _i("SG", "DBS", "DBS Bank", "DBSSSGSG", 9, 12),
    ("SG", "OCBC"): _i("SG", "OCBC", "OCBC Bank", "OCBCSGSG", 9, 12),
    ("SG", "UOB"): _i("SG", "UOB", "United Overseas Bank", "UOVSGSG", 9, 12),
    ("SG", "SCB"): _i("SG", "SCB", "Standard Chartered Singapore", "SCBLSGSG", 9, 12),
    # --- Vietnam ---
    ("VN", "VCB"): _i("VN", "VCB", "Vietcombank", "FTVBVNVX", 8, 16),
    ("VN", "MB"): _i("VN", "MB", "MB Bank", "ASCBVNVX", 8, 16),
    ("VN", "BIDV"): _i("VN", "BIDV", "BIDV", "BIDVVNVX", 8, 16),
    ("VN", "VTB"): _i("VN", "VTB", "VietinBank", "ICBKVNVX", 8, 16),
    ("VN", "AGB"): _i("VN", "AGB", "Agribank", "ABLBVNVX", 8, 16),
    # --- Philippines ---
    ("PH", "BDO"): _i("PH", "BDO", "BDO Unibank", "BNORPHMM", 10, 12),
    ("PH", "BPI"): _i("PH", "BPI", "Bank of the Philippine Islands", "BOPIPHMM", 10, 12),
    ("PH", "MB"): _i("PH", "MB", "Metrobank", "MBTCPHMM", 10, 12),
    ("PH", "LB"): _i("PH", "LB", "Landbank of the Philippines", "TLBAPHMM", 10, 12),
    ("PH", "RCBC"): _i("PH", "RCBC", "Rizal Commercial Banking Corp", "RCBCPHMM", 10, 12),
}

SUPPORTED_COUNTRIES = ("ID", "MY", "TH", "SG", "VN", "PH")


def get_institution(country: str, code: str) -> Institution:
    inst = BANK_DIRECTORY.get((country.upper(), code.upper()))
    if inst is None:
        raise UnsupportedBankError(country, code)
    return inst


def institutions_for_country(country: str) -> list[Institution]:
    return [i for (c, _), i in BANK_DIRECTORY.items() if c == country.upper()]
